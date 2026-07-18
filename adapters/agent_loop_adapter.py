"""Read agent-loop state to avoid duplicating active tasks.
Agent-loop continues running independently — Cortex only READS, never writes.
"""
from __future__ import annotations
import sqlite3, logging, os
from pathlib import Path

logger = logging.getLogger(__name__)

AGENT_LOOP_STATE = Path(
    os.environ.get("AGENT_LOOP_STATE_PATH", "/home/hermes/agent-loop-state.db")
)


def get_active_agent_loop_tasks() -> list[str]:
    """Return list of task IDs that agent-loop is currently working on.
    Returns empty list if agent-loop state is unavailable.
    """
    if not AGENT_LOOP_STATE.exists():
        logger.info("agent-loop state not found at %s — assuming no active tasks", AGENT_LOOP_STATE)
        return []

    try:
        conn = sqlite3.connect(str(AGENT_LOOP_STATE))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id FROM tasks WHERE status IN ('in_progress', 'processing')"
        ).fetchall()
        conn.close()
        return [r["id"] for r in rows]
    except Exception as e:
        logger.warning(f"Failed to read agent-loop state: {e}")
        return []


def is_agent_loop_busy() -> bool:
    return len(get_active_agent_loop_tasks()) > 0
