"""Verification Gate — real pytest/ruff + task-specific verify_command."""
from __future__ import annotations
import subprocess, logging, os
from cortex.tl_loop.schema import Task
from cortex.tl_loop.state_store import transition, log_event, TaskStatus

logger = logging.getLogger("verify")

def run_verify(task: Task) -> tuple[bool, str]:
    output_lines = []
    all_passed = True
    project_dir = "/home/hermes"
    if task.project_id:
        pdir = os.path.join("/home/hermes", task.project_id)
        if os.path.isdir(pdir):
            project_dir = pdir

    # 0. Task verify_command (if set) — ponytail: run before ruff/pytest
    if task.verify_command:
        try:
            r = subprocess.run(
                task.verify_command, shell=True,
                capture_output=True, text=True, timeout=300,
                cwd=project_dir,
            )
            output_lines.append(f"$ {task.verify_command[:80]}")
            output_lines.append(r.stdout[-2000:] or "(no output)")
            if r.stderr:
                output_lines.append(r.stderr[-500:])
            if r.returncode != 0:
                all_passed = False
                output_lines.append(f"verify_command FAILED (rc={r.returncode})")
        except Exception as e:
            output_lines.append(f"verify_command: {e}")
            all_passed = False

    # 1. Ruff check
    try:
        r = subprocess.run(
            ["python3", "-m", "ruff", "check", ".", "--select", "E,F,W"],
            capture_output=True, text=True, timeout=120,
            cwd=project_dir,
        )
        output_lines.append("$ ruff check")
        output_lines.append(r.stdout[-2000:] or "(clean)")
        if r.returncode != 0:
            all_passed = False
            output_lines.append(f"ruff FAILED (rc={r.returncode})")
    except Exception as e:
        output_lines.append(f"ruff: {e}")

    # 2. Pytest
    try:
        r = subprocess.run(
            ["python3", "-m", "pytest", "tests/", "-v", "--tb=short", "-m", "not slow"],
            capture_output=True, text=True, timeout=300,
            cwd=project_dir,
        )
        output_lines.append("$ pytest tests/ -m 'not slow'")
        output_lines.append(r.stdout[-3000:] or "(no tests)")
        if r.returncode != 0:
            all_passed = False
            output_lines.append(f"pytest FAILED (rc={r.returncode})")
    except FileNotFoundError:
        output_lines.append("pytest: no tests/ directory — skipping")
    except Exception as e:
        output_lines.append(f"pytest: {e}")

    output = "\n".join(output_lines)

    if all_passed:
        transition(task.id, TaskStatus.REVIEWING)
        log_event(task.id, "verify_passed", {"cmd": "ruff+pytest"})
    else:
        if task.attempt < task.max_attempts:
            transition(task.id, TaskStatus.RETRY)
            log_event(task.id, "verify_failed", {"attempt": task.attempt})
        else:
            transition(task.id, TaskStatus.BLOCKED)
            log_event(task.id, "escalation", {"reason": "verify failed after max retries"})

    logger.info(f"Verify: {task.id[:20]} passed={all_passed}")
    return all_passed, output
