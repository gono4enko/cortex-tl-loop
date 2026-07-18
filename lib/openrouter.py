"""OpenRouter API client with retry + backoff."""
from __future__ import annotations
import os, asyncio, logging, httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def openrouter_chat(
    messages: list[dict],
    model: str = "zai-org/GLM-5.2",
    max_tokens: int = 4096,
    temperature: float = 0.3,
    max_retries: int = 3,
) -> dict:
    """Send chat completion to OpenRouter with exponential backoff."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(OPENROUTER_URL, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                logger.info(
                    f"OpenRouter [{model}]: {data.get('usage',{}).get('total_tokens',0)} tokens, "
                    f"cost=${data.get('usage',{}).get('cost',0):.4f}"
                )
                return data
        except Exception as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning(f"OpenRouter attempt {attempt+1}/{max_retries} failed: {e}. Retry in {wait}s")
            await asyncio.sleep(wait)

    raise last_error or Exception("OpenRouter: all retries failed")


async def glm52_chat(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Convenience: call GLM-5.2 and return text response."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    result = await openrouter_chat(messages, model="zai-org/GLM-5.2", max_tokens=max_tokens, temperature=temperature)
    choices = result.get("choices", [])
    if choices:
        return choices[0]["message"]["content"]
    return ""
