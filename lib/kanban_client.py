"""Kanban API client — wrapper over http://localhost:9011/v1/tasks."""
import os
import httpx
import logging

logger = logging.getLogger(__name__)
KANBAN_URL = os.environ.get("KANBAN_URL", "http://localhost:9011")


async def kanban_get(path: str, params: dict = None, timeout: int = 10) -> dict:
    url = f"{KANBAN_URL}{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def kanban_post(path: str, data: dict, timeout: int = 10) -> dict:
    url = f"{KANBAN_URL}{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=data)
        r.raise_for_status()
        return r.json()


async def kanban_health() -> dict:
    try:
        return await kanban_get("/v1/heartbeat")
    except Exception as e:
        logger.warning(f"Kanban health check failed: {e}")
        return {"status": "unreachable", "error": str(e)}


async def kanban_create_task(task: dict) -> dict:
    return await kanban_post("/v1/tasks", task)


async def kanban_list_tasks(status: str = None, assignee: str = None, project_id: str = None, limit: int = 50) -> list:
    params = {"limit": limit}
    if status:
        params["status"] = status
    if assignee:
        params["assignee"] = assignee
    if project_id:
        params["project_id"] = project_id
    return await kanban_get("/v1/tasks", params)
