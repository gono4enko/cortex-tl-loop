"""Unified data model: Events, Tasks, State Machine, Runner contract."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

class TaskStatus(str, Enum):
    NEW = "new"
    PLANNING = "planning"
    READY = "ready"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    VERIFYING = "verifying"
    REVIEWING = "reviewing"
    MERGING = "merging"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    STUCK = "stuck"
    RETRY = "retry"

ALLOWED_TRANSITIONS = {
    TaskStatus.NEW:        [TaskStatus.PLANNING, TaskStatus.READY],
    TaskStatus.PLANNING:   [TaskStatus.READY, TaskStatus.BLOCKED],
    TaskStatus.READY:      [TaskStatus.DISPATCHED],
    TaskStatus.DISPATCHED: [TaskStatus.RUNNING, TaskStatus.STUCK],
    TaskStatus.RUNNING:    [TaskStatus.VERIFYING, TaskStatus.FAILED, TaskStatus.STUCK],
    TaskStatus.VERIFYING:  [TaskStatus.REVIEWING, TaskStatus.FAILED, TaskStatus.RETRY],
    TaskStatus.REVIEWING:  [TaskStatus.MERGING, TaskStatus.FAILED, TaskStatus.BLOCKED],
    TaskStatus.MERGING:    [TaskStatus.DONE, TaskStatus.FAILED],
    TaskStatus.DONE:       [],
    TaskStatus.FAILED:     [TaskStatus.RETRY, TaskStatus.BLOCKED],
    TaskStatus.BLOCKED:    [TaskStatus.READY],
    TaskStatus.STUCK:      [TaskStatus.RETRY, TaskStatus.BLOCKED],
    TaskStatus.RETRY:      [TaskStatus.READY, TaskStatus.BLOCKED],
}

class EventType(str, Enum):
    TASK_CREATED = "task_created"
    STATUS_CHANGED = "status_changed"
    AGENT_DISPATCHED = "agent_dispatched"
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    VERIFY_PASSED = "verify_passed"
    VERIFY_FAILED = "verify_failed"
    REVIEW_PASSED = "review_passed"
    REVIEW_FAILED = "review_failed"
    MERGE_DONE = "merge_done"
    KB_WRITTEN = "kb_written"
    TICK_RUN = "tick_run"
    ERROR = "error"
    ESCALATION = "escalation"

@dataclass
class Task:
    id: str
    title: str
    body: str = ""
    project_id: str = ""
    status: TaskStatus = TaskStatus.NEW
    priority: int = 3
    agent: str = ""
    attempt: int = 0
    max_attempts: int = 3
    cost_usd: float = 0.0
    touched_files: list[str] = field(default_factory=list)
    verify_cmd: str = ""
    branch: str = ""
    last_error: str = ""
    created_at: str = ""
    updated_at: str = ""

@dataclass  
class Event:
    id: str
    task_id: str
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    ts: str = ""

@dataclass
class TickResult:
    tasks_seen: int = 0
    decisions_made: int = 0
    rules_fired: int = 0
    llm_calls: int = 0
    errors: int = 0
    cost_usd: float = 0.0

class Runner(Protocol):
    name: str
    def run(self, task: Task) -> dict[str, Any]: ...
    def cancel(self, task_id: str) -> bool: ...

class MCPAdapter(Protocol):
    name: str
    def search(self, query: str) -> list[dict]: ...
    def health(self) -> bool: ...
