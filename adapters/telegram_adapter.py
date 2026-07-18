"""Cortex Telegram Adapter — TL <-> @her_andrew_bot communication."""
from __future__ import annotations
import os, logging, httpx

logger = logging.getLogger(__name__)

CORTEX_URL = os.environ.get("CORTEX_URL", "http://127.0.0.1:9015")
CORTEX_TOKEN = os.environ.get("CORTEX_API_TOKEN", "")


async def notify_andrey(text: str, priority: str = "info") -> bool:
    """Send urgent notification to Andrey via Cortex /notify/urgent (email + TG)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{CORTEX_URL}/notify/urgent",
                json={"subject": text[:100], "body": text, "priority": priority},
                headers={"X-Cortex-Token": CORTEX_TOKEN},
            )
            return r.status_code == 200
    except Exception as e:
        logger.warning(f"TG notify failed: {e}")
        return False


async def send_telegram_message(chat_id: int, text: str) -> bool:
    """Send message to a Telegram chat via bot API."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"},
            )
            return r.status_code == 200
    except Exception as e:
        logger.warning(f"TG send failed: {e}")
        return False
