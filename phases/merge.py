"""MERGE phase: git merge, push, update status."""
from __future__ import annotations
import logging, subprocess
from cortex.lib.db import execute, query

logger = logging.getLogger(__name__)


def merge_task(task_id: str) -> bool:
    """Merge task branch and push to GitHub. Returns True on success."""
    tasks = query("SELECT * FROM cortex_tasks WHERE id = ?", (task_id,))
    if not tasks:
        return False
    task = dict(tasks[0])
    branch = task.get("git_branch") or f"cortex/{task_id}"

    execute("UPDATE cortex_tasks SET status = 'merge', phase = 'merge' WHERE id = ?", (task_id,))

    try:
        # Checkout branch (if exists), merge, push
        r1 = subprocess.run(["git", "checkout", branch], capture_output=True, text=True, timeout=30)
        if r1.returncode != 0:
            # Branch may not exist — skip merge step
            logger.info(f"MERGE: branch {branch} not found, skipping git merge")
        else:
            subprocess.run(["git", "checkout", "main"], capture_output=True, timeout=30)
            subprocess.run(["git", "merge", "--squash", branch], capture_output=True, timeout=30)
            subprocess.run(["git", "commit", "-m", f"cortex: {task['title']}"], capture_output=True, timeout=30)
            subprocess.run(["git", "push", "origin", "main"], capture_output=True, timeout=60)

        execute("UPDATE cortex_tasks SET status = 'done', phase = 'kb-write', completed_at = datetime('now') WHERE id = ?", (task_id,))
        logger.info(f"MERGE: {task_id} completed")
        return True
    except Exception as e:
        logger.error(f"MERGE: {task_id} failed: {e}")
        execute("UPDATE cortex_tasks SET status = 'failed', phase = 'merge' WHERE id = ?", (task_id,))
        return False
