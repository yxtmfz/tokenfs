from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .core import CacheObject, NodeState, Replica, ReplicaStatus
from .tasks import BackgroundTask, DurableTaskQueue, TaskRunResult, TaskState, TaskType


def _safe_name(cache_key: str) -> str:
    return cache_key.replace("/", "__")


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class ExecutionStats:
    executed: int = 0
    committed: int = 0
    failed: int = 0
    canceled: int = 0
    bytes_copied: int = 0
    layout_changes: int = 0


class DirectoryReplicaExecutor:
    """Runs AURA-KV background tasks against directory-backed local and remote tiers.

    This is intentionally filesystem-level, not NVMe-specific. In the real setup,
    the remote root is the directory mounted on top of an NVMe-oF namespace.
    """

    def __init__(
        self,
        queue: DurableTaskQueue,
        remote_root: str | Path,
        local_root: str | Path,
        nodes: dict[str, NodeState],
        caches: dict[str, CacheObject],
    ) -> None:
        self.queue = queue
        self.remote_root = Path(remote_root)
        self.local_root = Path(local_root)
        self.nodes = nodes
        self.caches = caches
        self.remote_root.mkdir(parents=True, exist_ok=True)
        self.local_root.mkdir(parents=True, exist_ok=True)
        for node_id in nodes:
            self.node_dir(node_id).mkdir(parents=True, exist_ok=True)

    def node_dir(self, node_id: str) -> Path:
        return self.local_root / node_id

    def remote_path(self, cache_key: str) -> Path:
        return self.remote_root / _safe_name(cache_key)

    def local_path(self, node_id: str, cache_key: str) -> Path:
        return self.node_dir(node_id) / _safe_name(cache_key)

    def write_remote(self, cache_key: str, data: bytes) -> str:
        path = self.remote_path(cache_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return file_checksum(path)

    def execute_pending(self, current_layout_version: int, limit: int | None = None) -> ExecutionStats:
        stats = ExecutionStats()
        tasks = self.queue.list(TaskState.PENDING)
        if limit is not None:
            tasks = tasks[:limit]
        for task in tasks:
            result = self.execute(task, current_layout_version)
            stats.executed += 1
            if result.state == TaskState.COMMITTED:
                stats.committed += 1
            elif result.state == TaskState.FAILED:
                stats.failed += 1
            elif result.state == TaskState.CANCELED:
                stats.canceled += 1
            if result.changed_layout:
                stats.layout_changes += 1
            cache = self.caches.get(task.cache_key)
            if result.changed_layout and cache is not None and task.action_type in {TaskType.PROMOTE, TaskType.PREFETCH, TaskType.REPLICATE}:
                stats.bytes_copied += cache.size_bytes
        return stats

    def execute(self, task: BackgroundTask, current_layout_version: int) -> TaskRunResult:
        persisted = self.queue.get(task.task_id)
        if persisted is not None and persisted.state in {TaskState.COMMITTED, TaskState.FAILED, TaskState.CANCELED}:
            return TaskRunResult(task.task_id, persisted.state, False, "task already terminal")
        if task.layout_version != current_layout_version:
            canceled = self.queue.transition(
                task.task_id,
                TaskState.CANCELED,
                error_code="STALE_LAYOUT",
                error_message=f"task layout {task.layout_version} != current layout {current_layout_version}",
            )
            return TaskRunResult(task.task_id, canceled.state, False, "stale layout")
        dependencies = [self.queue.get(key) for key in task.dependency_task_ids]
        if any(dep is not None and dep.state in {TaskState.FAILED, TaskState.CANCELED} for dep in dependencies):
            canceled = self.queue.transition(task.task_id, TaskState.CANCELED,
                                            error_code="DEPENDENCY_FAILED",
                                            error_message="a prerequisite ended without committing")
            return TaskRunResult(task.task_id, canceled.state, False, "dependency failed")
        if not self.queue.dependencies_committed(task):
            return TaskRunResult(task.task_id, task.state, False, "waiting for dependencies")
        try:
            if task.action_type in {TaskType.PROMOTE, TaskType.PREFETCH, TaskType.REPLICATE}:
                return self._copy_to_local(task)
            if task.action_type == TaskType.EVICT:
                return self._evict_local(task)
            if task.action_type == TaskType.SWAP:
                return self._finish_swap(task)
        except Exception as exc:  # pragma: no cover - defensive path is covered through states
            if self.queue.get(task.task_id).state == TaskState.PENDING:
                self.queue.transition(task.task_id, TaskState.RUNNING)
            failed = self.queue.mark_failed_or_retry(task.task_id, "EXECUTOR_EXCEPTION", str(exc))
            return TaskRunResult(task.task_id, failed.state, False, str(exc))
        return TaskRunResult(task.task_id, task.state, False, "unknown task type")

    def _copy_to_local(self, task: BackgroundTask) -> TaskRunResult:
        cache = self._cache(task.cache_key)
        node = self._node(task.target)
        if node.has_replica(task.cache_key):
            self.queue.transition(task.task_id, TaskState.RUNNING)
            self.queue.transition(task.task_id, TaskState.VERIFYING)
            committed = self.queue.transition(task.task_id, TaskState.COMMITTED)
            return TaskRunResult(task.task_id, committed.state, False, "replica already ready")
        if not node.can_fit(cache.size_bytes):
            self.queue.transition(task.task_id, TaskState.RUNNING)
            failed = self.queue.mark_failed_or_retry(task.task_id, "NO_LOCAL_CAPACITY", "target node has insufficient local capacity")
            return TaskRunResult(task.task_id, failed.state, False, "no local capacity")

        src = self._source_path(task.source, task.cache_key)
        if not src.exists():
            self.queue.transition(task.task_id, TaskState.RUNNING)
            failed = self.queue.mark_failed_or_retry(task.task_id, "MISSING_SOURCE", f"source does not exist: {src}")
            return TaskRunResult(task.task_id, failed.state, False, "missing source")
        if src.stat().st_size != cache.size_bytes:
            self.queue.transition(task.task_id, TaskState.RUNNING)
            failed = self.queue.mark_failed_or_retry(task.task_id, "SOURCE_SIZE_MISMATCH", "source size differs from reserved object size")
            return TaskRunResult(task.task_id, failed.state, False, "source size mismatch")

        self.queue.transition(task.task_id, TaskState.RUNNING)
        dst = self.local_path(task.target, task.cache_key)
        tmp = dst.with_suffix(dst.suffix + f".{task.task_id}.tmp")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, tmp)
        with tmp.open("rb") as handle:
            os.fsync(handle.fileno())

        self.queue.transition(task.task_id, TaskState.VERIFYING)
        src_checksum = file_checksum(src)
        dst_checksum = file_checksum(tmp)
        expected_checksums = [value for value in (task.checksum, cache.checksum) if value]
        if (src_checksum != dst_checksum or tmp.stat().st_size != cache.size_bytes
                or any(value != src_checksum for value in expected_checksums)):
            tmp.unlink(missing_ok=True)
            failed = self.queue.mark_failed_or_retry(task.task_id, "CHECKSUM_MISMATCH", "replica does not match source size/checksum or expected identity")
            return TaskRunResult(task.task_id, failed.state, False, "checksum mismatch")

        os.replace(tmp, dst)
        self.queue.update_checksum(task.task_id, dst_checksum)
        added = node.add_replica(
            Replica(
                task.cache_key,
                task.target,
                status=ReplicaStatus.READY,
                size_bytes=cache.size_bytes,
                utility_at_creation=task.expected_benefit_ms,
                latest_utility=task.expected_benefit_ms,
            )
        )
        if not added:
            dst.unlink(missing_ok=True)
            failed = self.queue.mark_failed_or_retry(task.task_id, "NO_LOCAL_CAPACITY", "target node rejected replica")
            return TaskRunResult(task.task_id, failed.state, False, "target rejected replica")
        committed = self.queue.transition(task.task_id, TaskState.COMMITTED)
        return TaskRunResult(task.task_id, committed.state, True, "replica ready")

    def _evict_local(self, task: BackgroundTask) -> TaskRunResult:
        self.queue.transition(task.task_id, TaskState.RUNNING)
        node = self._node(task.target)
        path = self.local_path(task.target, task.cache_key)
        replica = node.replicas.get(task.cache_key)
        if replica is None:
            self.queue.transition(task.task_id, TaskState.VERIFYING)
            committed = self.queue.transition(task.task_id, TaskState.COMMITTED)
            return TaskRunResult(task.task_id, committed.state, False, "replica already absent")
        if replica.status != ReplicaStatus.READY:
            failed = self.queue.mark_failed_or_retry(task.task_id, "REPLICA_NOT_READY", "only READY replicas can be evicted")
            return TaskRunResult(task.task_id, failed.state, False, "not ready")
        alternative_exists = self.remote_path(task.cache_key).is_file() or any(
            other_id != task.target and other.has_replica(task.cache_key)
            and self.local_path(other_id, task.cache_key).is_file()
            for other_id, other in self.nodes.items()
        )
        if not alternative_exists:
            failed = self.queue.mark_failed_or_retry(task.task_id, "UNSAFE_LAST_REPLICA", "no remaining canonical or READY replica")
            return TaskRunResult(task.task_id, failed.state, False, "last reliable replica")
        path.unlink(missing_ok=True)
        node.remove_replica(task.cache_key)
        self.queue.transition(task.task_id, TaskState.VERIFYING)
        committed = self.queue.transition(task.task_id, TaskState.COMMITTED)
        return TaskRunResult(task.task_id, committed.state, True, "replica evicted")

    def _finish_swap(self, task: BackgroundTask) -> TaskRunResult:
        self.queue.transition(task.task_id, TaskState.RUNNING)
        self.queue.transition(task.task_id, TaskState.VERIFYING)
        committed = self.queue.transition(task.task_id, TaskState.COMMITTED)
        return TaskRunResult(task.task_id, committed.state, False, "swap dependencies committed")

    def _cache(self, cache_key: str) -> CacheObject:
        cache = self.caches.get(cache_key)
        if cache is None:
            raise KeyError(f"unknown cache {cache_key}")
        return cache

    def _node(self, node_id: str) -> NodeState:
        node = self.nodes.get(node_id)
        if node is None:
            raise KeyError(f"unknown node {node_id}")
        return node

    def _source_path(self, source: str, cache_key: str) -> Path:
        if source == "remote":
            return self.remote_path(cache_key)
        if source.startswith("node:"):
            return self.local_path(source.split(":", 1)[1], cache_key)
        return Path(source)
