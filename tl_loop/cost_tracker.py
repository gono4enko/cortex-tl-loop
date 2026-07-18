"""Cost tracker — per-task token/cost accounting."""
from __future__ import annotations
import logging, time, sqlite3
from pathlib import Path

logger = logging.getLogger("cost")

COST_DB = Path("/home/hermes/cortex/cost_log.db")

# Rough pricing per 1M tokens (July 2026)
PRICING = {
    "deepseek-chat":       (0.50, 2.20),   # DeepSeek V4 Flash
    "deepseek-v4-pro":     (1.00, 4.00),   # DeepSeek V4 Pro (thinking incl)
    "Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo": (0.35, 1.50),
    "Qwen/Qwen3-235B-A22B-Instruct": (0.30, 1.20),
    "zai-org/GLM-5.2":    (0.50, 2.00),
    "anthropic/claude-fable-5": (3.00, 15.00),
}


def _db():
    conn = sqlite3.connect(str(COST_DB))
    conn.execute("CREATE TABLE IF NOT EXISTS cost_log (ts TEXT, task_id TEXT, model TEXT, "
                 "input_tokens INT, output_tokens INT, cost_usd REAL)")
    return conn


def estimate_tokens(text: str) -> int:
    """Rough: ~4 chars per token."""
    return max(1, len(text or "") // 4)


def log_cost(task_id: str, model: str, input_text: str, output_text: str) -> float:
    """Log LLM call cost. Returns USD cost."""
    in_tok = estimate_tokens(input_text)
    out_tok = estimate_tokens(output_text)
    price_in, price_out = PRICING.get(model, (0.50, 2.00))
    cost = (in_tok / 1_000_000) * price_in + (out_tok / 1_000_000) * price_out

    try:
        _db().execute(
            "INSERT INTO cost_log (ts, task_id, model, input_tokens, output_tokens, cost_usd) "
            "VALUES (?,?,?,?,?,?)",
            (time.strftime("%Y-%m-%dT%H:%M:%S"), task_id, model, in_tok, out_tok, round(cost, 6)),
        )
        _db().commit()
    except Exception as e:
        logger.warning(f"Cost log failed: {e}")

    return cost


def get_total_cost(since: str = None) -> float:
    """Total cost since timestamp."""
    try:
        if since:
            row = _db().execute("SELECT SUM(cost_usd) FROM cost_log WHERE ts >= ?", (since,)).fetchone()
        else:
            row = _db().execute("SELECT SUM(cost_usd) FROM cost_log").fetchone()
        return round(row[0] or 0, 4)
    except Exception:
        return 0
