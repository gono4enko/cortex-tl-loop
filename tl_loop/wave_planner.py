"""Wave DAG Planner — parallel task group validation."""
from __future__ import annotations
import yaml, logging
from collections import defaultdict

logger = logging.getLogger("wave_planner")

def validate_wave_plan(plan: dict) -> tuple[bool, str]:
    """Validate wave plan: no file conflicts within same wave."""
    if not plan or "waves" not in plan:
        return False, "missing 'waves' key"

    for wave_name, tasks in plan["waves"].items():
        # Collect all touched files in this wave
        file_to_tasks = defaultdict(list)
        for task in tasks:
            for f in task.get("touched_files", []):
                file_to_tasks[f].append(task.get("name", "unnamed"))

        # Check for conflicts
        conflicts = {f: tlist for f, tlist in file_to_tasks.items() if len(tlist) > 1}
        if conflicts:
            conflict_str = "; ".join(f"{f}: {', '.join(ts)}" for f, ts in conflicts.items())
            return False, f"wave '{wave_name}': file conflicts — {conflict_str}"

    return True, "ok"


def get_wave_order(plan: dict) -> list[str]:
    """Return ordered list of wave names."""
    if not plan:
        return []
    return list(plan.get("waves", {}).keys())


def get_tasks_in_wave(plan: dict, wave_name: str) -> list[dict]:
    """Get tasks in a specific wave."""
    if not plan:
        return []
    return plan.get("waves", {}).get(wave_name, [])
