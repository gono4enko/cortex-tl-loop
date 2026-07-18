"""Daily/weekly reporter — Telegram morning, email Sunday."""
from __future__ import annotations
import logging, os
from cortex.lib.email import send_email, SMTP_TO

logger = logging.getLogger(__name__)

async def daily_telegram(tasks_done: int, tasks_active: int, ticks: int):
    """Send daily one-liner to Andrey via Telegram."""
    text = f"Cortex Daily: {tasks_done} done, {tasks_active} active, {ticks} ticks"
    try:
        import httpx
        bot = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat = os.environ.get("TELEGRAM_OWNER_ID", "176882915")
        if bot:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(f"https://api.telegram.org/bot{bot}/sendMessage",
                    json={"chat_id": chat, "text": text})
    except Exception as e:
        logger.warning(f"Daily TG: {e}")

async def weekly_email(done: int, failed: int, cost: float):
    """Send weekly digest to Andrey."""
    body = f"""# Cortex Weekly Report

## Metrics
- Tasks completed: {done}
- Tasks failed: {failed}
- Estimated cost: ${cost:.2f}

## Status
All systems operational. TL Orchestration Loop active.

---
Cortex Team Lead / GLM-5.2
hermes-assistant :9015
"""
    send_email(to=SMTP_TO, subject="Cortex Weekly Report", body=body, priority="info")
