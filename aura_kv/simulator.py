from __future__ import annotations

import csv
import json
import random
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .core import AccessEvent, CacheIdentity, CacheObject, NodeState, Replica
from .policies import (
    AffinityOnlyPolicy,
    AuraKVPolicy,
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
    ) -> None:
        self.config = config
        self.caches = caches
        self.trace = trace
        self.policy = policy
        self.scenario = scenario
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

    @property
    def duplicate_bytes(self) -> int:
        return sum(replica.size_bytes for node in self.nodes.values() for replica in node.replicas.values())

    def node_duplicate_bytes(self, node_id: str) -> int:
        return sum(replica.size_bytes for replica in self.nodes[node_id].replicas.values())

    def remote_has(self, cache_key: str) -> bool:
        return cache_key in self.remote_objects

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
        while not node.can_fit(cache.size_bytes):
            victim = self.choose_victim(node, evict)
            if victim is None:
                return False
            node.remove_replica(victim)
            self.replica_churn += 1
            self.last_replica_change[(victim, node_id)] = cache.last_access_at
        replica = Replica(
            cache_key=cache.identity.cache_key,
            node_id=node_id,
            size_bytes=cache.size_bytes,
            lease_expire_at=cache.last_access_at + 600,
            utility_at_creation=1.0,
        )
        if node.add_replica(replica):
            self.replica_churn += 1
            self.migration_bytes += cache.size_bytes
            self.last_replica_change[(cache.identity.cache_key, node_id)] = cache.last_access_at
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
        return False

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

    def run(self) -> SimulationResult:
        for event in self.trace:
            cache = self.caches[event.cache_key]
            cache.last_access_at = event.timestamp
            counts = self.access_graph.setdefault(event.cache_key, {})
            counts[event.node_id] = counts.get(event.node_id, 0.0) + 1.0
            source, decisions = self.policy.on_access(self, event)
            for decision in decisions:
                self.decisions.append(asdict(decision))
            latency = self.latency_for_source(source, event)
            self.latencies_ms.append(latency)
            if event.node_id in self.nodes:
                node = self.nodes[event.node_id]
                node.lru_clock[event.cache_key] = event.timestamp
                node.lfu_count[event.cache_key] = node.lfu_count.get(event.cache_key, 0) + 1
            self.policy.after_access(self, event)

        requests = len(self.trace)
        violations = sum(1 for latency in self.latencies_ms if latency > self.config.foreground_slo_ms)
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
        )


def make_policy(name: str, config: SimulationConfig) -> SimulationPolicy:
    if name == "RemoteOnly":
        return RemoteOnlyPolicy()
    if name == "ProducerLocal":
        return ProducerLocalPolicy()
    if name == "NodeLRU":
        return NodeLRUPolicy()
    if name == "SizeAwareLRU":
        return SizeAwareLRUPolicy()
    if name == "NodeLFU":
        return NodeLFUPolicy()
    if name == "StaticNReplica":
        return StaticNReplicaPolicy(n=2)
    if name == "AffinityOnly":
        return AffinityOnlyPolicy()
    if name == "WeightedScoreBaseline":
        return WeightedScoreBaselinePolicy()
    if name == "EWMAReplacement":
        return EWMAReplacementPolicy()
    if name == "SourceAwareReplacement":
        return SourceAwareReplacementPolicy()
    if name == "PrefixSourceAwareReplacement":
        return PrefixSourceAwareReplacementPolicy()
    if name == "IndependentControllers":
        return IndependentControllersPolicy()
    if name == "OracleDemand":
        return OracleDemandPolicy()
    if name == "ExhaustiveOptimal":
        return ExhaustiveOptimalPolicy()
    if name == "AURA-KV":
        return AuraKVPolicy(
            duplicate_budget_bytes=config.duplicate_budget_mib * MIB,
            node_duplicate_budget_bytes=config.node_duplicate_budget_mib * MIB,
        )
    raise ValueError(f"unknown policy: {name}")


POLICIES = [
    "RemoteOnly",
    "ProducerLocal",
    "NodeLRU",
    "NodeLFU",
    "SizeAwareLRU",
    "WeightedScoreBaseline",
    "EWMAReplacement",
    "SourceAwareReplacement",
    "PrefixSourceAwareReplacement",
    "StaticNReplica",
    "AffinityOnly",
    "IndependentControllers",
    "AURA-KV",
    "OracleDemand",
    "ExhaustiveOptimal",
]


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
