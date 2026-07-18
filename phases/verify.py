"""VERIFY phase: auto-tests, linting, verification rubric."""
from __future__ import annotations
import logging, subprocess, os
from cortex.lib.db import execute, query

logger = logging.getLogger(__name__)

VERIFY_COMMANDS = {
    "python": ["python -m pytest tests/ -v --tb=short", "ruff check ."],
    "typescript": ["npx tsc --noEmit", "npx eslint ."],
    "generic": ["echo 'No verify command configured'"],
}


def verify_task(task_id: str) -> tuple[bool, str]:
    """Run verification for a task. Returns (passed, output)."""
    tasks = query("SELECT * FROM cortex_tasks WHERE id = ?", (task_id,))
    if not tasks:
        return False, "Task not found"

    task = dict(tasks[0])
    execute("UPDATE cortex_tasks SET status = 'verify', phase = 'verify' WHERE id = ?", (task_id,))

    verify_cmd = task.get("verify_command") or "python -m pytest tests/ -v --tb=short"
    project_id = task.get("project_id") or ""

    output_lines = []
    all_passed = True

    try:
        for cmd in [verify_cmd]:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=600,
                cwd=f"/home/hermes/projects/{project_id}" if project_id else "/home/hermes",
            )
            output_lines.append(f"$ {cmd}")
            output_lines.append(result.stdout[-2000:])
            if result.stderr:
                output_lines.append(result.stderr[-1000:])
            if result.returncode != 0:
                all_passed = False

        output = "\n".join(output_lines)
        if all_passed:
            execute("UPDATE cortex_tasks SET status = 'review', phase = 'review' WHERE id = ?", (task_id,))
        else:
            execute("UPDATE cortex_tasks SET status = 'failed', phase = 'verify' WHERE id = ?", (task_id,))

        return all_passed, output
    except Exception as e:
        execute("UPDATE cortex_tasks SET status = 'failed', phase = 'verify' WHERE id = ?", (task_id,))
        return False, str(e)
