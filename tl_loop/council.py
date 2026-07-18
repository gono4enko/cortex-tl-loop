"""Expert Council — 3-expert debate for blocked/stuck tasks."""
from __future__ import annotations
import requests, logging, json, os
from cortex.tl_loop.schema import Task

logger = logging.getLogger("council")

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPINFRA_KEY = os.environ.get("DEEPINFRA_API_KEY", "")

EXPERTS = {
    "glm": {"model": "zai-org/GLM-5.2", "provider": "deepinfra", "role": "System Architect"},
    "claude": {"model": "anthropic/claude-fable-5", "provider": "deepinfra", "role": "Strategist"},
    "deepseek": {"model": "deepseek-chat", "provider": "deepseek", "role": "Pragmatist Critic"},
}

COUNCIL_PROMPT = """You are {role} in an expert council. A task is blocked/stuck.

Task: {title}
Description: {description}
Files: {files}
Attempts: {attempt}/{max_attempts}
Status: {status}
Block reason: {reason}

Analyze and return JSON:
{{"verdict": "retry"|"rework"|"escalate"|"abandon", "action": "specific next step", "reason": "why"}}"""

SYNTHESIS_PROMPT = """You are the Tech Lead. Three experts gave recommendations:

GLM-5.2 (architect): {glm_verdict} — {glm_action}
Claude (strategist): {claude_verdict} — {claude_action}
DeepSeek (pragmatist): {deepseek_verdict} — {deepseek_action}

Make final decision. Return JSON:
{{"verdict": "retry"|"rework"|"escalate"|"abandon", "action": "final step", "consensus": true|false}}"""


def _call_llm(provider: str, model: str, prompt: str, max_tokens: int = 1024) -> str:
    try:
        if provider == "deepseek":
            r = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": max_tokens, "temperature": 0.3},
                timeout=120,
            )
        else:
            r = requests.post(
                "https://api.deepinfra.com/v1/openai/chat/completions",
                headers={"Authorization": f"Bearer {DEEPINFRA_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": max_tokens, "temperature": 0.4},
                timeout=180,
            )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        logger.error(f"Council LLM ({model}): {r.status_code}")
        return ""
    except Exception as e:
        logger.error(f"Council LLM error ({model}): {e}")
        return ""


def _parse_verdict(content: str) -> dict:
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return {"verdict": "escalate", "action": "manual review", "reason": "parse failed"}


def convene(task: Task, reason: str = "") -> dict:
    logger.info(f"Council: convening for {task.id[:20]} ({reason})")

    expert_results = {}
    for name, cfg in EXPERTS.items():
        prompt = COUNCIL_PROMPT.format(
            role=cfg["role"],
            title=task.title or "unknown",
            description=task.description or "no description",
            files=", ".join(task.touched_files) if task.touched_files else "unknown",
            attempt=task.attempt, max_attempts=task.max_attempts,
            status=task.status or "blocked", reason=reason or "unknown",
        )
        content = _call_llm(cfg["provider"], cfg["model"], prompt)
        expert_results[name] = _parse_verdict(content)
        expert_results[name]["raw"] = content[:300]
        logger.info(f"Council: {name} -> {expert_results[name].get('verdict')}")

    synthesis = SYNTHESIS_PROMPT.format(
        glm_verdict=expert_results.get("glm", {}).get("verdict", "?"),
        glm_action=expert_results.get("glm", {}).get("action", "?"),
        claude_verdict=expert_results.get("claude", {}).get("verdict", "?"),
        claude_action=expert_results.get("claude", {}).get("action", "?"),
        deepseek_verdict=expert_results.get("deepseek", {}).get("verdict", "?"),
        deepseek_action=expert_results.get("deepseek", {}).get("action", "?"),
    )
    final_content = _call_llm("deepseek", "deepseek-chat", synthesis, max_tokens=512)
    final = _parse_verdict(final_content)
    final["experts"] = {k: {"verdict": v.get("verdict"), "action": v.get("action")}
                        for k, v in expert_results.items()}

    logger.info(f"Council: final -> {final.get('verdict')}: {final.get('action')}")
    return final


def should_convene(task: Task) -> tuple[bool, str]:
    if task.attempt >= 3:
        return True, f"3+ retries ({task.attempt}/{task.max_attempts})"
    if task.status and "stuck" in task.status.lower():
        return True, "task stuck"
    if task.status and "blocked" in task.status.lower():
        return True, "task blocked"
    return False, ""
