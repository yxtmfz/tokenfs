from __future__ import annotations

import csv
import json
import random
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .core import AccessEvent, CacheIdentity, CacheObject, NodeState, Replica
from .policies import (
    AffinityOnlyPolicy,
    AuraKVPolicy,
    DualWindowReplacementPolicy,
    EWMAReplacementPolicy,
    ExhaustiveOptimalPolicy,
    IndependentControllersPolicy,
    NodeLFUPolicy,
    NodeLRUPolicy,
    OracleDemandPolicy,
    PrefixSourceAwareReplacementPolicy,
    ProducerLocalPolicy,
    RemoteOnlyPolicy,
    SizeAwareLRUPolicy,
    SimulationPolicy,
    SourceAwareReplacementPolicy,
    StaticNReplicaPolicy,
    WeightedScoreBaselinePolicy,
    AlternativeSourceResolver,
)


MIB = 1024 * 1024


@dataclass
class SimulationConfig:
    seed: int = 7
    nodes: int = 2
    gpus_per_node: int = 2
    local_capacity_mib: int = 96
    remote_read_p50_ms: float = 1.2
    remote_read_p99_ms: float = 8.0
    local_read_p50_ms: float = 0.08
    peer_read_p99_ms: float = 4.0
    foreground_slo_ms: float = 10.0
    duplicate_budget_mib: int = 128
    node_duplicate_budget_mib: int = 64
    demand_horizon_seconds: float = 600.0


@dataclass
class SimulationResult:
    policy: str
    scenario: str
    simulated_result: bool
    requests: int
    local_cache_hit_rate: float
    remote_read_bytes: int
    peer_read_bytes: int
    recomputed_ms: float
    duplicate_bytes: int
    replica_count: int
    replica_churn: int
    migration_bytes: int
    ttft_p50_ms: float
    ttft_p95_ms: float
    ttft_p99_ms: float
    slo_violation_rate: float
    decision_count: int
    objective_cost: float = 0.0
    objective_cost_per_request: float = 0.0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[idx]


