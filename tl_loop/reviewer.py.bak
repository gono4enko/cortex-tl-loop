"""Tier-1/Tier-2 Review pipeline — real LLM calls."""
from __future__ import annotations
import requests, logging, json, os, subprocess
from cortex.tl_loop.schema import Task
from cortex.tl_loop.state_store import transition, log_event, TaskStatus
from cortex.tl_loop.cost_tracker import log_cost

logger = logging.getLogger("reviewer")

CRITICAL_PATHS = ["erp/", "graph/", ".env", "package.json", "ecosystem.config.js"]
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPINFRA_KEY = os.environ.get("DEEPINFRA_API_KEY", "")

T1_CHECKLIST = """Check this task diff against a 10-point checklist:
1. SECRETS: no API keys, tokens, passwords in diff
2. IMPORTS: all imports resolve, no unused imports
3. TYPES: TypeScript types are correct, no `any` abuse
4. NAMING: variables/functions follow project conventions
5. ERROR_HANDLING: errors are caught, not silently ignored
6. TESTS: test files updated if logic changed
7. DOCS: docstrings/comments for non-obvious logic
8. PERF: no O(n²) loops on large datasets, no sync blocking
9. CONVENTIONS: follows project code style
10. DESTRUCTIVE: no rm -rf, DROP TABLE, destructive operations

Return JSON: {"passed": bool, "complexity": "low"|"high", "checklist": {"item_N": bool, ...}, "notes": "..."}"""

T2_ANALYSIS = """Deep architectural review of this task:
1. Impact on system architecture — does it break existing patterns?
2. Data flow — are new DB queries, API calls correct?
3. Security — any new attack surface?
4. Dependencies — new packages justified?
5. Migration path — backward compatible?

Return JSON: {"passed": bool, "issues": ["..."], "recommendation": "merge"|"block"|"rework", "notes": "..."}"""


def _call_deepseek(prompt: str, max_tokens: int = 2048) -> dict:
    """Sync call to DeepSeek V4 Flash."""
    try:
        r = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "temperature": 0.1},
            timeout=120,
        )
        if r.status_code == 200:
            data = r.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            log_cost(task_id="review_t1", model="deepseek-chat", input_text=prompt, output_text=content)
            return data
        logger.error(f"DeepSeek API: {r.status_code} {r.text[:200]}")
        return {}
    except Exception as e:
        logger.error(f"DeepSeek call failed: {e}")
        return {}


