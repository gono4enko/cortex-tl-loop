"""REVIEW phase: T1 + T2 review pipeline."""
from __future__ import annotations
import logging, json
from cortex.lib.db import execute, query

logger = logging.getLogger(__name__)

CRITICAL_PATHS = ["erp/", "graph/", ".env", "package.json", "ecosystem.config.js"]


def is_complex(task: dict) -> bool:
    """Determine if task needs T2 review."""
    touched = task.get("touched_files", "[]")
    try:
        files = json.loads(touched) if isinstance(touched, str) else touched
    except json.JSONDecodeError:
        files = []

    for f in files:
        for cp in CRITICAL_PATHS:
            if cp in f:
                return True
    return task.get("complexity") == "high"


def review_t1(task_id: str) -> dict:
    """Tier-1 review: 10-point checklist. Returns review dict."""
    execute("UPDATE cortex_tasks SET phase = 'review', status = 'review' WHERE id = ?", (task_id,))

    result = {
        "task_id": task_id,
        "tier": "t1",
        "reviewer_model": "deepseek-v4-flash",
        "passed": True,
        "complexity": "low",
        "checklist": {},
        "notes": "T1 review — automated checklist (placeholder for LLM review)",
    }

    for i in range(10):
        item_id = f"item_{i+1}"
        result["checklist"][item_id] = True

    total = len(result["checklist"])
    passed_count = sum(1 for v in result["checklist"].values() if v)
    if passed_count < total:
        result["passed"] = False

    if is_complex(dict(query("SELECT * FROM cortex_tasks WHERE id = ?", (task_id,))[0])):
        result["complexity"] = "high"

    execute(
        """INSERT INTO reviews (task_id, tier, reviewer_model, passed, complexity, checklist_json, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (task_id, "t1", "deepseek-v4-flash", result["passed"], result["complexity"],
         json.dumps(result["checklist"]), result["notes"]),
    )

    if result["complexity"] == "high":
        logger.info(f"REVIEW: {task_id} complexity=high → triggering T2")
        return review_t2(task_id)

    if result["passed"]:
        execute("UPDATE cortex_tasks SET status = 'merge', phase = 'merge' WHERE id = ?", (task_id,))
    else:
        execute("UPDATE cortex_tasks SET status = 'failed', phase = 'review' WHERE id = ?", (task_id,))

    return result


def review_t2(task_id: str) -> dict:
    """Tier-2 review: architectural analysis."""
    result = {
        "task_id": task_id,
        "tier": "t2",
        "reviewer_model": "Qwen3-235B-A22B",
        "passed": True,
        "complexity": "high",
        "checklist": {},
        "notes": "T2 architectural review (placeholder for LLM deep analysis)",
    }

    execute(
        """INSERT INTO reviews (task_id, tier, reviewer_model, passed, complexity, checklist_json, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (task_id, "t2", "Qwen3-235B-A22B", result["passed"], "high", "{}", result["notes"]),
    )

    if result["passed"]:
        execute("UPDATE cortex_tasks SET status = 'merge', phase = 'merge' WHERE id = ?", (task_id,))
    else:
        execute("UPDATE cortex_tasks SET status = 'blocked', phase = 'review' WHERE id = ?", (task_id,))
    return result
