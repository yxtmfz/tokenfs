from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any


EVENT_TYPES = {
    "REQUEST_ARRIVED",
    "CACHE_LOOKUP",
    "LOCAL_HIT",
    "PEER_HIT",
    "REMOTE_HIT",
    "RECOMPUTE",
    "REQUEST_COMPLETED",
    "ACCESS_EVENT_RECORDED",
    "CONTROLLER_CYCLE_STARTED",
    "DEMAND_UPDATED",
    "CANDIDATE_CREATED",
    "CANDIDATE_ACCEPTED",
    "CANDIDATE_REJECTED",
    "ACTION_PLAN_CREATED",
    "CONTROLLER_CYCLE_COMPLETED",
    "TASK_CREATED",
    "TASK_PENDING",
    "TASK_RUNNING",
    "TASK_VERIFYING",
    "TASK_COMMITTED",
    "TASK_FAILED",
    "TASK_RETRYING",
    "TASK_CANCELED",
    "REPLICA_COPYING",
    "REPLICA_VERIFYING",
    "REPLICA_READY",
    "REPLICA_EXPIRED",
    "REPLICA_DELETING",
    "REPLICA_REMOVED",
    "LAYOUT_VERSION_CHANGED",
    "BUDGET_RESERVED",
    "BUDGET_RELEASED",
}


@dataclass
class AuraEvent:
    timestamp: float
    run_id: str
    component: str
    event_type: str
    request_id: str = ""
    request_class: str = ""
    prefix_path: str = ""
    cache_key: str = ""
    node_id: str = ""
    controller_cycle_id: str = ""
    candidate_id: str = ""
    action_id: str = ""
    task_id: str = ""
    layout_version: int = 0
    source: str = ""
    target: str = ""
    state_before: str = ""
    state_after: str = ""
    bytes: int = 0
    latency_ms: float = 0.0
    eviction_loss_ms: float = 0.0
    replica_gain_ms: float = 0.0
    robust_benefit_ms: float = 0.0
    decision: str = ""
    reason: str = ""
    retry_count: int = 0
    error_code: str = ""
    error_message: str = ""
    simulated: bool = True
    workload_phase: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type
        return data


def new_run_id(prefix: str = "aura") -> str:
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[idx]


