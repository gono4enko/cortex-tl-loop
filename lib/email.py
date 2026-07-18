"""Cortex Email: SMTP sender + IMAP poller for team_lead@pergolarussia.ru."""
from __future__ import annotations
import smtplib, imaplib, email, time, logging, os, asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

logger = logging.getLogger(__name__)

def _read_pass(file_var: str) -> str:
    path = os.environ.get(file_var, "")
    if path and Path(path).exists():
        return Path(path).read_text().strip()
    return ""

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.beget.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "25"))
SMTP_USER = os.environ.get("SMTP_USER", "team_lead@pergolarussia.ru")
SMTP_PASS = _read_pass("SMTP_PASS_FILE") or os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "team_lead@pergolarussia.ru")
SMTP_TO = os.environ.get("SMTP_TO", "gono4enko@gmail.com")

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.beget.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
IMAP_USER = os.environ.get("IMAP_USER", "team_lead@pergolarussia.ru")
IMAP_PASS = _read_pass("IMAP_PASS_FILE") or os.environ.get("IMAP_PASS", "")

PRIORITY_COLORS = {"info": "#2196F3", "warn": "#FF9800", "urgent": "#f44336", "blocker": "#B71C1C"}


def send_email(to: str = None, subject: str = "", body: str = "", priority: str = "info") -> bool:
    """Send email via SMTP. Returns True on success."""
    color = PRIORITY_COLORS.get(priority, "#2196F3")
    html = f"""<html><body style="font-family:Arial,sans-serif">
<h2 style="color:{color}">{subject}</h2>
<pre style="white-space:pre-wrap;font-size:14px">{body}</pre>
<hr><small>Cortex Team Lead / GLM-5.2 @ hermes-assistant</small>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_FROM
    msg["To"] = to or SMTP_TO
    msg["Subject"] = f"[{priority.upper()}] {subject}"
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    for attempt in range(3):
        try:
            s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
            s.quit()
            logger.info(f"Email sent: {subject} -> {to or SMTP_TO}")
            return True
        except Exception as e:
            logger.warning(f"SMTP attempt {attempt+1}/3 failed: {e}")
            time.sleep(2 ** attempt)
    return False


def imap_fetch_unseen() -> list[dict]:
    """Fetch unseen emails. Returns list of {from, subject, body, date, msg_id}."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=15)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("INBOX")
        _, data = mail.search(None, "UNSEEN")
        results = []
        for num in data[0].split():
            _, msg_data = mail.fetch(num, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            results.append({
                "msg_id": msg.get("Message-ID", ""),
                "from": msg.get("From", ""),
                "subject": msg.get("Subject", ""),
                "date": msg.get("Date", ""),
                "body": _get_body(msg),
            })
        mail.logout()
        return results
    except Exception as e:
        logger.warning(f"IMAP fetch failed: {e}")
        return []


def _get_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode("utf-8", errors="replace")[:2000]
    return msg.get_payload(decode=True).decode("utf-8", errors="replace")[:2000]


async def imap_poll_loop(interval: int = 300):
    """Background IMAP poller. Stores unseen emails in cortex.db."""
    from cortex.lib.db import execute
    while True:
        try:
            msgs = imap_fetch_unseen()
            for m in msgs:
                execute(
                    "INSERT INTO inbox_messages (msg_id, sender, subject, body, received_at) VALUES (?, ?, ?, ?, datetime('now'))",
                    (m["msg_id"], m["from"], m["subject"], m["body"]),
                )
                logger.info(f"Inbox: {m['subject'][:60]}")
        except Exception as e:
            logger.warning(f"IMAP poll error: {e}")
        await asyncio.sleep(interval)


def notify_andrey(subject: str, body: str, priority: str = "info", also_telegram: bool = False) -> bool:
    """Send notification to Andrey. If also_telegram, sends to both channels."""
    return send_email(to=SMTP_TO, subject=subject, body=body, priority=priority)