class TraceSimulator:
    def __init__(
        self,
        config: SimulationConfig,
        caches: dict[str, CacheObject],
        trace: list[AccessEvent],
        policy: SimulationPolicy,
        scenario: str,
        monitor: Any | None = None,
        run_id: str = "",
    ) -> None:
        self.config = config
        self.caches = caches
        self.trace = trace
        self.policy = policy
        self.scenario = scenario
        self.monitor = monitor
        self.run_id = run_id
        self.rng = random.Random(config.seed)
        self.nodes = {
            f"node{i}": NodeState(f"node{i}", config.local_capacity_mib * MIB)
            for i in range(config.nodes)
        }
        self.remote_objects = set(caches)
        self.access_graph: dict[str, dict[str, float]] = {}
        self.source_resolver = AlternativeSourceResolver()
        self.remote_p99_ms = config.remote_read_p99_ms
        self.peer_p99_ms = config.peer_read_p99_ms
        self.latencies_ms: list[float] = []
        self.local_hits = 0
        self.remote_read_bytes = 0
        self.peer_read_bytes = 0
        self.recomputed_ms = 0.0
        self.replica_churn = 0
        self.migration_bytes = 0
        self.decisions: list[dict] = []
        self.last_replica_change: dict[tuple[str, str], float] = {}
        self.layout_version = 1
        self.controller_cycle = 0
        self.task_sequence = 0
        self.action_sequence = 0

    @property
    def duplicate_bytes(self) -> int:
        return sum(replica.size_bytes for node in self.nodes.values() for replica in node.replicas.values())

    def node_duplicate_bytes(self, node_id: str) -> int:
        return sum(replica.size_bytes for replica in self.nodes[node_id].replicas.values())

    def remote_has(self, cache_key: str) -> bool:
        return cache_key in self.remote_objects

    def workload_phase(self, event: AccessEvent) -> str:
        if self.scenario == "hotspot_shift":
            return "node0-hot" if event.timestamp < 32.0 else "node1-hot"
        if self.scenario == "remote_congestion":
            return "remote-congested"
        if self.scenario == "demand_estimation_error":
            return "bursty"
        if self.scenario == "private":
            return "private"
        if self.scenario == "cluster_shared":
            return "shared-prefix"
        return self.scenario

    def emit(self, event_type: str, component: str, **kwargs: Any) -> None:
        if self.monitor is None:
            return
        kwargs.setdefault("layout_version", self.layout_version)
        self.monitor.emit(event_type, component, **kwargs)

    def emit_layout_snapshot(self) -> None:
        if self.monitor is None:
            return
        replicas = []
        for node_id, node in self.nodes.items():
            for replica in node.replicas.values():
                replicas.append(
                    {
                        "cache_key": replica.cache_key,
                        "node_id": node_id,
                        "state": replica.status.value,
                        "object_bytes": replica.size_bytes,
                        "lease": replica.lease_expire_at,
                        "action_id": "",
                        "task_id": "",
                        "capacity_used": node.local_used_bytes,
                        "reserved_bytes": 0,
                        "duplicate_bytes": self.duplicate_bytes,
                        "layout_version": self.layout_version,
                    }
                )
        for cache_key in self.remote_objects:
            cache = self.caches.get(cache_key)
            replicas.append(
                {
                    "cache_key": cache_key,
                    "node_id": "remote",
                    "state": "CANONICAL",
                    "object_bytes": cache.size_bytes if cache else 0,
                    "lease": 0,
                    "action_id": "",
                    "task_id": "",
                    "capacity_used": 0,
                    "reserved_bytes": 0,
                    "duplicate_bytes": self.duplicate_bytes,
                    "layout_version": self.layout_version,
                }
            )
        self.monitor.append_layout(
            {
                "layout_version": self.layout_version,
                "duplicate_bytes": self.duplicate_bytes,
                "replicas": replicas,
            }
        )

    def prefix_dependency_benefit(self, cache: CacheObject) -> float:
        if not cache.parent_cache_key:
            children = sum(1 for item in self.caches.values() if item.parent_cache_key == cache.identity.cache_key)
            return min(30.0, children * 3.0)
        return 0.0

    def churn_penalty(self, cache_key: str, node_id: str) -> float:
        key = (cache_key, node_id)
        last = self.last_replica_change.get(key)
        if last is None:
            return 0.0
        return 8.0

    def p99_latency(self) -> float:
        return percentile(self.latencies_ms, 99)

    def ensure_space_and_add(self, node_id: str, cache: CacheObject, reason: str, evict: str = "lru") -> bool:
        node = self.nodes[node_id]
        if node.has_replica(cache.identity.cache_key):
            return True
        node_budget = min(node.local_capacity_bytes, self.config.node_duplicate_budget_mib * MIB)
        if cache.size_bytes > node_budget or cache.size_bytes > self.config.duplicate_budget_mib * MIB:
            return False
        while node.local_used_bytes + cache.size_bytes > node_budget:
            victim = self.choose_victim(node, evict)
            if victim is None:
                return False
            victim_cache = self.caches[victim]
            self.remove_replica_for_space(node_id, victim, f"node capacity pressure before adding {cache.identity.cache_key}")
        while self.duplicate_bytes + cache.size_bytes > self.config.duplicate_budget_mib * MIB:
            victim = self.choose_global_victim(evict)
            if victim is None:
                return False
            victim_node, victim_key = victim
            self.remove_replica_for_space(victim_node, victim_key, f"global duplicate budget before adding {cache.identity.cache_key}")
        replica = Replica(
            cache_key=cache.identity.cache_key,
            node_id=node_id,
            size_bytes=cache.size_bytes,
            lease_expire_at=cache.last_access_at + 600,
            utility_at_creation=1.0,
        )
        task_id = self.next_task_id("replicate")
        self.emit_task_transition(
            task_id,
            "REPLICATE",
            cache.identity.cache_key,
            "remote",
            node_id,
            ["CREATED", "PENDING", "RUNNING"],
            bytes_value=cache.size_bytes,
            reason=reason,
        )
        self.emit(
            "REPLICA_COPYING",
            "layout",
            cache_key=cache.identity.cache_key,
            node_id=node_id,
            source="remote",
            target=node_id,
            task_id=task_id,
            bytes=cache.size_bytes,
            state_before="ABSENT",
            state_after="COPYING",
            reason=reason,
            extra={"duplicate_bytes": self.duplicate_bytes},
        )
        self.emit_task_transition(
            task_id,
            "REPLICATE",
            cache.identity.cache_key,
            "remote",
            node_id,
            ["VERIFYING"],
            bytes_value=cache.size_bytes,
            reason="stage progress, not real byte progress",
        )
        self.emit(
            "REPLICA_VERIFYING",
            "layout",
            cache_key=cache.identity.cache_key,
            node_id=node_id,
            source="remote",
            target=node_id,
            task_id=task_id,
            bytes=cache.size_bytes,
            state_before="COPYING",
            state_after="VERIFYING",
            reason="stage progress, not real byte progress",
            extra={"duplicate_bytes": self.duplicate_bytes},
        )
        if node.add_replica(replica):
            self.replica_churn += 1
            self.migration_bytes += cache.size_bytes
            self.last_replica_change[(cache.identity.cache_key, node_id)] = cache.last_access_at
            self.layout_version += 1
            self.emit(
                "REPLICA_READY",
                "layout",
                cache_key=cache.identity.cache_key,
                node_id=node_id,
                source="remote",
                target=node_id,
                task_id=task_id,
                bytes=cache.size_bytes,
                state_before="VERIFYING",
                state_after="READY",
                reason=reason,
                extra={"duplicate_bytes": self.duplicate_bytes},
            )
            self.emit_task_transition(
                task_id,
                "REPLICATE",
                cache.identity.cache_key,
                "remote",
                node_id,
                ["COMMITTED"],
                bytes_value=cache.size_bytes,
                reason="replica ready",
            )
            self.emit(
                "LAYOUT_VERSION_CHANGED",
                "layout",
                cache_key=cache.identity.cache_key,
                node_id=node_id,
                task_id=task_id,
                layout_version=self.layout_version,
                reason="replica add changed layout",
                extra={"duplicate_bytes": self.duplicate_bytes},
            )
            self.emit_layout_snapshot()
            self.decisions.append(
                {
                    "cache_key": cache.identity.cache_key,
                    "node_id": node_id,
                    "action": "ADD_REPLICA",
                    "reason": reason,
                    "size_bytes": cache.size_bytes,
                }
            )
            return True
        self.emit_task_transition(
            task_id,
            "REPLICATE",
            cache.identity.cache_key,
            "remote",
            node_id,
            ["FAILED"],
            bytes_value=cache.size_bytes,
            reason="node rejected replica",
            error_code="NO_LOCAL_CAPACITY",
            error_message="target node cannot fit replica",
        )
        return False

    def remove_replica_for_space(self, node_id: str, cache_key: str, reason: str) -> None:
        node = self.nodes[node_id]
        victim_cache = self.caches[cache_key]
        evict_task = self.next_task_id("evict")
        self.emit_task_transition(
            evict_task,
            "EVICT",
            cache_key,
            f"node:{node_id}",
            node_id,
            ["CREATED", "RUNNING"],
            bytes_value=victim_cache.size_bytes,
            reason=reason,
        )
        self.emit(
            "REPLICA_DELETING",
            "layout",
            cache_key=cache_key,
            node_id=node_id,
            target=node_id,
            task_id=evict_task,
            bytes=victim_cache.size_bytes,
            state_before="READY",
            state_after="DELETING",
            reason="evict victim for new replica",
        )
        node.remove_replica(cache_key)
        self.replica_churn += 1
        self.last_replica_change[(cache_key, node_id)] = victim_cache.last_access_at
        self.layout_version += 1
        self.emit(
            "REPLICA_REMOVED",
            "layout",
            cache_key=cache_key,
            node_id=node_id,
            target=node_id,
            task_id=evict_task,
            bytes=victim_cache.size_bytes,
            state_before="DELETING",
            state_after="ABSENT",
            reason="local replica removed",
            extra={"duplicate_bytes": self.duplicate_bytes},
        )
        self.emit_task_transition(
            evict_task,
            "EVICT",
            cache_key,
            f"node:{node_id}",
            node_id,
            ["VERIFYING", "COMMITTED"],
            bytes_value=victim_cache.size_bytes,
            reason="eviction committed",
        )
        self.emit(
            "LAYOUT_VERSION_CHANGED",
            "layout",
            cache_key=cache_key,
            node_id=node_id,
            task_id=evict_task,
            layout_version=self.layout_version,
            reason="eviction changed layout",
            extra={"duplicate_bytes": self.duplicate_bytes},
        )

    def choose_global_victim(self, evict: str) -> tuple[str, str] | None:
        candidates = [node for node in self.nodes.values() if node.replicas]
        if not candidates:
            return None
        if evict == "lfu":
            node = min(candidates, key=lambda item: min(item.lfu_count.get(key, 0) for key in item.replicas))
            key = min(node.replicas, key=lambda item: node.lfu_count.get(item, 0))
            return node.node_id, key
        if evict == "value":
            def replica_value(item: tuple[NodeState, str]) -> float:
                node, key = item
                cache = self.caches[key]
                reads = self.access_graph.get(key, {}).get(node.node_id, 0.0)
                return reads * max(1.0, cache.recompute_cost_ms) / max(1.0, cache.size_bytes / MIB)
            node, key = min(((node, key) for node in candidates for key in node.replicas), key=replica_value)
            return node.node_id, key
        node = min(candidates, key=lambda item: min(item.lru_clock.get(key, 0.0) for key in item.replicas))
        key = min(node.replicas, key=lambda item: node.lru_clock.get(item, 0.0))
        return node.node_id, key

    def next_task_id(self, prefix: str) -> str:
        self.task_sequence += 1
        return f"{prefix}-{self.task_sequence}"

    def next_action_id(self) -> str:
        self.action_sequence += 1
        return f"action-{self.action_sequence}"

    def emit_task_transition(
        self,
        task_id: str,
        action_type: str,
        cache_key: str,
        source: str,
        target: str,
        states: list[str],
        *,
        bytes_value: int,
        reason: str,
        error_code: str = "",
        error_message: str = "",
    ) -> None:
        previous = ""
        for state in states:
            event_type = f"TASK_{state}"
            self.emit(
                event_type,
                "executor",
                task_id=task_id,
                cache_key=cache_key,
                source=source,
                target=target,
                state_before=previous,
                state_after=state,
                bytes=bytes_value,
                decision=action_type,
                reason=reason,
                error_code=error_code if state == "FAILED" else "",
                error_message=error_message if state == "FAILED" else "",
                extra={"action_type": action_type, "stage_progress": self.stage_progress(state)},
            )
            previous = state

    @staticmethod
    def stage_progress(state: str) -> int:
        return {
            "CREATED": 0,
            "PENDING": 0,
            "RUNNING": 40,
            "VERIFYING": 85,
            "COMMITTED": 100,
            "FAILED": 100,
            "CANCELED": 100,
        }.get(state, 0)

    def choose_victim(self, node: NodeState, evict: str) -> str | None:
        if not node.replicas:
            return None
        if evict == "lfu":
            return min(node.replicas, key=lambda key: node.lfu_count.get(key, 0))
        if evict == "size_aware_lru":
            def size_aware_lru(key: str) -> float:
                cache = self.caches[key]
                age = max(0.0, cache.last_access_at - node.lru_clock.get(key, 0.0))
                return age / max(1.0, cache.size_bytes / MIB)
            return max(node.replicas, key=size_aware_lru)
        if evict == "value":
            def value(key: str) -> float:
                cache = self.caches[key]
                reads = self.access_graph.get(key, {}).get(node.node_id, 0.0)
                return reads * max(1.0, cache.recompute_cost_ms) / max(1.0, cache.size_bytes / MIB)
            return min(node.replicas, key=value)
        return min(node.replicas, key=lambda key: node.lru_clock.get(key, 0.0))

    def latency_for_source(self, source: str, event: AccessEvent) -> float:
        cache = self.caches[event.cache_key]
        if source == "local":
            self.local_hits += 1
            return self.config.local_read_p50_ms + self.rng.random() * 0.05
        if "peer" in source:
            self.peer_read_bytes += event.bytes
            return self.config.peer_read_p99_ms * (0.45 + self.rng.random() * 0.55)
        if "recompute" in source:
            self.recomputed_ms += cache.recompute_cost_ms
            return cache.recompute_cost_ms
        self.remote_read_bytes += event.bytes
        tail = self.config.remote_read_p99_ms if self.rng.random() > 0.94 else self.config.remote_read_p50_ms
        return tail * (0.65 + self.rng.random() * 0.7)

    def run(self, event_delay_seconds: float = 0.0) -> SimulationResult:
        self.emit_layout_snapshot()
        for event in self.trace:
            cache = self.caches[event.cache_key]
            cache.last_access_at = event.timestamp
            phase = self.workload_phase(event)
            self.emit(
                "REQUEST_ARRIVED",
                "foreground",
                timestamp=time.time(),
                request_id=event.request_id,
                request_class=event.sharing_domain,
                prefix_path=event.parent_cache_key,
                cache_key=event.cache_key,
                node_id=event.node_id,
                bytes=event.bytes,
                workload_phase=phase,
                extra={"token_count": event.token_count},
            )
            self.emit(
                "CACHE_LOOKUP",
                "foreground",
                request_id=event.request_id,
                cache_key=event.cache_key,
                node_id=event.node_id,
                bytes=event.bytes,
                workload_phase=phase,
                reason="lookup local, peer, remote or recompute sources",
            )
            counts = self.access_graph.setdefault(event.cache_key, {})
            counts[event.node_id] = counts.get(event.node_id, 0.0) + 1.0
            self.controller_cycle += 1
            cycle_id = f"cycle-{self.controller_cycle}"
            cycle_start = time.time()
            self.emit(
                "CONTROLLER_CYCLE_STARTED",
                "controller",
                controller_cycle_id=cycle_id,
                request_id=event.request_id,
                cache_key=event.cache_key,
                node_id=event.node_id,
                workload_phase=phase,
                reason="simulated control cycle starts after foreground event",
            )
            self.emit(
                "DEMAND_UPDATED",
                "controller",
                controller_cycle_id=cycle_id,
                request_id=event.request_id,
                cache_key=event.cache_key,
                node_id=event.node_id,
                workload_phase=phase,
                reason="access event updates demand estimator",
            )
            source, decisions = self.policy.on_access(self, event)
            for decision in decisions:
                candidate_id = f"cand-{self.controller_cycle}-{len(self.decisions) + 1}"
                action_id = self.next_action_id()
                event_type = "CANDIDATE_REJECTED" if decision.action.value in {"DEFER"} else "CANDIDATE_ACCEPTED"
                self.emit(
                    "CANDIDATE_CREATED",
                    "controller",
                    controller_cycle_id=cycle_id,
                    candidate_id=candidate_id,
                    action_id=action_id,
                    request_id=event.request_id,
                    cache_key=decision.cache_key,
                    node_id=decision.node_id,
                    source=decision.alternative_source.value,
                    target=decision.node_id,
                    bytes=event.bytes,
                    replica_gain_ms=decision.benefit,
                    robust_benefit_ms=decision.benefit - decision.cost,
                    decision=decision.action.value,
                    reason=decision.reason,
                    workload_phase=phase,
                )
                self.emit(
                    event_type,
                    "controller",
                    controller_cycle_id=cycle_id,
                    candidate_id=candidate_id,
                    action_id=action_id,
                    request_id=event.request_id,
                    cache_key=decision.cache_key,
                    node_id=decision.node_id,
                    source=decision.alternative_source.value,
                    target=decision.node_id,
                    bytes=event.bytes,
                    replica_gain_ms=decision.benefit,
                    robust_benefit_ms=decision.benefit - decision.cost,
                    decision=decision.action.value,
                    reason=decision.reason,
                    workload_phase=phase,
                )
                self.decisions.append(asdict(decision))
            if decisions:
                self.emit(
                    "ACTION_PLAN_CREATED",
                    "controller",
                    controller_cycle_id=cycle_id,
                    request_id=event.request_id,
                    cache_key=event.cache_key,
                    node_id=event.node_id,
                    reason=f"{len(decisions)} candidate decisions emitted",
                    workload_phase=phase,
                )
            self.emit(
                "CONTROLLER_CYCLE_COMPLETED",
                "controller",
                controller_cycle_id=cycle_id,
                request_id=event.request_id,
                cache_key=event.cache_key,
                node_id=event.node_id,
                latency_ms=(time.time() - cycle_start) * 1000.0,
                workload_phase=phase,
                reason="simulated control cycle completed",
            )
            latency = self.latency_for_source(source, event)
            self.latencies_ms.append(latency)
            hit_event = {
                "local": "LOCAL_HIT",
                "remote": "REMOTE_HIT",
                "recompute": "RECOMPUTE",
            }.get(source, "PEER_HIT" if "peer" in source else "REMOTE_HIT")
            self.emit(
                hit_event,
                "foreground",
                request_id=event.request_id,
                request_class=event.sharing_domain,
                prefix_path=event.parent_cache_key,
                cache_key=event.cache_key,
                node_id=event.node_id,
                source=source.upper(),
                bytes=event.bytes,
                latency_ms=latency,
                workload_phase=phase,
                extra={"token_count": event.token_count},
            )
            self.emit(
                "REQUEST_COMPLETED",
                "foreground",
                request_id=event.request_id,
                request_class=event.sharing_domain,
                prefix_path=event.parent_cache_key,
                cache_key=event.cache_key,
                node_id=event.node_id,
                source=source.upper(),
                bytes=event.bytes,
                latency_ms=latency,
                workload_phase=phase,
                reason="latency is a SIMULATED proxy, not real TTFT",
            )
            self.emit(
                "ACCESS_EVENT_RECORDED",
                "foreground",
                request_id=event.request_id,
                cache_key=event.cache_key,
                node_id=event.node_id,
                bytes=event.bytes,
                workload_phase=phase,
                reason="foreground event persisted for later control cycles",
            )
            if event.node_id in self.nodes:
                node = self.nodes[event.node_id]
                node.lru_clock[event.cache_key] = event.timestamp
                node.lfu_count[event.cache_key] = node.lfu_count.get(event.cache_key, 0) + 1
            self.policy.after_access(self, event)
            if event_delay_seconds > 0:
                time.sleep(event_delay_seconds)

        requests = len(self.trace)
        violations = sum(1 for latency in self.latencies_ms if latency > self.config.foreground_slo_ms)
        remote_mib = self.remote_read_bytes / MIB
        peer_mib = self.peer_read_bytes / MIB
        migration_mib = self.migration_bytes / MIB
        duplicate_mib = self.duplicate_bytes / MIB
        # A paper-friendly proxy objective. It is not a real TTFT value; it
        # combines foreground latency with traffic and layout maintenance cost
        # so conservative policies are not judged by hit rate alone.
        objective_cost = (
            sum(self.latencies_ms)
            + 0.08 * remote_mib
            + 0.04 * peer_mib
            + 0.03 * migration_mib
            + 0.01 * duplicate_mib
            + 1.50 * self.replica_churn
        )
        return SimulationResult(
            policy=self.policy.name,
            scenario=self.scenario,
            simulated_result=True,
            requests=requests,
            local_cache_hit_rate=self.local_hits / requests if requests else 0.0,
            remote_read_bytes=self.remote_read_bytes,
            peer_read_bytes=self.peer_read_bytes,
            recomputed_ms=round(self.recomputed_ms, 3),
            duplicate_bytes=self.duplicate_bytes,
            replica_count=sum(len(node.replicas) for node in self.nodes.values()),
            replica_churn=self.replica_churn,
            migration_bytes=self.migration_bytes,
            ttft_p50_ms=round(percentile(self.latencies_ms, 50), 4),
            ttft_p95_ms=round(percentile(self.latencies_ms, 95), 4),
            ttft_p99_ms=round(percentile(self.latencies_ms, 99), 4),
            slo_violation_rate=violations / requests if requests else 0.0,
            decision_count=len(self.decisions),
            objective_cost=round(objective_cost, 4),
            objective_cost_per_request=round(objective_cost / requests, 4) if requests else 0.0,
        )