class MetricsAggregator:
    def __init__(self, series_limit: int = 240) -> None:
        self.series_limit = series_limit
        self.start_time = time.time()
        self.metrics: dict[str, float] = {
            "request_count": 0,
            "completed_request_count": 0,
            "failed_request_count": 0,
            "local_hit_count": 0,
            "peer_hit_count": 0,
            "remote_hit_count": 0,
            "recompute_count": 0,
            "local_bytes": 0,
            "peer_bytes": 0,
            "remote_bytes": 0,
            "recompute_tokens": 0,
            "duplicate_bytes": 0,
            "peak_duplicate_bytes": 0,
            "migration_bytes": 0,
            "replica_create_count": 0,
            "replica_evict_count": 0,
            "delete_then_recreate_count": 0,
            "task_queue_length": 0,
            "running_task_count": 0,
            "verifying_task_count": 0,
            "committed_task_count": 0,
            "failed_task_count": 0,
            "canceled_task_count": 0,
            "retry_count": 0,
            "controller_cycle_duration": 0,
            "candidate_count": 0,
            "accepted_candidate_count": 0,
            "rejected_candidate_count": 0,
            "eviction_loss_ms": 0,
            "replica_gain_ms": 0,
            "robust_benefit_ms": 0,
            "current_layout_version": 0,
        }
        self.latencies: list[float] = []
        self.task_started_at: dict[str, float] = {}
        self.task_latencies: list[float] = []
        self.active_tasks: dict[str, str] = {}
        self.series: list[dict[str, Any]] = []

    def add(self, event: AuraEvent) -> None:
        metric = self.metrics
        if event.event_type == "REQUEST_ARRIVED":
            metric["request_count"] += 1
        elif event.event_type == "REQUEST_COMPLETED":
            metric["completed_request_count"] += 1
            self.latencies.append(event.latency_ms)
        elif event.event_type == "LOCAL_HIT":
            metric["local_hit_count"] += 1
            metric["local_bytes"] += event.bytes
        elif event.event_type == "PEER_HIT":
            metric["peer_hit_count"] += 1
            metric["peer_bytes"] += event.bytes
        elif event.event_type == "REMOTE_HIT":
            metric["remote_hit_count"] += 1
            metric["remote_bytes"] += event.bytes
        elif event.event_type == "RECOMPUTE":
            metric["recompute_count"] += 1
            metric["recompute_tokens"] += float(event.extra.get("token_count", 0))
        elif event.event_type == "CANDIDATE_CREATED":
            metric["candidate_count"] += 1
            metric["eviction_loss_ms"] += event.eviction_loss_ms
            metric["replica_gain_ms"] += event.replica_gain_ms
            metric["robust_benefit_ms"] += event.robust_benefit_ms
        elif event.event_type == "CANDIDATE_ACCEPTED":
            metric["accepted_candidate_count"] += 1
        elif event.event_type == "CANDIDATE_REJECTED":
            metric["rejected_candidate_count"] += 1
        elif event.event_type == "CONTROLLER_CYCLE_COMPLETED":
            metric["controller_cycle_duration"] = event.latency_ms
        elif event.event_type == "TASK_CREATED":
            self.active_tasks[event.task_id] = "PENDING"
        elif event.event_type in {"TASK_RUNNING", "TASK_VERIFYING", "TASK_COMMITTED", "TASK_FAILED", "TASK_CANCELED"}:
            state = event.event_type.replace("TASK_", "")
            self.active_tasks[event.task_id] = state
            if event.event_type == "TASK_RUNNING":
                self.task_started_at[event.task_id] = event.timestamp
            if event.event_type in {"TASK_COMMITTED", "TASK_FAILED", "TASK_CANCELED"}:
                started = self.task_started_at.get(event.task_id)
                if started is not None:
                    self.task_latencies.append(max(0.0, event.timestamp - started) * 1000.0)
        elif event.event_type == "TASK_RETRYING":
            metric["retry_count"] += 1
        elif event.event_type == "REPLICA_READY":
            metric["replica_create_count"] += 1
            metric["migration_bytes"] += event.bytes
        elif event.event_type == "REPLICA_REMOVED":
            metric["replica_evict_count"] += 1
        elif event.event_type == "LAYOUT_VERSION_CHANGED":
            metric["current_layout_version"] = event.layout_version

        if event.extra.get("duplicate_bytes") is not None:
            metric["duplicate_bytes"] = float(event.extra["duplicate_bytes"])
            metric["peak_duplicate_bytes"] = max(metric["peak_duplicate_bytes"], metric["duplicate_bytes"])
        self._refresh_task_counts()
        self._append_series(event)

    def _refresh_task_counts(self) -> None:
        states = list(self.active_tasks.values())
        self.metrics["task_queue_length"] = sum(1 for state in states if state == "PENDING")
        self.metrics["running_task_count"] = sum(1 for state in states if state == "RUNNING")
        self.metrics["verifying_task_count"] = sum(1 for state in states if state == "VERIFYING")
        self.metrics["committed_task_count"] = sum(1 for state in states if state == "COMMITTED")
        self.metrics["failed_task_count"] = sum(1 for state in states if state == "FAILED")
        self.metrics["canceled_task_count"] = sum(1 for state in states if state == "CANCELED")

    def _append_series(self, event: AuraEvent) -> None:
        if event.event_type not in {
            "REQUEST_COMPLETED",
            "LOCAL_HIT",
            "PEER_HIT",
            "REMOTE_HIT",
            "TASK_CREATED",
            "TASK_RUNNING",
            "TASK_COMMITTED",
            "CONTROLLER_CYCLE_COMPLETED",
            "LAYOUT_VERSION_CHANGED",
        }:
            return
        snapshot = self.snapshot()
        self.series.append(
            {
                "timestamp": event.timestamp,
                "request_count": snapshot["request_count"],
                "requests_per_second": snapshot["requests_per_second"],
                "remote_bytes": snapshot["remote_bytes"],
                "duplicate_bytes": snapshot["duplicate_bytes"],
                "migration_bytes": snapshot["migration_bytes"],
                "task_queue_length": snapshot["task_queue_length"],
                "running_task_count": snapshot["running_task_count"],
                "p50_proxy": snapshot["p50_proxy"],
                "p95_proxy": snapshot["p95_proxy"],
                "p99_proxy": snapshot["p99_proxy"],
            }
        )
        self.series = self.series[-self.series_limit :]

    def snapshot(self) -> dict[str, Any]:
        elapsed = max(1e-6, time.time() - self.start_time)
        result = dict(self.metrics)
        result["requests_per_second"] = result["request_count"] / elapsed
        result["request_latency_proxy"] = median(self.latencies) if self.latencies else 0.0
        result["p50_proxy"] = percentile(self.latencies, 50)
        result["p95_proxy"] = percentile(self.latencies, 95)
        result["p99_proxy"] = percentile(self.latencies, 99)
        result["slo_violation_proxy"] = 0.0
        result["task_execution_latency"] = median(self.task_latencies) if self.task_latencies else 0.0
        return result