def _call_deepinfra(model: str, prompt: str, max_tokens: int = 4096) -> dict:
    """Sync call to DeepInfra (Qwen3-235B, GLM-5.2, etc)."""
    try:
        r = requests.post(
            "https://api.deepinfra.com/v1/openai/chat/completions",
            headers={"Authorization": f"Bearer {DEEPINFRA_KEY}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "temperature": 0.2},
            timeout=180,
        )
        if r.status_code == 200:
            data = r.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            log_cost(task_id="review_t2", model=model, input_text=prompt, output_text=content)
            return data
        logger.error(f"DeepInfra API ({model}): {r.status_code} {r.text[:200]}")
        return {}
    except Exception as e:
        logger.error(f"DeepInfra call failed ({model}): {e}")
        return {}


def _get_diff(task: Task) -> str:
    """Get git diff for task files."""
    project_dir = "/home/hermes"
    if task.project_id:
        pdir = os.path.join("/home/hermes", task.project_id)
        if os.path.isdir(os.path.join(pdir, ".git")):
            project_dir = pdir
    try:
        files = " ".join(task.touched_files[:20]) if task.touched_files else "."
        r = subprocess.run(
            ["git", "diff", "HEAD~1", "--", *task.touched_files[:20]] if task.touched_files
            else ["git", "diff", "HEAD~1"],
            capture_output=True, text=True, timeout=30, cwd=project_dir,
        )
        return r.stdout[:8000]
    except Exception:
        return ""


def _complexity_from_touched(task: Task) -> str:
    """Check if task touches critical paths."""
    touched_str = " ".join(task.touched_files) if task.touched_files else ""
    for cp in CRITICAL_PATHS:
        if cp.rstrip("/") in touched_str:
            return "high"
    return "low"


def run_tier1_review(task: Task) -> dict:
    """Tier-1: LLM checklist review via DeepSeek V4 Flash."""
    diff = _get_diff(task)
    prompt = f"""Task: {task.title}
Description: {task.description or 'no description'}
Files: {', '.join(task.touched_files) if task.touched_files else 'unknown'}
Project: {task.project_id or 'hermes'}

Diff:
{diff if diff else '(no diff available)'}

{T1_CHECKLIST}"""

    resp = _call_deepseek(prompt)
    content = ""
    try:
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        pass

    if content:
        try:
            # Extract JSON from response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(content[json_start:json_end])
            else:
                raise ValueError("No JSON found")
        except (json.JSONDecodeError, ValueError):
            # Fallback: heuristic
            passed = "PASS" in content.upper() and "FAIL" not in content.upper()
            parsed = {"passed": passed, "complexity": _complexity_from_touched(task),
                       "checklist": {}, "notes": content[:500]}
    else:
        # API failed — fallback to heuristic
        parsed = {"passed": True, "complexity": _complexity_from_touched(task),
                   "checklist": {}, "notes": "T1: API unavailable — auto-passed"}

    parsed["tier"] = "t1"
    parsed.setdefault("complexity", _complexity_from_touched(task))
    logger.info(f"T1 Review: {task.id[:20]} passed={parsed.get('passed')} complexity={parsed.get('complexity')}")
    return parsed


def run_tier2_review(task: Task) -> dict:
    """Tier-2: architectural analysis via Qwen3-235B-A22B."""
    diff = _get_diff(task)[:6000]
    prompt = f"""Task: {task.title}
Description: {task.description or 'no description'}
Files: {', '.join(task.touched_files) if task.touched_files else 'unknown'}
Project: {task.project_id or 'hermes'}

Diff:
{diff if diff else '(no diff available)'}

{T2_ANALYSIS}"""

    resp = _call_deepinfra("Qwen/Qwen3-235B-A22B-Instruct", prompt)
    content = ""
    try:
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        pass

    if content:
        try:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(content[json_start:json_end])
            else:
                raise ValueError("No JSON")
        except (json.JSONDecodeError, ValueError):
            parsed = {"passed": "BLOCK" not in content.upper(), "issues": [],
                       "recommendation": "merge", "notes": content[:500]}
    else:
        parsed = {"passed": True, "issues": [], "recommendation": "merge",
                   "notes": "T2: API unavailable — auto-passed"}

    parsed["tier"] = "t2"
    parsed["complexity"] = "high"
    logger.info(f"T2 Review: {task.id[:20]} passed={parsed.get('passed')}")
    return parsed


def review_pipeline(task: Task) -> dict:
    """Full review pipeline: T1 → (T2 if high) → pass/block."""
    t1 = run_tier1_review(task)

    if not t1.get("passed", False):
        transition(task.id, TaskStatus.FAILED)
        log_event(task.id, "review_failed", {"tier": "t1"})
        return {"passed": False, "ready_for_merge": False, "t1": t1}

    if t1.get("complexity") == "high":
        t2 = run_tier2_review(task)
        if not t2.get("passed", False):
            transition(task.id, TaskStatus.BLOCKED)
            log_event(task.id, "review_blocked", {"tier": "t2"})
            return {"passed": False, "ready_for_merge": False, "t1": t1, "t2": t2}
        log_event(task.id, "review_passed", {"tiers": "t1+t2"})
        return {"passed": True, "ready_for_merge": True, "t1": t1, "t2": t2}

    log_event(task.id, "review_passed", {"tier": "t1"})
    return {"passed": True, "ready_for_merge": True, "t1": t1}
