"""INGEST phase: accept tasks from CLI, Telegram, agent-loop adapter."""
from __future__ import annotations
import logging, uuid, datetime
from cortex.lib.db import execute, query

logger = logging.getLogger(__name__)


def create_task(
    title: str,
    body: str = "",
    project_id: str = "",
    priority: int = 3,
    needs_human: int = 0,
) -> str:
    """Create a new cortex task. Returns task_id."""
    task_id = f"cortex-{datetime.date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    execute(
        """INSERT INTO cortex_tasks (id, title, body, project_id, status, phase, priority, needs_human)
           VALUES (?, ?, ?, ?, 'ingest', 'ingest', ?, ?)""",
        (task_id, title, body, project_id, priority, needs_human),
    )
    logger.info(f"INGEST: created task {task_id} — {title}")
    return task_id


def get_pending_tasks(limit: int = 20) -> list:
    """Get tasks in ingest/planning/ready status."""
    return query(
        """SELECT * FROM cortex_tasks
           WHERE status IN ('ingest', 'planning', 'ready')
           ORDER BY priority DESC, created_at ASC
           LIMIT ?""",
        (limit,),
    )


def update_task_status(task_id: str, status: str, phase: str = None):
    params = [status, datetime.datetime.utcnow().isoformat(), task_id]
    phase_sql = ""
    if phase:
        phase_sql = ", phase = ?"
        params.insert(0, phase)
    execute(
        f"UPDATE cortex_tasks SET status = ?, updated_at = ?{phase_sql} WHERE id = ?",
        tuple(params),
    )


def get_tasks_by_status(status: str) -> list:
    return query("SELECT * FROM cortex_tasks WHERE status = ?", (status,))