class JsonlRunStore:
    def __init__(
        self,
        run_dir: str | Path,
        run_id: str | None = None,
        *,
        simulated: bool = True,
        policy: str = "",
        workload: str = "",
        mode: str = "SIMULATED",
        series_limit: int = 240,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or new_run_id()
        self.simulated = simulated
        self.policy = policy
        self.workload = workload
        self.mode = mode
        self.aggregator = MetricsAggregator(series_limit=series_limit)
        self.events_path = self.run_dir / "events.jsonl"
        self.metrics_path = self.run_dir / "metrics.jsonl"
        self.layout_path = self.run_dir / "layout_snapshots.jsonl"
        self.manifest_path = self.run_dir / "manifest.json"
        self.write_manifest(status="RUNNING")

    def write_manifest(self, status: str, **extra: Any) -> None:
        payload = {
            "run_id": self.run_id,
            "status": status,
            "mode": self.mode,
            "simulated": self.simulated,
            "policy": self.policy,
            "workload": self.workload,
            "updated_at": time.time(),
            **extra,
        }
        self.manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def emit(self, event_type: str, component: str, **kwargs: Any) -> AuraEvent:
        event = AuraEvent(
            timestamp=float(kwargs.pop("timestamp", time.time())),
            run_id=self.run_id,
            component=component,
            event_type=event_type,
            simulated=self.simulated,
            **kwargs,
        )
        self.append(event)
        return event

    def append(self, event: AuraEvent) -> None:
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n")
        self.aggregator.add(event)
        self.append_metrics(event.timestamp)

    def append_metrics(self, timestamp: float | None = None) -> None:
        payload = {"timestamp": timestamp or time.time(), "run_id": self.run_id, **self.aggregator.snapshot()}
        with self.metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

    def append_layout(self, snapshot: dict[str, Any]) -> None:
        payload = {"timestamp": time.time(), "run_id": self.run_id, **snapshot}
        with self.layout_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: str | Path, limit: int | None = None) -> list[dict[str, Any]]:
    jsonl = Path(path)
    if not jsonl.exists():
        return []
    rows: list[dict[str, Any]] = []
    with jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows[-limit:] if limit else rows


