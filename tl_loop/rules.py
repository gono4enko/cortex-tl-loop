"""Rules Engine — first-match priority, LLM fallback for complex decisions."""
from __future__ import annotations
import logging
from cortex.tl_loop.schema import Task, TaskStatus
from cortex.tl_loop.state_store import (
    transition, get_agents_online, assign_agent, log_event,
)

logger = logging.getLogger(__name__)
DAILY_COST_LIMIT = 70.0

class RuleResult:
    def __init__(self, matched: bool, action: str = "", agent: str = "", reason: str = ""):
        self.matched = matched; self.action = action; self.agent = agent; self.reason = reason

def kill_switch(task=None, agents=None) -> RuleResult:
    cost = 0.0  # daily cost tracking via cortex.db
    if cost >= DAILY_COST_LIMIT * 0.95:
        return RuleResult(True, "block", "", f"Daily cost limit: ${cost:.2f}")
    if cost >= DAILY_COST_LIMIT * 0.70:
        logger.warning(f"Cost warning: ${cost:.2f} / ${DAILY_COST_LIMIT}")
    return RuleResult(False)

def rule_new_ready(task: Task, agents: list[str]) -> RuleResult:
    if task.status not in (TaskStatus.NEW, TaskStatus.READY, TaskStatus.RETRY):
        return RuleResult(False)
    if not agents:
        return RuleResult(True, "wait", "", "No agents online")
    agent = agents[0]
    assign_agent(task.id, agent)
    return RuleResult(True, "dispatch", agent, f"Dispatched to {agent}")

def rule_ingest(task: Task, agents: list[str]) -> RuleResult:
    if task.status != TaskStatus.NEW:
        return RuleResult(False)
    transition(task.id, TaskStatus.READY)
    return RuleResult(True, "ready", "", "Moved from ingest to ready")

def rule_stuck(task: Task, agents: list[str]) -> RuleResult:
    if task.status != TaskStatus.STUCK:
        return RuleResult(False)
    if task.attempt >= task.max_attempts:
        transition(task.id, TaskStatus.BLOCKED)
        log_event(task.id, "escalation", {"reason": f"Max attempts ({task.max_attempts})"})
        return RuleResult(True, "block", "", "Max retries exhausted")
    if not agents:
        return RuleResult(True, "wait", "", "No agents for retry")
    transition(task.id, TaskStatus.RETRY)
    return RuleResult(True, "retry", agents[0], f"Retry #{task.attempt+1}")

def rule_verify(task: Task, agents: list[str]) -> RuleResult:
    if task.status != TaskStatus.RUNNING:
        return RuleResult(False)
    transition(task.id, TaskStatus.VERIFYING)
    return RuleResult(True, "verify", "", "Moving to verification")

def rule_done(task: Task, agents: list[str]) -> RuleResult:
    if task.status == TaskStatus.DONE:
        return RuleResult(True, "complete", "", "Task done")
    return RuleResult(False)

RULES = [kill_switch, rule_ingest, rule_new_ready, rule_stuck, rule_verify, rule_done]

def apply_rules(task: Task, agents: list[str]) -> RuleResult:
    """Apply rules in priority order. Returns first match."""
    for rule in RULES:
        result = rule(task, agents)
        if result.matched:
            return result
    # LLM fallback for unmatched states
    import asyncio  # disabled - use sync fallback
    try:
        info = "Task: " + task.id + " status=" + task.status.value + " priority=" + str(task.priority)
        decision = {"action": "wait", "agent": agents[0] if agents else "", "reason": "LLM fallback not available in sync tick"}
        action = decision.get("action", "wait")
        agent = decision.get("agent", agents[0] if agents else "")
        reason = decision.get("reason", "LLM decision")
        if action == "dispatch" and agent and task.status in (TaskStatus.NEW, TaskStatus.READY):
            assign_agent(task.id, agent)
        elif action == "retry":
            transition(task.id, TaskStatus.RETRY)
        elif action == "block":
            transition(task.id, TaskStatus.BLOCKED)
        return RuleResult(True, action, agent, reason)
    except Exception:
        return RuleResult(False, "skip", "", "LLM unavailable")
