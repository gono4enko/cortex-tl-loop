"""Unified State Store — TL loop state + shared cortex connection."""
from __future__ import annotations
import uuid, json, logging, time, sqlite3, threading
from datetime import datetime, timezone
from pathlib import Path
from cortex.tl_loop.schema import Task, TaskStatus, ALLOWED_TRANSITIONS

logger = logging.getLogger(__name__)

STATE_DB = Path("/home/hermes/cortex/tl_loop_state.db")
_local = threading.local()
_cortex_conn = None

def _state_db():
    if not hasattr(_local, "conn"):
        conn = sqlite3.connect(str(STATE_DB))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        _local.conn = conn
    return _local.conn

def _cortex_db():
    global _cortex_conn
    if _cortex_conn is None:
        _cortex_conn = sqlite3.connect("/home/hermes/cortex/cortex.db", timeout=30)
        _cortex_conn.row_factory = sqlite3.Row
        _cortex_conn.execute("PRAGMA journal_mode=WAL")
        _cortex_conn.execute("PRAGMA busy_timeout=30000")
    return _cortex_conn

def now(): return datetime.now(timezone.utc).isoformat()

def log_event(task_id: str, etype: str, payload: dict = None):
    eid = uuid.uuid4().hex[:12]
    db = _state_db()
    db.execute("INSERT INTO events (id, task_id, type, payload, ts) VALUES (?,?,?,?,?)",
        (eid, task_id, etype, json.dumps(payload or {}, ensure_ascii=False), now()))
    db.commit()

def transition(task_id: str, new_status: TaskStatus) -> bool:
    cdb = _cortex_db()
    try:
        row = cdb.execute("SELECT status FROM cortex_tasks WHERE id = ?", (task_id,)).fetchone()
        if not row: return False
        current = TaskStatus(row[0])
        if new_status not in ALLOWED_TRANSITIONS.get(current, []):
            return False
        cdb.execute("UPDATE cortex_tasks SET status = ?, updated_at = ? WHERE id = ?",
                (new_status.value, now(), task_id))
        cdb.commit()
        log_event(task_id, "status_changed", {"from": current.value, "to": new_status.value})
        return True
    except Exception as e:
        logger.warning(f"Transition failed: {e}")
        try: cdb.rollback()
        except: pass
        return False

def get_pending_tasks(limit: int = 20) -> list[Task]:
    try:
        cdb = _cortex_db()
        rows = cdb.execute(
            "SELECT * FROM cortex_tasks WHERE status IN ('new','planning','ready','retry') ORDER BY priority DESC LIMIT ?",
            (limit,)).fetchall()
        return [_row(r) for r in rows]
    except Exception as e:
        logger.warning(f"get_pending_tasks: {e}")
        return []

def get_stuck_tasks(minutes: int = 15) -> list[Task]:
    try:
        cdb = _cortex_db()
        rows = cdb.execute(
            f"SELECT * FROM cortex_tasks WHERE (status IN ('dispatched','running') AND updated_at < datetime('now', '-{minutes} minutes')) OR status = 'stuck' ORDER BY priority DESC LIMIT 20"
        ).fetchall()
        return [_row(r) for r in rows]
    except Exception as e:
        logger.warning(f"get_stuck_tasks: {e}")
        return []

def get_verify_ready() -> list[Task]:
    try:
        cdb = _cortex_db()
        rows = cdb.execute("SELECT * FROM cortex_tasks WHERE status = 'verifying' ORDER BY priority DESC LIMIT 10").fetchall()
        return [_row(r) for r in rows]
    except Exception:
        return []

def get_agents_online() -> list[str]:
    try:
        cdb = _cortex_db()
        rows = cdb.execute(
            "SELECT agent FROM heartbeats WHERE status = 'alive' AND datetime(last_seen) > datetime('now', '-3 minutes')"
        ).fetchall()
        return [r["agent"] for r in rows]
    except Exception:
        return []

def assign_agent(task_id: str, agent: str) -> bool:
    try:
        cdb = _cortex_db()
        cdb.execute("UPDATE cortex_tasks SET executor_agent = ?, status = 'dispatched' WHERE id = ?", (agent, task_id))
        cdb.commit()
        return True
    except: return False

def mark_done(task_id: str):
    try:
        cdb = _cortex_db()
        cdb.execute("UPDATE cortex_tasks SET status = 'done', completed_at = ?, phase = 'kb-write' WHERE id = ?", (now(), task_id))
        cdb.commit()
        log_event(task_id, "kb_written")
    except: pass

def log_tick(tasks: int, decisions: int, rules: int, errors: int):
    try:
        db = _state_db()
        db.execute("INSERT INTO tick_log (ts, tasks_seen, decisions, rules, errors) VALUES (?,?,?,?,?)",
            (now(), tasks, decisions, rules, errors))
        db.commit()
    except: pass

def get_tick_count() -> int:
    try:
        row = _state_db().execute("SELECT COUNT(*) FROM tick_log").fetchone()
        return row[0] if row else 0
    except: return 0

def bootstrap_db():
    db = _state_db()
    db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, task_id TEXT, type TEXT, payload TEXT, ts TEXT)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_ev_task ON events(task_id)")
    db.execute("CREATE TABLE IF NOT EXISTS tick_log (ts TEXT, tasks_seen INT, decisions INT, rules INT, errors INT)")
    db.commit()
    logger.info("TL State Store ready")

def _row(r) -> Task:
    d = dict(r)
    touched = d.get("touched_files","[]")
    if isinstance(touched, str):
        try: touched = json.loads(touched)
        except: touched = []
    return Task(id=d.get("id",""), title=d.get("title",""), body=d.get("body","") or "",
        project_id=d.get("project_id","") or "", status=TaskStatus(d.get("status","new")),
        priority=d.get("priority",3) or 3, agent=d.get("executor_agent","") or "",
        touched_files=touched, verify_cmd=d.get("verify_command","") or "",
        cost_usd=d.get("cost_estimate",0) or 0)