def _load_manifest(run_dir: Path) -> dict[str, Any]:
    manifest = run_dir / "manifest.json"
    if not manifest.exists():
        return {"status": "STOPPED", "mode": "SIMULATED", "simulated": True, "run_id": run_dir.name}
    return json.loads(manifest.read_text(encoding="utf-8"))


def build_state_snapshot(run_dir: str | Path, *, event_limit: int = 200, series_limit: int = 240) -> dict[str, Any]:
    root = Path(run_dir)
    manifest = _load_manifest(root)
    events = read_jsonl(root / "events.jsonl")
    tail = events[-event_limit:]
    metrics_rows = read_jsonl(root / "metrics.jsonl")
    layout_rows = read_jsonl(root / "layout_snapshots.jsonl")
    latest_metrics = metrics_rows[-1] if metrics_rows else {}
    series = metrics_rows[-series_limit:]
    tasks: dict[str, dict[str, Any]] = {}
    layout: dict[str, dict[str, Any]] = {}
    cycles: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    requests: dict[str, list[dict[str, Any]]] = {}
    now = time.time()
    last_event_time = events[-1]["timestamp"] if events else 0.0
    for event in events:
        if event.get("request_id"):
            requests.setdefault(event["request_id"], []).append(event)
        if event.get("task_id"):
            task = tasks.setdefault(event["task_id"], {"task_id": event["task_id"], "events": []})
            task["events"].append(event)
            if event["event_type"].startswith("TASK_"):
                task.update(
                    {
                        "action_type": event.get("decision") or event.get("extra", {}).get("action_type", ""),
                        "cache_key": event.get("cache_key", ""),
                        "source": event.get("source", ""),
                        "target": event.get("target", ""),
                        "state": event["event_type"].replace("TASK_", ""),
                        "retry_count": event.get("retry_count", 0),
                        "layout_version": event.get("layout_version", 0),
                        "expected_benefit": event.get("robust_benefit_ms", 0),
                        "error_message": event.get("error_message", ""),
                        "updated_at": event.get("timestamp", 0),
                    }
                )
        if event.get("controller_cycle_id"):
            cycle = cycles.setdefault(event["controller_cycle_id"], {"cycle_id": event["controller_cycle_id"], "events": 0})
            cycle["events"] += 1
            cycle["layout_version"] = event.get("layout_version", cycle.get("layout_version", 0))
            cycle["updated_at"] = event.get("timestamp", cycle.get("updated_at", 0))
        if event["event_type"].startswith("CANDIDATE_"):
            candidates.append(event)
        if event["event_type"].startswith("REPLICA_") and event.get("cache_key"):
            key = f"{event['cache_key']}::{event.get('node_id') or event.get('target')}"
            layout[key] = {
                "cache_key": event["cache_key"],
                "node_id": event.get("node_id") or event.get("target"),
                "state": event["event_type"].replace("REPLICA_", ""),
                "object_bytes": event.get("bytes", 0),
                "layout_version": event.get("layout_version", 0),
                "task_id": event.get("task_id", ""),
                "action_id": event.get("action_id", ""),
                "updated_at": event.get("timestamp", 0),
            }
    if layout_rows:
        for row in layout_rows[-1].get("replicas", []):
            key = f"{row.get('cache_key')}::{row.get('node_id')}"
            layout[key] = row
    status = manifest.get("status", "STOPPED")
    if status == "RUNNING" and last_event_time and now - last_event_time > 5.0:
        status = "IDLE"
    connection = "STALE" if last_event_time and now - last_event_time > 5.0 else "CONNECTED"
    return {
        "manifest": {**manifest, "status": status, "connection": connection},
        "latest_metrics": latest_metrics,
        "series": series[-series_limit:],
        "events": tail,
        "tasks": list(tasks.values())[-event_limit:],
        "layout": list(layout.values()),
        "cycles": list(cycles.values())[-event_limit:],
        "candidates": candidates[-event_limit:],
        "request_traces": requests,
        "event_count": len(events),
    }
