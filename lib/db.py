"""SQLite WAL database connection for Cortex."""
import sqlite3
import os
import threading
from pathlib import Path

_db_path = os.environ.get("CORTEX_DB_PATH", "/home/hermes/cortex/cortex.db")
_local = threading.local()


def get_db() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        Path(_db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(_db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


def init_db():
    """Run schema.sql to create tables if not exist."""
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    if not schema_path.exists():
        return
    conn = get_db()
    schema = schema_path.read_text()
    conn.executescript(schema)
    conn.commit()


def query(sql: str, params: tuple = ()):
    conn = get_db()
    return conn.execute(sql, params).fetchall()


def execute(sql: str, params: tuple = ()):
    conn = get_db()
    conn.execute(sql, params)
    conn.commit()


def execute_many(sql: str, params_list: list):
    conn = get_db()
    conn.executemany(sql, params_list)
    conn.commit()
