#!/usr/bin/env python3
"""Hermes Cortex — Full 8-phase orchestrator v1.0. Team Lead: GLM-5.2."""
from __future__ import annotations
import os, sys, signal, asyncio, logging
from pathlib import Path

sys.path.insert(0, "/home/hermes")

from dotenv import load_dotenv
load_dotenv(Path("/home/hermes/cortex/.env"))

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from cortex.lib.db import init_db, get_db
from cortex.lib.availability import heartbeat, mark_stale
from cortex.phases.ingest import create_task as ingest_create_task, get_pending_tasks
from cortex.phases.dispatch import assign_executor, create_assignment, get_available_agents
from cortex.phases.plan import plan_task
from cortex.phases.execute import execute_task_local, get_tasks_for_execution
from cortex.phases.verify import verify_task
from cortex.security.config_safety import pre_task_check
from cortex.lib.email import send_email, imap_poll_loop, notify_andrey

def _check_auth(request):
    expected = os.environ.get("CORTEX_API_TOKEN", "")
    token = request.headers.get("X-Cortex-Token", request.headers.get("Authorization", "")).replace("Bearer ", "")
    return token == expected if expected else True
from cortex.phases.review import review_t1
from cortex.phases.merge import merge_task
from cortex.phases.kb_write import kb_write_task
from cortex.adapters.agent_loop_adapter import is_agent_loop_busy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [cortex] %(levelname)s: %(message)s")
logger = logging.getLogger("cortex")

app = FastAPI(title="Hermes Cortex", version="1.0.0-wave8")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_shutdown_event = asyncio.Event()


class TaskRequest(BaseModel):
    title: str
    body: str = ""
    project_id: str = ""
    priority: int = 3


# ── Health ──
@app.get("/health")
async def health():
    try:
        get_db().execute("SELECT 1")
        return {"status":"ok","service":"hermes-cortex","version":"1.0.0","team_lead":"GLM-5.2"}
    except:
        return {"status":"degraded"}


# ── Status ──
@app.get("/status")
async def status():
    db = get_db()
    tasks_total = db.execute("SELECT COUNT(*) FROM cortex_tasks").fetchone()[0]
    tasks_active = db.execute("SELECT COUNT(*) FROM cortex_tasks WHERE status NOT IN ('done','failed','blocked')").fetchone()[0]
    phases = {}
    for r in db.execute("SELECT phase, COUNT(*) FROM cortex_tasks GROUP BY phase").fetchall():
        phases[r[0]] = r[1]
    return {"tasks":{"total":tasks_total,"active":tasks_active},"phases":phases,"agent_loop":"busy" if is_agent_loop_busy() else "idle"}


# ── INGEST ──
@app.post("/task")
async def create_task(req: TaskRequest):
    tid = ingest_create_task(req.title, req.body, req.project_id, req.priority)
    gate = pre_task_check(body=req.body)
    status = "ingest"
    if gate.get("touches_configs") and gate.get("severity") == "ERROR":
        from cortex.lib.db import execute as _ex
        import json as _js
        status = "blocked"
        _ex("UPDATE cortex_tasks SET status='blocked', notes=? WHERE id=?", (_js.dumps(gate, ensure_ascii=False), tid))
    return {"task_id": tid, "status": "ingest"}


# ── DISPATCH ──
@app.post("/task/{task_id}/dispatch")
async def dispatch(task_id: str):
    from cortex.lib.db import query
    t = query("SELECT * FROM cortex_tasks WHERE id = ?", (task_id,))
    if not t: return {"error":"not found"}, 404
    agent = assign_executor(task_id, dict(t[0]).get("complexity","med"))
    if agent:
        create_assignment(task_id, agent)
        return {"task_id":task_id,"agent":agent,"status":"dispatched"}
    return {"task_id":task_id,"status":"pending"}


# ── PLAN ──
@app.post("/plan")
async def plan(task_id: str = None):
    if not task_id: return {"error":"task_id required"}
    result = await plan_task(task_id)
    return {"task_id":task_id,"plan":"created" if result else "failed"}


# ── EXECUTE ──
@app.post("/execute")
async def execute(task_id: str = None):
    if not task_id: return {"error":"task_id required"}
    return {"task_id":task_id,"executed":execute_task_local(task_id)}


# ── VERIFY ──
@app.post("/verify")
async def verify(task_id: str = None):
    if not task_id: return {"error":"task_id required"}
    passed, output = verify_task(task_id)
    return {"task_id":task_id,"passed":passed,"output":output[:500]}


# ── REVIEW ──
@app.post("/review")
async def review(task_id: str = None):
    if not task_id: return {"error":"task_id required"}
    result = review_t1(task_id)
    return result


# ── MERGE ──
@app.post("/merge")
async def merge(task_id: str = None):
    if not task_id: return {"error":"task_id required"}
    return {"task_id":task_id,"merged":merge_task(task_id)}


# ── KB-WRITE ──
@app.post("/kb-write")
async def kb_write(task_id: str = None):
    if not task_id: return {"error":"task_id required"}
    result = kb_write_task(task_id)
    return result