def make_policy(name: str, config: SimulationConfig) -> SimulationPolicy:
    if name == "RemoteOnly":
        return RemoteOnlyPolicy()
    if name in {"ProducerLocal", "LocalFirst"}:
        policy = ProducerLocalPolicy()
        policy.name = name
        return policy
    if name in {"NodeLRU", "LRU-Local"}:
        policy = NodeLRUPolicy()
        policy.name = name
        return policy
    if name == "SizeAwareLRU":
        return SizeAwareLRUPolicy()
    if name in {"NodeLFU", "LFU-Local"}:
        policy = NodeLFUPolicy()
        policy.name = name
        return policy
    if name == "StaticNReplica":
        return StaticNReplicaPolicy(n=2)
    if name == "AffinityOnly":
        return AffinityOnlyPolicy()
    if name == "WeightedScoreBaseline":
        return WeightedScoreBaselinePolicy()
    if name == "EWMAReplacement":
        return EWMAReplacementPolicy()
    if name == "DualWindowReplacement":
        return DualWindowReplacementPolicy()
    if name == "SourceAwareReplacement":
        return SourceAwareReplacementPolicy()
    if name == "PrefixSourceAwareReplacement":
        return PrefixSourceAwareReplacementPolicy()
    if name in {"IndependentControllers", "WA-Affinity-Independent"}:
        policy = IndependentControllersPolicy()
        policy.name = name
        return policy
    if name == "OracleDemand":
        return OracleDemandPolicy()
    if name == "ExhaustiveOptimal":
        return ExhaustiveOptimalPolicy()
    if name in {"AURA-KV", "AURA-Joint"}:
        policy = AuraKVPolicy(
            duplicate_budget_bytes=config.duplicate_budget_mib * MIB,
            node_duplicate_budget_bytes=config.node_duplicate_budget_mib * MIB,
        )
        policy.name = name
        return policy
    raise ValueError(f"unknown policy: {name}")


