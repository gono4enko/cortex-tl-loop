#!/usr/bin/env python3
"""Cortex Watchdog — monitor orchestrator health, restart if needed."""
import subprocess, time, logging, os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [watchdog] %(levelname)s: %(message)s")
logger = logging.getLogger("watchdog")

HEALTH_URL = "http://localhost:9015/health"
CHECK_INTERVAL = 60
MAX_FAILURES = 3


def check_health() -> bool:
    try:
        import urllib.request, json
        r = urllib.request.urlopen(HEALTH_URL, timeout=10)
        data = json.loads(r.read())
        return data.get("status") in ("ok", "degraded")
    except Exception:
        return False


def main():
    failures = 0
    while True:
        if check_health():
            failures = 0
        else:
            failures += 1
            logger.warning(f"Health check failed ({failures}/{MAX_FAILURES})")

        if failures >= MAX_FAILURES:
            logger.error("Cortex unresponsive, restarting via PM2")
            subprocess.run(["sudo", "-u", "hermes", "pm2", "restart", "hermes-cortex"], timeout=30)
            time.sleep(10)
            failures = 0

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