# ── Full Pipeline ──
@app.post("/pipeline")
async def full_pipeline(task_id: str = None):
    """Run full 8-phase pipeline for a task."""
    if not task_id: return {"error":"task_id required"}
    log = []
    
    # 1. INGEST (task already exists)
    log.append({"phase":"ingest","ok":True})
    
    # 2. PLAN
    plan_result = await plan_task(task_id)
    log.append({"phase":"plan","ok":plan_result is not None})
    
    # 3. DISPATCH (for each sub-task)
    from cortex.lib.db import query
    for t in query("SELECT id FROM cortex_tasks WHERE wave_id = (SELECT wave_id FROM cortex_tasks WHERE id = ?)", (task_id,)):
        agent = assign_executor(t[0], "med")
        if agent:
            create_assignment(t[0], agent)
            log.append({"phase":"dispatch","task":t[0],"agent":agent})
    
    # 4. EXECUTE (server-side tasks)
    for t in get_tasks_for_execution(limit=5):
        t_dict = dict(t)
        if t_dict.get("executor_agent") in ("kilo-hermes","hermes-opencode","hermes-bot"):
            ok = execute_task_local(t_dict["id"])
            log.append({"phase":"execute","task":t_dict["id"],"ok":ok})
    
    # 5. VERIFY
    passed, output = verify_task(task_id)
    log.append({"phase":"verify","passed":passed})
    
    # 6. REVIEW
    if passed:
        review_result = review_t1(task_id)
        log.append({"phase":"review","passed":review_result["passed"],"complexity":review_result["complexity"]})
    
    # 7. MERGE
    merged = merge_task(task_id)
    log.append({"phase":"merge","ok":merged})
    
    # 8. KB-WRITE
    kb_result = kb_write_task(task_id)
    log.append({"phase":"kb-write","ok":"error" not in kb_result})
    
    return {"task_id":task_id,"pipeline":log}


# ── Agents / Heartbeat ──
@app.post("/heartbeat/{agent}")
async def agent_hb(agent: str, request: Request):
    body = {}
    try: body = await request.json()
    except: pass
    heartbeat(agent, body.get("status","alive"), body.get("current_task_id"))
    return {"ok":True}

@app.post("/task/{task_id}/config-check")
async def config_check(task_id: str):
    from cortex.lib.db import query as _q, execute as _ex
    import json as _js
    row = _q("SELECT body FROM cortex_tasks WHERE id = ?", (task_id,))
    if not row:
        return {"error": "not found"}
    body = row[0]["body"] if row[0] else ""
    gate = pre_task_check(body=body)
    if gate.get("severity") == "ERROR":
        _ex("UPDATE cortex_tasks SET status='blocked', notes=? WHERE id=?", (_js.dumps(gate, ensure_ascii=False), task_id))
        return {"task_id": task_id, "verdict": "blocked", "gate": gate}
    return {"task_id": task_id, "verdict": "pass", "gate": gate}


@app.post("/notify")
async def notify(req: Request):
    if not _check_auth(req):
        return {"error": "unauthorized"}
    body = await req.json()
    ok = send_email(to=body.get("to"), subject=body.get("subject",""), body=body.get("body",""), priority=body.get("priority","info"))
    return {"ok": ok, "to": body.get("to")}

@app.post("/notify/urgent")
async def notify_urgent(req: Request):
    if not _check_auth(req):
        return {"error": "unauthorized"}
    body = await req.json()
    ok = notify_andrey(body.get("subject",""), body.get("body",""), body.get("priority","info"), also_telegram=True)
    return {"ok": ok}

@app.get("/inbox")
async def inbox(limit: int = 20):
    from cortex.lib.db import query as _q
    rows = _q("SELECT * FROM inbox_messages ORDER BY received_at DESC LIMIT ?", (limit,))
    return {"inbox": [dict(r) for r in rows]}

@app.post("/task/{task_id}/approve")
async def approve_task(task_id: str):
    from cortex.lib.db import query as _q, execute as _ex
    import json as _js
    rows = _q("SELECT * FROM cortex_tasks WHERE id = ?", (task_id,))
    if not rows:
        return {"error": "not found"}
    _ex("UPDATE cortex_tasks SET status='ready', notes=COALESCE(notes,'')||' [approved]' WHERE id=?", (task_id,))
    _ex("INSERT INTO audit (actor, action, target, ts) VALUES (?, 'approve', ?, datetime('now'))", ("andrey", task_id))
    return {"task_id": task_id, "status": "approved"}

@app.get("/agents")

async def agents():
    return {"agents":get_available_agents()}

@app.get("/tasks")
async def tasks_list(status: str = None, limit: int = 50):
    from cortex.lib.db import query
    sql = "SELECT * FROM cortex_tasks"
    params = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY priority DESC, created_at DESC LIMIT ?"
    params.append(limit)
    return {"tasks":[dict(r) for r in query(sql, tuple(params))]}


# ── Loops ──
@app.on_event("startup")
async def startup():
    logger.info("Cortex v1.0 — GLM-5.2 Team Lead — 8 phases + email/TG")
    init_db()
    try:
        db = get_db()
        db.execute("CREATE TABLE IF NOT EXISTS inbox_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id TEXT, sender TEXT, subject TEXT, body TEXT, received_at TEXT, read_at TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT, target TEXT, details TEXT, ts TEXT)")
        db.commit()
    except: pass
    if os.environ.get("CORTEX_IMAP_ENABLED") == "1":
        asyncio.create_task(imap_poll_loop(int(os.environ.get("IMAP_POLL_INTERVAL","300"))))
    asyncio.create_task(run_loops())


async def run_loops():
    while not _shutdown_event.is_set():
        try:
            heartbeat("cortex-orchestrator","alive")
            mark_stale(120)
        except: pass
        await asyncio.sleep(60)


def main():
    loop = asyncio.get_event_loop()
    async def serve():
        config = uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("CORTEX_PORT",9015)), log_level="info")
        await uvicorn.Server(config).serve()
    
    run_handle = asyncio.ensure_future(serve())
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s,f: _shutdown_event.set())
    
    try:
        loop.run_until_complete(run_handle)
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
