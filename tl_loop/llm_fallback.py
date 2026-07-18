"""LLM Fallback — call GLM-5.2 when rules don't match."""
from __future__ import annotations
import json, logging, os
from cortex.lib.openrouter import glm52_chat

logger = logging.getLogger(__name__)

DECISION_PROMPT = """Ты — Team Lead автономного AI-агентства. Прими решение по задаче.

Правила:
- Если задача новая и есть свободные агенты → dispatch первому агенту
- Если агенты заняты → wait (поставить в очередь)
- Если задача провалилась < 3 раз → retry с другим агентом
- Если задача провалилась 3+ раза → blocked (нужен человек)
- Если задача ждёт review > 30 мин → форсировать merge
- Если бюджет дня > $18 → blocked все новые задачи

Ответь ТОЛЬКО JSON: {"action": "dispatch|wait|retry|block|verify|done", "agent": "имя_агента", "reason": "кратко почему"}"""

async def llm_decide(task_info: str, agents: list[str]) -> dict:
    """Ask GLM-5.2 to decide what to do with a task."""
    user = f"""Задачи:
{task_info}

Свободные агенты: {agents or 'нет'}
Время: сейчас

Прими решение (JSON)."""
    
    try:
        response = await glm52_chat(DECISION_PROMPT, user, max_tokens=256)
        # Extract JSON from response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
        return {"action": "wait", "agent": "", "reason": "LLM response not parseable"}
    except Exception as e:
        logger.warning(f"LLM fallback error: {e}")
        return {"action": "wait", "agent": "", "reason": f"LLM error: {str(e)[:50]}"}
