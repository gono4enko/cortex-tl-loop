#!/usr/bin/env python3
"""Cortex CLI — command-line interface for task submission."""
import sys, os
sys.path.insert(0, "/home/hermes")
os.chdir("/home/hermes/cortex")

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path("/home/hermes/cortex/.env"))

from cortex.phases.ingest import create_task, get_pending_tasks


def main():
    if len(sys.argv) < 2:
        print("Usage: cortex <command> [args]")
        print("Commands:")
        print("  add <title> [--priority N] [--project ID] [--body TEXT]")
        print("  list [status]")
        print("  status")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "add":
        title = sys.argv[2] if len(sys.argv) > 2 else ""
        if not title:
            print("Error: task title required")
            sys.exit(1)
        priority = 3
        project = ""
        body = ""
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--priority" and i + 1 < len(sys.argv):
                priority = int(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--project" and i + 1 < len(sys.argv):
                project = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--body" and i + 1 < len(sys.argv):
                body = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        task_id = create_task(title, body, project, priority)
        print(f"Task created: {task_id}")

    elif cmd == "list":
        status_filter = sys.argv[2] if len(sys.argv) > 2 else "ingest"
        tasks = get_pending_tasks()
        for t in tasks:
            print(f"  [{t['status']}] {t['id']} — {t['title']} (p{t['priority']})")

    elif cmd == "status":
        from cortex.lib.db import get_db
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM cortex_tasks").fetchone()[0]
        active = db.execute(
            "SELECT COUNT(*) FROM cortex_tasks WHERE status NOT IN ('done','failed','blocked')"
        ).fetchone()[0]
        print(f"Cortex status: {total} tasks total, {active} active")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