POLICIES = [
    "RemoteOnly",
    "LocalFirst",
    "LRU-Local",
    "LFU-Local",
    "SizeAwareLRU",
    "WeightedScoreBaseline",
    "EWMAReplacement",
    "DualWindowReplacement",
    "SourceAwareReplacement",
    "PrefixSourceAwareReplacement",
    "StaticNReplica",
    "AffinityOnly",
    "WA-Affinity-Independent",
    "AURA-Joint",
    "OracleDemand",
    "ExhaustiveOptimal",
]

LEGACY_POLICY_NAMES = [
    "ProducerLocal",
    "NodeLRU",
    "NodeLFU",
    "IndependentControllers",
    "AURA-KV",
]

ALL_POLICY_NAMES = list(dict.fromkeys(POLICIES + LEGACY_POLICY_NAMES))


def make_cache(
    key: str,
    producer_node: str,
    gpu: int,
    size_mib: int,
    recompute_ms: float,
    sharing_domain: str = "default",
    parent: str = "",
    shared: bool = True,
) -> CacheObject:
    return CacheObject(
        identity=CacheIdentity(
            cache_key=key,
            sharing_domain=sharing_domain,
            token_prefix_hash=key,
            tenant_id=sharing_domain,
        ),
        producer_node_id=producer_node,
        producer_gpu_id=gpu,
        size_bytes=size_mib * MIB,
        token_count=size_mib * 512,
        recompute_cost_ms=recompute_ms,
        parent_cache_key=parent,
        sharing_allowed=shared,
    )


