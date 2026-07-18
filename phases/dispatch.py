"""DISPATCH phase: assign tasks to best-fit executor."""
from __future__ import annotations
import logging, datetime, json
from cortex.lib.db import query, execute

logger = logging.getLogger(__name__)

EXECUTOR_PRIORITY = [
    "mac-opencode",
    "mac-kilo",
    "kilo-hermes",
    "hermes-opencode",
    "hermes-bot",
]

COMPLEXITY_MAP = {
    "high": ["mac-opencode", "hermes-opencode"],
    "med": ["mac-kilo", "kilo-hermes", "mac-opencode"],
    "low": ["hermes-bot", "kilo-hermes", "mac-kilo"],
}


def get_available_agents() -> list:
    """Get agents with heartbeat within stale timeout."""
    stale_sec = 120
    rows = query(
        """SELECT agent, status, last_seen, current_task_id
           FROM heartbeats
           WHERE status = 'alive'
             AND datetime(last_seen) > datetime('now', ?)""",
        (f"-{stale_sec} seconds",),
    )
    return [dict(r) for r in rows]


def assign_executor(task_id: str, complexity: str = "med") -> str | None:
    """Assign best available executor for task complexity. Returns agent name or None."""
    available = get_available_agents()
    if not available:
        logger.warning(f"DISPATCH: no available agents for {task_id}")
        return None

    available_names = {a["agent"] for a in available if not a["current_task_id"]}

    candidates = COMPLEXITY_MAP.get(complexity, COMPLEXITY_MAP["med"])
    for agent in candidates:
        if agent in available_names:
            execute(
                "UPDATE cortex_tasks SET executor_agent = ?, status = 'in_progress', phase = 'execute', started_at = ? WHERE id = ?",
                (agent, datetime.datetime.utcnow().isoformat(), task_id),
            )
            execute(
                "UPDATE heartbeats SET current_task_id = ? WHERE agent = ?",
                (task_id, agent),
            )
            logger.info(f"DISPATCH: {task_id} → {agent} (complexity={complexity})")
            return agent

    logger.warning(f"DISPATCH: no matching agent for {task_id} (wanted {candidates}, available {available_names})")
    return None


def create_assignment(task_id: str, agent: str):
    """Log assignment in assignments table."""
    execute(
        "INSERT INTO assignments (task_id, agent) VALUES (?, ?)",
        (task_id, agent),
    )
