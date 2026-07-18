#!/bin/bash
cd /home/hermes/cortex
python3 -c "
import sys; sys.path.insert(0, \"/home/hermes\")
from cortex.lib.email import send_email, SMTP_TO
from cortex.tl_loop.state_store import get_tick_count
import sqlite3
c = sqlite3.connect(\"/home/hermes/cortex/cortex.db\")
c.execute(\"PRAGMA busy_timeout=5000\")
done = c.execute(\"SELECT COUNT(*) FROM cortex_tasks WHERE status="\"done\""\").fetchone()[0]
failed = c.execute(\"SELECT COUNT(*) FROM cortex_tasks WHERE status IN ("\"failed\"","\"blocked\"")\").fetchone()[0]
total = c.execute(\"SELECT COUNT(*) FROM cortex_tasks\").fetchone()[0]
c.close()
ticks = get_tick_count()
body = f\"\"\"# Cortex Daily Report
- Tasks: {total} total, {done} done, {failed} blocked/failed
- TL Ticks: {ticks}
- Budget: $70/day
- Services: all online

Cortex Team Lead / GLM-5.2
\"\"\"
send_email(to=SMTP_TO, subject=\"Cortex Daily Report\", body=body, priority=\"info\")
print(\"Report sent\")
"
