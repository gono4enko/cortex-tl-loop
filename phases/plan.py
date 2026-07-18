"""PLAN phase: GLM-5.2 breaks down task into wave plan."""
from __future__ import annotations
import logging, json, datetime, uuid
from cortex.lib.db import execute, query
from cortex.lib.openrouter import glm52_chat
from cortex.lib.contracts import parse_wave_plan, validate_wave_plan

logger = logging.getLogger(__name__)

PLAN_SYSTEM_PROMPT = """Ты — GLM-5.2, Team Lead автономного AI-агентства «Hermes Cortex».

Твоя задача: разложить входящую задачу на wave_plan.yaml — план параллельных задач для исполнителей.

Правила:
1. Задачи в одной волне НЕ должны пересекаться по touched_files
2. Выбирай оптимального исполнителя: mac-opencode (тяжёлые), mac-kilo (surgical), kilo-hermes (DevOps), hermes-bot (batch)
3. Для каждой задачи укажи: id, title, objective, executor, priority (1-5), touched_files, forbidden_files, acceptance_criteria, verify_command
4. Формат вывода — ТОЛЬКО валидный YAML wave_plan

Пример вывода:
```yaml
wave_id: "wave-20260718-01"
project_id: "cortex"
description: "Реализовать health endpoint для сервиса X"
tasks:
  - id: "cortex-20260718-001"
    title: "Добавить /health endpoint"
    objective: "Создать FastAPI health endpoint возвращающий статус сервиса и БД"
    executor: "mac-opencode"
    priority: 5
    touched_files:
      - "src/api/health.py"
    forbidden_files:
      - ".env"
      - "ecosystem.config.js"
    acceptance_criteria:
      - "GET /health возвращает 200 и JSON"
      - "Статус БД в ответе"
    verify_command: "pytest tests/test_health.py -v"
```
"""


async def plan_task(task_id: str) -> dict | None:
    """Run PLAN phase for a task using GLM-5.2. Returns wave_plan dict or None."""
    tasks = query("SELECT * FROM cortex_tasks WHERE id = ?", (task_id,))
    if not tasks:
        logger.error(f"PLAN: task {task_id} not found")
        return None

    task = dict(tasks[0])
    execute("UPDATE cortex_tasks SET status = 'planning', phase = 'plan' WHERE id = ?", (task_id,))

    user_msg = f"""Задача: {task['title']}
Описание: {task['body'] or 'Нет описания'}
Проект: {task['project_id'] or 'не указан'}
Приоритет: {task['priority']}

Разложи эту задачу на wave_plan.yaml."""

    try:
        response = await glm52_chat(PLAN_SYSTEM_PROMPT, user_msg, max_tokens=8192)
        plan = parse_wave_plan(response)
        errors = validate_wave_plan(plan)

        if errors:
            logger.warning(f"PLAN validation errors for {task_id}: {errors}")
            # Store plan anyway, mark with errors
            wave_id = plan.get("wave_id", f"wave-{datetime.date.today().isoformat()}-{uuid.uuid4().hex[:6]}")
            execute(
                "INSERT INTO waves (id, project_id, status, plan_yaml) VALUES (?, ?, 'failed', ?)",
                (wave_id, task.get("project_id", ""), response),
            )
            execute(
                "UPDATE cortex_tasks SET wave_id = ?, status = 'blocked' WHERE id = ?",
                (wave_id, task_id),
            )
            return None

        wave_id = plan["wave_id"]
        execute(
            "INSERT INTO waves (id, project_id, status, plan_yaml) VALUES (?, ?, 'pending', ?)",
            (wave_id, task.get("project_id", ""), response),
        )

        # Create sub-tasks from plan
        for subtask in plan.get("tasks", []):
            subtask_id = subtask.get("id", f"cortex-{uuid.uuid4().hex[:8]}")
            execute(
                """INSERT INTO cortex_tasks (id, title, body, project_id, status, phase, priority, wave_id, executor_agent, touched_files)
                   VALUES (?, ?, ?, ?, 'ready', 'dispatch', ?, ?, ?, ?)""",
                (
                    subtask_id,
                    subtask.get("title", ""),
                    subtask.get("objective", ""),
                    task.get("project_id", ""),
                    subtask.get("priority", 3),
                    wave_id,
                    subtask.get("executor", ""),
                    json.dumps(subtask.get("touched_files", [])),
                ),
            )

        # Mark original task as planned
        execute(
            "UPDATE cortex_tasks SET status = 'ready', phase = 'plan', wave_id = ? WHERE id = ?",
            (wave_id, task_id),
        )
        logger.info(f"PLAN: {task_id} → wave {wave_id} with {len(plan.get('tasks', []))} sub-tasks")
        return plan

    except Exception as e:
        logger.error(f"PLAN failed for {task_id}: {e}")
        execute("UPDATE cortex_tasks SET status = 'failed', phase = 'plan' WHERE id = ?", (task_id,))
        return None