def generate_trace(scenario: str, config: SimulationConfig) -> tuple[dict[str, CacheObject], list[AccessEvent]]:
    rng = random.Random(config.seed)
    caches: dict[str, CacheObject] = {}
    events: list[AccessEvent] = []

    def add_event(i: int, key: str, node: str, gpu: int, ts: float, tenant: str = "default") -> None:
        cache = caches[key]
        events.append(
            AccessEvent(
                timestamp=ts,
                request_id=f"req-{scenario}-{i}",
                tenant_id=tenant,
                cache_key=key,
                parent_cache_key=cache.parent_cache_key,
                node_id=node,
                gpu_id=gpu,
                operation="read",
                bytes=cache.size_bytes,
                token_count=cache.token_count,
                foreground=True,
                recompute_cost_ms=cache.recompute_cost_ms,
                sharing_domain=tenant,
                token_prefix_hash=key,
            )
        )

    if scenario == "private":
        for node_i in range(config.nodes):
            for gpu_i in range(config.gpus_per_node):
                key = f"private-node{node_i}-gpu{gpu_i}"
                caches[key] = make_cache(key, f"node{node_i}", gpu_i, 12, 8, shared=False)
        for i in range(120):
            node_i = i % config.nodes
            gpu_i = (i // config.nodes) % config.gpus_per_node
            add_event(i, f"private-node{node_i}-gpu{gpu_i}", f"node{node_i}", gpu_i, i * 0.5)
    elif scenario == "node_shared":
        for node_i in range(config.nodes):
            key = f"node{node_i}-system-prefix"
            caches[key] = make_cache(key, f"node{node_i}", 0, 18, 45)
        for i in range(120):
            node_i = i % config.nodes
            gpu_i = i % config.gpus_per_node
            add_event(i, f"node{node_i}-system-prefix", f"node{node_i}", gpu_i, i * 0.5)
    elif scenario == "cluster_shared":
        caches["common-prefix"] = make_cache("common-prefix", "node0", 0, 24, 80)
        for i in range(160):
            node_i = i % config.nodes
            add_event(i, "common-prefix", f"node{node_i}", i % config.gpus_per_node, i * 0.4)
    elif scenario == "hotspot_shift":
        caches["moving-prefix"] = make_cache("moving-prefix", "node0", 0, 24, 70)
        for i in range(160):
            node_i = 0 if i < 80 else min(1, config.nodes - 1)
            add_event(i, "moving-prefix", f"node{node_i}", i % config.gpus_per_node, i * 0.4)
    elif scenario == "high_recompute":
        caches["expensive-prefix"] = make_cache("expensive-prefix", "node0", 0, 32, 180)
        caches["cheap-cache"] = make_cache("cheap-cache", "node0", 0, 32, 8)
        for i in range(120):
            key = "expensive-prefix" if i % 3 != 0 else "cheap-cache"
            add_event(i, key, f"node{i % config.nodes}", i % config.gpus_per_node, i * 0.5)
    elif scenario == "tenant_isolation":
        caches["tenantA-prefix"] = make_cache("tenantA-prefix", "node0", 0, 16, 50, sharing_domain="tenantA")
        caches["tenantB-prefix"] = make_cache("tenantB-prefix", "node1", 0, 16, 50, sharing_domain="tenantB")
        for i in range(120):
            if i % 2 == 0:
                add_event(i, "tenantA-prefix", "node0", 0, i * 0.5, tenant="tenantA")
            else:
                add_event(i, "tenantB-prefix", "node1", 0, i * 0.5, tenant="tenantB")
    elif scenario == "demand_estimation_error":
        caches["bursty-prefix"] = make_cache("bursty-prefix", "node0", 0, 20, 60)
        for i in range(150):
            node_i = rng.choice([0, 1]) if i % 10 == 0 else (0 if i < 90 else 1)
            add_event(i, "bursty-prefix", f"node{node_i}", i % config.gpus_per_node, i * 0.35)
    elif scenario == "remote_congestion":
        caches["congested-prefix"] = make_cache("congested-prefix", "node0", 0, 24, 65)
        for i in range(150):
            add_event(i, "congested-prefix", f"node{i % config.nodes}", i % config.gpus_per_node, i * 0.35)
    elif scenario == "scan_pollution":
        caches["steady-hot"] = make_cache("steady-hot", "node0", 0, 24, 160)
        for scan_i in range(24):
            caches[f"scan-once-{scan_i:02d}"] = make_cache(f"scan-once-{scan_i:02d}", "node0", 0, 16, 5)
        i = 0
        for _ in range(8):
            add_event(i, "steady-hot", "node0", 0, i * 0.25)
            i += 1
        for round_i in range(6):
            for scan_i in range(round_i * 4, round_i * 4 + 4):
                add_event(i, f"scan-once-{scan_i:02d}", "node0", 0, i * 0.25)
                i += 1
            for _ in range(5):
                add_event(i, "steady-hot", "node0", 0, i * 0.25)
                i += 1
    elif scenario == "large_object_pollution":
        for hot_i in range(6):
            caches[f"small-hot-{hot_i}"] = make_cache(f"small-hot-{hot_i}", "node0", 0, 6, 90)
        for big_i in range(8):
            caches[f"large-cold-{big_i}"] = make_cache(f"large-cold-{big_i}", "node0", 0, 42, 8)
        i = 0
        for _ in range(4):
            for hot_i in range(6):
                add_event(i, f"small-hot-{hot_i}", "node0", 0, i * 0.3)
                i += 1
        for big_i in range(8):
            add_event(i, f"large-cold-{big_i}", "node0", 0, i * 0.3)
            i += 1
            for hot_i in range(6):
                add_event(i, f"small-hot-{hot_i}", "node0", 0, i * 0.3)
                i += 1
    elif scenario == "multi_gpu_shared_burst":
        caches["shared-kv"] = make_cache("shared-kv", "node0", 0, 18, 120)
        caches["node0-private"] = make_cache("node0-private", "node0", 0, 18, 80, shared=False)
        caches["node1-private"] = make_cache("node1-private", "node1", 0, 18, 80, shared=False)
        i = 0
        for _ in range(25):
            add_event(i, "shared-kv", "node0", 0, i * 0.25)
            i += 1
            if config.nodes > 1:
                add_event(i, "shared-kv", "node1", 0, i * 0.25)
                i += 1
        for _ in range(20):
            add_event(i, "node0-private", "node0", 0, i * 0.25)
            i += 1
            if config.nodes > 1:
                add_event(i, "node1-private", "node1", 0, i * 0.25)
                i += 1
        for _ in range(25):
            node_i = i % min(config.nodes, 4)
            add_event(i, "shared-kv", f"node{node_i}", 0, i * 0.25)
            i += 1
    elif scenario == "tight_capacity_thrash":
        for hot_i in range(5):
            caches[f"thrash-hot-{hot_i}"] = make_cache(f"thrash-hot-{hot_i}", "node0", 0, 12, 110)
        for cold_i in range(12):
            caches[f"thrash-cold-{cold_i}"] = make_cache(f"thrash-cold-{cold_i}", "node0", 0, 12, 6)
        i = 0
        for _ in range(4):
            for hot_i in range(5):
                add_event(i, f"thrash-hot-{hot_i}", "node0", 0, i * 0.2)
                i += 1
        for cold_i in range(12):
            add_event(i, f"thrash-cold-{cold_i}", "node0", 0, i * 0.2)
            i += 1
            add_event(i, f"thrash-hot-{cold_i % 5}", "node0", 0, i * 0.2)
            i += 1
        for _ in range(4):
            for hot_i in range(5):
                add_event(i, f"thrash-hot-{hot_i}", "node0", 0, i * 0.2)
                i += 1
    elif scenario == "expensive_vs_cheap_mix":
        caches["expensive-kv"] = make_cache("expensive-kv", "node0", 0, 20, 220)
        for cheap_i in range(10):
            caches[f"cheap-kv-{cheap_i}"] = make_cache(f"cheap-kv-{cheap_i}", "node0", 0, 10, 4)
        i = 0
        for _ in range(10):
            add_event(i, "expensive-kv", "node0", 0, i * 0.25)
            i += 1
        for cheap_i in range(10):
            add_event(i, f"cheap-kv-{cheap_i}", "node0", 0, i * 0.25)
            i += 1
            if cheap_i % 2 == 0:
                add_event(i, "expensive-kv", "node0", 0, i * 0.25)
                i += 1
        for _ in range(12):
            add_event(i, "expensive-kv", "node0", 0, i * 0.25)
            i += 1
    else:
        raise ValueError(f"unknown scenario: {scenario}")
    return caches, events


SCENARIOS = [
    "private",
    "node_shared",
    "cluster_shared",
    "hotspot_shift",
    "high_recompute",
    "remote_congestion",
    "demand_estimation_error",
    "tenant_isolation",
    "scan_pollution",
    "large_object_pollution",
    "multi_gpu_shared_burst",
    "tight_capacity_thrash",
    "expensive_vs_cheap_mix",
]


def run_matrix(config: SimulationConfig, scenarios: list[str], policies: list[str]) -> list[SimulationResult]:
    results: list[SimulationResult] = []
    for scenario in scenarios:
        scenario_config = config
        if scenario == "remote_congestion":
            scenario_config = SimulationConfig(**{**asdict(config), "remote_read_p99_ms": config.remote_read_p99_ms * 2.5})
        for policy_name in policies:
            caches, trace = generate_trace(scenario, scenario_config)
            sim = TraceSimulator(
                scenario_config,
                caches,
                trace,
                make_policy(policy_name, scenario_config),
                scenario,
            )
            if hasattr(sim.policy, "set_future_trace"):
                sim.policy.set_future_trace(trace)  # type: ignore[attr-defined]
            results.append(sim.run())
    return results


def write_results(results: list[SimulationResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [asdict(result) for result in results]
    (output_dir / "aura_sim_results.json").write_text(
        json.dumps({"notice": "SIMULATED RESULT - not real NVMe-oF hardware data", "results": rows}, indent=2),
        encoding="utf-8",
    )
    with (output_dir / "aura_sim_results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# AURA-KV Trace Simulator Report",
        "",
        "**SIMULATED RESULT**: 当前结果来自 trace-driven simulator，不代表真实 NVMe-oF 硬件性能。",
        "",
        "| 场景 | 策略 | 本地命中率 | 远端读取 MiB | 重复副本 MiB | Churn | P99 ms | SLO 违约率 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['scenario']} | {row['policy']} | {row['local_cache_hit_rate']:.3f} | "
            f"{row['remote_read_bytes'] / MIB:.1f} | {row['duplicate_bytes'] / MIB:.1f} | "
            f"{row['replica_churn']} | {row['ttft_p99_ms']:.3f} | {row['slo_violation_rate']:.3f} |"
        )
    aura = [row for row in rows if row["policy"] == "AURA-KV"]
    if aura:
        lines.extend(
            [
                "",
                "## AURA-KV 汇总",
                "",
                f"- 平均本地命中率: {statistics.mean(row['local_cache_hit_rate'] for row in aura):.3f}",
                f"- 平均 P99: {statistics.mean(row['ttft_p99_ms'] for row in aura):.3f} ms",
                f"- 平均重复副本空间: {statistics.mean(row['duplicate_bytes'] for row in aura) / MIB:.1f} MiB",
                "",
                "这些数字用于检查策略是否按预期运作，真实论文结果仍需在导师提供的 NVMe-oF/GPU 环境中重新采集。",
            ]
        )
    (output_dir / "aura_sim_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
