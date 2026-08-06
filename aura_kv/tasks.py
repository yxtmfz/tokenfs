from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TaskType(str, Enum):
    PROMOTE = "PROMOTE"
    PREFETCH = "PREFETCH"
    REPLICATE = "REPLICATE"
    EVICT = "EVICT"
    SWAP = "SWAP"


class TaskState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


LEGAL_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.PENDING: {TaskState.RUNNING, TaskState.CANCELED},
    TaskState.RUNNING: {TaskState.VERIFYING, TaskState.FAILED, TaskState.CANCELED},
    TaskState.VERIFYING: {TaskState.COMMITTED, TaskState.FAILED, TaskState.CANCELED},
    TaskState.FAILED: {TaskState.PENDING, TaskState.CANCELED},
    TaskState.COMMITTED: set(),
    TaskState.CANCELED: set(),
}


@dataclass
class BackgroundTask:
    action_type: TaskType
    cache_key: str
    source: str
    target: str
    layout_version: int
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: TaskState = TaskState.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    reserved_bytes: int = 0
    expected_benefit_ms: float = 0.0
    error_code: str = ""
    error_message: str = ""
    checksum: str = ""
    dependency_task_ids: list[str] = field(default_factory=list)


@dataclass
class TaskRunResult:
    task_id: str
    state: TaskState
    changed_layout: bool
    message: str = ""


class TaskTransitionError(ValueError):
    pass


class DurableTaskQueue:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS background_tasks (
                task_id TEXT PRIMARY KEY,
                action_type TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                layout_version INTEGER NOT NULL,
                state TEXT NOT NULL,
                retry_count INTEGER NOT NULL,
                max_retries INTEGER NOT NULL,
                created_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL,
                reserved_bytes INTEGER NOT NULL,
                expected_benefit_ms REAL NOT NULL,
                error_code TEXT NOT NULL,
                error_message TEXT NOT NULL,
                checksum TEXT NOT NULL,
                dependency_task_ids TEXT NOT NULL
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_background_tasks_state ON background_tasks(state, created_at)")
        self.conn.commit()

    def enqueue(self, task: BackgroundTask) -> BackgroundTask:
        self.conn.execute(
            """
            INSERT INTO background_tasks (
                task_id, action_type, cache_key, source, target, layout_version, state,
                retry_count, max_retries, created_at, started_at, finished_at, reserved_bytes,
                expected_benefit_ms, error_code, error_message, checksum, dependency_task_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._to_row(task),
        )
        self.conn.commit()
        return task

    def get(self, task_id: str) -> BackgroundTask | None:
        row = self.conn.execute("SELECT * FROM background_tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._from_row(row) if row else None

    def list(self, state: TaskState | None = None) -> list[BackgroundTask]:
        if state is None:
            rows = self.conn.execute("SELECT * FROM background_tasks ORDER BY created_at, task_id").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM background_tasks WHERE state = ? ORDER BY created_at, task_id", (state.value,)
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def dependencies_committed(self, task: BackgroundTask) -> bool:
        for dep_id in task.dependency_task_ids:
            dep = self.get(dep_id)
            if dep is None or dep.state != TaskState.COMMITTED:
                return False
        return True

    def transition(self, task_id: str, next_state: TaskState, *, error_code: str = "", error_message: str = "") -> BackgroundTask:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if next_state not in LEGAL_TRANSITIONS[task.state]:
            raise TaskTransitionError(f"illegal task transition {task.state.value} -> {next_state.value}")
        now = time.time()
        task.state = next_state
        if next_state == TaskState.RUNNING and task.started_at is None:
            task.started_at = now
        if next_state in {TaskState.COMMITTED, TaskState.FAILED, TaskState.CANCELED}:
            task.finished_at = now
        task.error_code = error_code
        task.error_message = error_message
        self._update(task)
        return task

    def mark_failed_or_retry(self, task_id: str, error_code: str, error_message: str) -> BackgroundTask:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.state not in {TaskState.RUNNING, TaskState.VERIFYING}:
            raise TaskTransitionError(f"cannot fail task from {task.state.value}")
        if task.retry_count < task.max_retries:
            task.retry_count += 1
            task.state = TaskState.PENDING
            task.started_at = None
            task.error_code = error_code
            task.error_message = error_message
            self._update(task)
            return task
        return self.transition(task_id, TaskState.FAILED, error_code=error_code, error_message=error_message)

    def update_checksum(self, task_id: str, checksum: str) -> BackgroundTask:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        task.checksum = checksum
        self._update(task)
        return task

    def _update(self, task: BackgroundTask) -> None:
        self.conn.execute(
            """
            UPDATE background_tasks SET
                action_type = ?, cache_key = ?, source = ?, target = ?, layout_version = ?,
                state = ?, retry_count = ?, max_retries = ?, created_at = ?, started_at = ?,
                finished_at = ?, reserved_bytes = ?, expected_benefit_ms = ?, error_code = ?,
                error_message = ?, checksum = ?, dependency_task_ids = ?
            WHERE task_id = ?
            """,
            (*self._to_row(task)[1:], task.task_id),
        )
        self.conn.commit()

    @staticmethod
    def _to_row(task: BackgroundTask) -> tuple[object, ...]:
        return (
            task.task_id,
            task.action_type.value,
            task.cache_key,
            task.source,
            task.target,
            task.layout_version,
            task.state.value,
            task.retry_count,
            task.max_retries,
            task.created_at,
            task.started_at,
            task.finished_at,
            task.reserved_bytes,
            task.expected_benefit_ms,
            task.error_code,
            task.error_message,
            task.checksum,
            json.dumps(task.dependency_task_ids, separators=(",", ":")),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> BackgroundTask:
        return BackgroundTask(
            task_id=row["task_id"],
            action_type=TaskType(row["action_type"]),
            cache_key=row["cache_key"],
            source=row["source"],
            target=row["target"],
            layout_version=int(row["layout_version"]),
            state=TaskState(row["state"]),
            retry_count=int(row["retry_count"]),
            max_retries=int(row["max_retries"]),
            created_at=float(row["created_at"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            reserved_bytes=int(row["reserved_bytes"]),
            expected_benefit_ms=float(row["expected_benefit_ms"]),
            error_code=row["error_code"],
            error_message=row["error_message"],
            checksum=row["checksum"],
            dependency_task_ids=json.loads(row["dependency_task_ids"] or "[]"),
        )
