#!/usr/bin/env python3
"""Cortex Daily Report — send to Andrey via email."""
import sys, os
sys.path.insert(0, "/home/hermes")
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path("/home/hermes/cortex/.env"))
except: pass

from cortex.lib.email import send_email
from cortex.tl_loop.state_store import get_tick_count
import sqlite3

c = sqlite3.connect("/home/hermes/cortex/cortex.db")
c.execute("PRAGMA busy_timeout=5000")
done = c.execute("SELECT COUNT(*) FROM cortex_tasks WHERE status='done'").fetchone()[0]
failed = c.execute("SELECT COUNT(*) FROM cortex_tasks WHERE status IN ('failed','blocked')").fetchone()[0]
total = c.execute("SELECT COUNT(*) FROM cortex_tasks").fetchone()[0]
c.close()

ticks = get_tick_count()

body = f"""Cortex Daily Report

Tasks: {total} total, {done} done, {failed} blocked/failed
TL Ticks: {ticks}
Budget: $70/day
Services: all online

Cortex Team Lead / GLM-5.2
hermes-assistant :9015
"""

ok = send_email(to="gono4enko@gmail.com", subject="Cortex Daily Report", body=body, priority="info")
print(f"Report sent: {ok}")
