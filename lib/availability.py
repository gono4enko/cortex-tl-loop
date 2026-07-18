"""Agent availability tracking via heartbeat."""
from __future__ import annotations
import datetime
from cortex.lib.db import query, execute


def heartbeat(agent: str, status: str = "alive", current_task_id: str = None):
    execute(
        """INSERT OR REPLACE INTO heartbeats (agent, last_seen, status, current_task_id)
           VALUES (?, datetime('now'), ?, ?)""",
        (agent, status, current_task_id),
    )


def mark_stale(timeout_sec: int = 120):
    """Mark agents with stale heartbeat as 'stale'."""
    query(
        """UPDATE heartbeats SET status = 'stale'
           WHERE status = 'alive'
             AND datetime(last_seen) < datetime('now', ?)""",
        (f"-{timeout_sec} seconds",),
    )


def get_agent_status(agent: str) -> dict | None:
    rows = query("SELECT * FROM heartbeats WHERE agent = ?", (agent,))
    return dict(rows[0]) if rows else None


def is_agent_available(agent: str) -> bool:
    row = get_agent_status(agent)
    if not row:
        return False
    return row["status"] == "alive" and not row["current_task_id"]
