"""EXECUTE phase: launch executor agents with task contracts."""
from __future__ import annotations
import logging, subprocess, os, json, datetime, tempfile
from pathlib import Path
from cortex.lib.db import execute, query

logger = logging.getLogger(__name__)

EXECUTOR_COMMANDS = {
    "mac-opencode": "/opt/homebrew/bin/opencode run",
    "mac-kilo": "kilo run",
    "kilo-hermes": "/home/hermes/.hermes-venv/bin/hermes run",
    "hermes-opencode": "/home/hermes/.opencode/bin/opencode run",
    "hermes-bot": "/home/hermes/.hermes-venv/bin/python -m hermes_assistant.bot",
}


def build_contract(task: dict) -> str:
    """Build a task contract string for the executor."""
    touched = task.get("touched_files", "[]")
    forbidden = task.get("forbidden_files", "[]")
    criteria = task.get("acceptance_criteria", "[]")
    verify = task.get("verify_command", "")

    try:
        touched = json.loads(touched) if isinstance(touched, str) else touched
        forbidden = json.loads(forbidden) if isinstance(forbidden, str) else forbidden
        criteria = json.loads(criteria) if isinstance(criteria, str) else criteria
    except json.JSONDecodeError:
        pass

    contract = f"""# Task: {task['id']}
# Project: {task.get('project_id', '')}
# Executor: {task.get('executor_agent', '')}

## Objective
{task.get('body') or task.get('title', '')}

## Touched Files
{chr(10).join(f'- {f}' for f in (touched if isinstance(touched, list) else [])) or '- (none specified)'}

## Forbidden Files
{chr(10).join(f'- {f}' for f in (forbidden if isinstance(forbidden, list) else [])) or '- (none specified)'}

## Acceptance Criteria
{chr(10).join(f'- {c}' for c in (criteria if isinstance(criteria, list) else [])) or '- (none specified)'}

## Verify Command
{verify or 'pytest tests/ -v'}

## Rules
- Do NOT touch forbidden files
- Run verify command after changes
- Commit with descriptive message
"""
    return contract


def execute_task_local(task_id: str) -> bool:
    """Execute a task locally on the server (for server-side executors)."""
    tasks = query("SELECT * FROM cortex_tasks WHERE id = ?", (task_id,))
    if not tasks:
        return False

    task = dict(tasks[0])
    agent = task.get("executor_agent", "")
    cmd = EXECUTOR_COMMANDS.get(agent)

    if not cmd:
        logger.warning(f"EXECUTE: no command for agent {agent}")
        return False

    contract = build_contract(task)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(contract)
        contract_path = f.name

    diary_path = f"/home/hermes/cortex/logs/diary_{task_id}.log"

    try:
        execute("UPDATE cortex_tasks SET status = 'in_progress', phase = 'execute', started_at = ? WHERE id = ?",
                (datetime.datetime.utcnow().isoformat(), task_id))

        result = subprocess.run(
            f"{cmd} \"{contract_path}\"",
            shell=True,
            capture_output=True,
            text=True,
            timeout=1800,
            cwd="/home/hermes",
        )

        with open(diary_path, "w") as diary:
            diary.write(f"exit_code: {result.returncode}\n")
            diary.write(f"stdout:\n{result.stdout}\n")
            diary.write(f"stderr:\n{result.stderr}\n")

        if result.returncode == 0:
            execute(
                "UPDATE cortex_tasks SET status = 'verify', phase = 'verify', diary_path = ? WHERE id = ?",
                (diary_path, task_id),
            )
        else:
            execute(
                "UPDATE cortex_tasks SET status = 'failed', diary_path = ? WHERE id = ?",
                (diary_path, task_id),
            )

        logger.info(f"EXECUTE: {task_id} done, exit={result.returncode}")
        return result.returncode == 0

    except subprocess.TimeoutExpired:
        logger.error(f"EXECUTE: {task_id} timeout")
        execute("UPDATE cortex_tasks SET status = 'failed' WHERE id = ?", (task_id,))
        return False
    except Exception as e:
        logger.error(f"EXECUTE: {task_id} error: {e}")
        return False
    finally:
        try:
            os.unlink(contract_path)
        except Exception:
            pass


def get_tasks_for_execution(limit: int = 5) -> list:
    """Get tasks ready for execution (status=ready, agent assigned)."""
    return query(
        """SELECT * FROM cortex_tasks
           WHERE status = 'ready'
             AND executor_agent IS NOT NULL
             AND executor_agent != ''
           ORDER BY priority DESC
           LIMIT ?""",
        (limit,),
    )
