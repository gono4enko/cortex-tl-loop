"""KB-WRITE phase: record to Obsidian + ChromaDB + Ledger."""
from __future__ import annotations
import logging, datetime, json
from cortex.lib.db import execute, query

logger = logging.getLogger(__name__)

OBSIDIAN_KB_PATH = "/home/hermes/obsidian-kb"


def kb_write_task(task_id: str) -> dict:
    """Write task result to knowledge base. Returns refs dict."""
    tasks = query("SELECT * FROM cortex_tasks WHERE id = ?", (task_id,))
    if not tasks:
        return {"error": "task not found"}

    task = dict(tasks[0])
    project = task.get("project_id") or "cortex"
    date_str = datetime.date.today().isoformat()

    # Build Obsidian markdown note
    note = f"""# {task['title']}
- **Task:** {task['id']}
- **Project:** {project}
- **Status:** {task['status']}
- **Executor:** {task.get('executor_agent', 'auto')}
- **Priority:** {task['priority']}
- **Created:** {task['created_at']}
- **Completed:** {task.get('completed_at', datetime.datetime.utcnow().isoformat())}

## Description
{task.get('body') or task['title']}

## Result
Status: {task['status']}
Phase: {task.get('phase', 'unknown')}
"""

    obsidian_path = f"cortex/tasks/{project}/{date_str}-{task_id}.md"

    try:
        full_path = f"{OBSIDIAN_KB_PATH}/06-ai-context/{obsidian_path}"
        import os
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(note)

        # Record KB ref
        execute(
            "INSERT INTO kb_refs (task_id, obsidian_path) VALUES (?, ?)",
            (task_id, obsidian_path),
        )

        execute("UPDATE cortex_tasks SET status = 'done', phase = 'kb-write' WHERE id = ?", (task_id,))
        logger.info(f"KB-WRITE: {task_id} → {obsidian_path}")
        return {"obsidian_path": obsidian_path}
    except Exception as e:
        logger.error(f"KB-WRITE: {task_id} failed: {e}")
        return {"error": str(e)}
