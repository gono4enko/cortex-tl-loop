"""TL Orchestration Loop — Wave 2: council + review pipeline."""
from __future__ import annotations
import asyncio, logging, os, time, subprocess, json
from cortex.tl_loop.schema import TaskStatus, TickResult
from cortex.tl_loop.state_store import (
    bootstrap_db, get_pending_tasks, get_stuck_tasks, get_verify_ready,
    get_agents_online, transition, log_event, mark_done,
    log_tick, get_tick_count, assign_agent,
)
from cortex.tl_loop.rules import apply_rules, kill_switch
from cortex.tl_loop.verify_gate import run_verify
from cortex.tl_loop.reviewer import review_pipeline
from cortex.tl_loop.council import convene, should_convene
from cortex.tl_loop.reporter import daily_telegram
import chromadb
from chromadb.config import Settings

logger = logging.getLogger("tl_loop")
LAST_DAILY = 0


def git_merge(task):
    """Real git merge + push for completed task."""
    project_dir = "/home/hermes"
    if task.project_id:
        pdir = f"/home/hermes/{task.project_id}"
        if os.path.isdir(f"{pdir}/.git"):
            project_dir = pdir
    try:
        branch = task.branch or f"cortex/{task.id[:12]}"
        subprocess.run(["git", "add", "-A"], cwd=project_dir, capture_output=True, timeout=15)
        subprocess.run(
            ["git", "commit", "-m", f"cortex: {task.title[:80]}"],
            cwd=project_dir, capture_output=True, timeout=15,
        )
        subprocess.run(["git", "push", "origin", "HEAD"], cwd=project_dir, capture_output=True, timeout=30)
        logger.info(f"Merge: {task.id[:20]} pushed")
        return True, "pushed"
    except Exception as e:
        logger.warning(f"Merge: {task.id[:20]} failed: {e}")
        return False, str(e)[:100]


def kb_write(task):
    """Write task result to Obsidian KB + ChromaDB index."""
    content = f"# {task.title}\n- Status: done\n- Files: {', '.join(task.touched_files) if task.touched_files else 'none'}\n- ID: {task.id}"
    try:
        kb_dir = f"/home/hermes/obsidian-kb/06-ai-context/cortex/tasks/{task.project_id or 'general'}"
        os.makedirs(kb_dir, exist_ok=True)
        with open(f"{kb_dir}/{task.id}.md", "w") as f:
            f.write(content)
        logger.info(f"KB: {task.id[:20]} written")
    except Exception as e:
        logger.warning(f"KB write failed: {e}")

    # ChromaDB re-index  # ponytail: in-process, upgrade to bg thread if slow
    try:
        client = chromadb.PersistentClient(
            path="/home/hermes/.chroma_cortex", settings=Settings(anonymized_telemetry=False))
        coll = client.get_or_create_collection("cortex_tasks")
        coll.add(documents=[content], ids=[task.id],
                 metadatas=[{"title": task.title, "project": task.project_id or "general"}])
        logger.info(f"Chroma: {task.id[:20]} indexed")
    except Exception as e:
        logger.warning(f"Chroma index failed: {e}")


async def tick() -> TickResult:
    global LAST_DAILY
    result = TickResult()
    try:
        ks = kill_switch()
        if ks.matched:
            logger.error(f"KILL SWITCH: {ks.reason}")
            log_event("SYSTEM", "error", {"kill_switch": ks.reason})
            return result

        agents = get_agents_online()
        if "cortex-orchestrator" in agents:
            agents.remove("cortex-orchestrator")

        # 1. New/ready/retry -> dispatch
        for task in get_pending_tasks(20):
            result.tasks_seen += 1
            rule = apply_rules(task, agents)
            if rule.matched:
                result.rules_fired += 1
                result.decisions_made += 1

        # 2. Stuck -> council + recovery
        for task in get_stuck_tasks(5):
            result.tasks_seen += 1
            transition(task.id, TaskStatus.STUCK)
            # Expert council for stuck tasks
            convene_ok, convene_reason = should_convene(task)
            if convene_ok:
                logger.warning(f"Council: triggering for {task.id[:20]} ({convene_reason})")
                decision = convene(task, convene_reason)
                log_event(task.id, "council_decision", decision)
                if decision.get("verdict") == "retry":
                    transition(task.id, TaskStatus.RETRY)
                elif decision.get("verdict") == "rework":
                    transition(task.id, TaskStatus.RETRY)
                elif decision.get("verdict") == "abandon":
                    transition(task.id, TaskStatus.DONE)
                    mark_done(task.id)
                else:
                    transition(task.id, TaskStatus.BLOCKED)
                result.decisions_made += 1
            else:
                rule = apply_rules(task, agents)
                if rule.matched:
                    result.rules_fired += 1

        # 3. AUTO-CHAIN: verify -> review -> merge -> done
        for task in get_verify_ready():
            passed, output = run_verify(task)
            if passed:
                logger.info(f"Verify PASS: {task.id[:20]}")
                review = review_pipeline(task)
                if review.get("ready_for_merge"):
                    transition(task.id, TaskStatus.MERGING)
                    git_ok, git_msg = git_merge(task)
                    if git_ok:
                        transition(task.id, TaskStatus.DONE)
                        mark_done(task.id)
                        kb_write(task)
                        logger.info(f"Chain DONE: {task.id[:20]}")
                    else:
                        transition(task.id, TaskStatus.FAILED)
                        logger.error(f"Merge FAIL: {task.id[:20]}: {git_msg}")
                else:
                    logger.warning(f"Review FAIL: {task.id[:20]}")
                result.decisions_made += 1
            else:
                logger.warning(f"Verify FAIL: {task.id[:20]}")
                # Council for persistent verify failures
                if task.attempt >= 3:
                    decision = convene(task, f"verify failed {task.attempt} times")
                    log_event(task.id, "council_decision", decision)

        # 4. Daily report
        now = time.time()
        if now - LAST_DAILY > 86400:
            try:
                await daily_telegram(0, len(get_pending_tasks(100)), get_tick_count())
            except Exception:
                pass
            LAST_DAILY = now

    except Exception as e:
        result.errors += 1
        logger.exception(f"Tick error: {e}")

    log_tick(result.tasks_seen, result.decisions_made, result.rules_fired, result.errors)
    return result


async def run_forever(interval: int = 300):
    bootstrap_db()
    logger.info(f"TL Loop v3 Wave2 started (interval={interval}s, tick #{get_tick_count()+1})")
    while True:
        try:
            await tick()
        except Exception as e:
            logger.exception("Loop error")
        await asyncio.sleep(interval)
