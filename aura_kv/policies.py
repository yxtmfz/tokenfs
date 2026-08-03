from __future__ import annotations

from dataclasses import dataclass, field
from math import log

from .core import (
    AccessEvent,
    AlternativeSource,
    CacheAction,
    CacheObject,
    Decision,
    NodeState,
    SharedState,
)
from .cost_model import SourceCostModel
from .demand import DemandEstimator, EWMADemandEstimator, GammaPoissonDemandEstimator, OracleDemandEstimator
from .layout import LayoutCostEvaluator
from .optimization import LayoutConstraints


@dataclass
class ResourcePrices:
    lambda_capacity: dict[str, float] = field(default_factory=dict)
    lambda_duplicate: float = 0.0
    lambda_background_bw: dict[str, float] = field(default_factory=dict)
    lambda_slo: float = 0.0
    eta_capacity: float = 0.10
    eta_duplicate: float = 0.10
    eta_slo: float = 0.10
    capacity_target: float = 0.80
    duplicate_target: float = 0.20
    target_p99_ms: float = 10.0

    def update(self, nodes: dict[str, NodeState], duplicate_bytes: int, observed_p99_ms: float) -> None:
        total_capacity = sum(node.local_capacity_bytes for node in nodes.values()) or 1
        for node_id, node in nodes.items():
            used_ratio = node.local_used_bytes / max(1, node.local_capacity_bytes)
            current = self.lambda_capacity.get(node_id, 0.0)
            self.lambda_capacity[node_id] = max(
                0.0, current + self.eta_capacity * (used_ratio - self.capacity_target)
            )
        duplicate_ratio = duplicate_bytes / total_capacity
        self.lambda_duplicate = max(
            0.0, self.lambda_duplicate + self.eta_duplicate * (duplicate_ratio - self.duplicate_target)
        )
        self.lambda_slo = max(
            0.0, self.lambda_slo + self.eta_slo * (observed_p99_ms - self.target_p99_ms)
        )


@dataclass
class SharednessClassifier:
    min_access_samples: int = 5
    private_dominance_enter: float = 0.92
    cluster_shared_entropy_enter: float = 0.60
    min_cross_node_accesses: int = 4

    def classify(self, cache: CacheObject, access_counts: dict[str, float], total_samples: int) -> tuple[SharedState, dict[str, float]]:
        if not cache.sharing_allowed:
            return SharedState.FORCED_PRIVATE, {"reason": 1.0}
        total = sum(access_counts.values())
        active = sum(1 for value in access_counts.values() if value > 0)
        if total_samples < self.min_access_samples or total <= 0:
            return SharedState.PROVISIONAL_PRIVATE, {"samples": float(total_samples)}
        max_ratio = max(access_counts.values()) / total
        entropy = 0.0
        if active > 1:
            entropy = -sum((value / total) * log(value / total) for value in access_counts.values() if value > 0)
            entropy /= log(active)
        cross_node_accesses = total - max(access_counts.values())
        metrics = {
            "dominance": max_ratio,
            "sharedness_entropy": entropy,
            "active_node_count": float(active),
            "cross_node_accesses": cross_node_accesses,
        }
        if active >= 2 and entropy >= self.cluster_shared_entropy_enter and cross_node_accesses >= self.min_cross_node_accesses:
            return SharedState.CLUSTER_SHARED, metrics
        if max_ratio >= self.private_dominance_enter:
            return SharedState.GPU_PRIVATE, metrics
        if active == 1:
            return SharedState.GPU_PRIVATE, metrics
        return SharedState.NODE_SHARED if active == 1 else SharedState.CLUSTER_SHARED, metrics


class AlternativeSourceResolver:
    def resolve(self, cache_key: str, node_id: str, nodes: dict[str, NodeState], has_remote: bool, recomputable: bool) -> AlternativeSource:
        node = nodes[node_id]
        if node.has_replica(cache_key):
            return AlternativeSource.SAME_NODE_REPLICA
        if any(other.node_id != node_id and other.has_replica(cache_key) for other in nodes.values()):
            return AlternativeSource.PEER_NODE_REPLICA
        if has_remote:
            return AlternativeSource.REMOTE_NVME_OF
        if recomputable:
            return AlternativeSource.RECOMPUTE
        return AlternativeSource.NONE

    @staticmethod
    def penalty_ms(source: AlternativeSource, remote_p99_ms: float, peer_p99_ms: float, recompute_ms: float) -> float:
        if source in {AlternativeSource.SAME_NODE_REPLICA, AlternativeSource.LOCAL_OTHER_TIER}:
            return 0.08
        if source == AlternativeSource.PEER_NODE_REPLICA:
            return peer_p99_ms
        if source == AlternativeSource.REMOTE_NVME_OF:
            return remote_p99_ms
        if source == AlternativeSource.RECOMPUTE:
            return recompute_ms
        return float("inf")


class SimulationPolicy:
    name = "Base"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        raise NotImplementedError

    def after_access(self, sim: "TraceSimulator", event: AccessEvent) -> None:
        return None


class RemoteOnlyPolicy(SimulationPolicy):
    name = "RemoteOnly"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        return "remote", [Decision(event.cache_key, event.node_id, CacheAction.DEFER, AlternativeSource.REMOTE_NVME_OF, "remote-only baseline")]


class ProducerLocalPolicy(SimulationPolicy):
    name = "ProducerLocal"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        cache = sim.caches[event.cache_key]
        node = sim.nodes[event.node_id]
        producer = sim.nodes[cache.producer_node_id]
        if node.has_replica(event.cache_key):
            return "local", []
        if event.node_id == cache.producer_node_id:
            sim.ensure_space_and_add(producer.node_id, cache, "producer local")
            return "local" if producer.has_replica(event.cache_key) else "remote", []
        return "remote" if sim.remote_has(event.cache_key) else "recompute", []


class NodeLRUPolicy(SimulationPolicy):
    name = "NodeLRU"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        cache = sim.caches[event.cache_key]
        node = sim.nodes[event.node_id]
        if node.has_replica(event.cache_key):
            node.lru_clock[event.cache_key] = event.timestamp
            return "local", []
        sim.ensure_space_and_add(event.node_id, cache, "lru fill", evict="lru")
        node.lru_clock[event.cache_key] = event.timestamp
        return "remote", []


class SizeAwareLRUPolicy(SimulationPolicy):
    name = "SizeAwareLRU"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        cache = sim.caches[event.cache_key]
        node = sim.nodes[event.node_id]
        if node.has_replica(event.cache_key):
            node.lru_clock[event.cache_key] = event.timestamp
            return "local", []
        sim.ensure_space_and_add(event.node_id, cache, "size-aware lru fill", evict="size_aware_lru")
        node.lru_clock[event.cache_key] = event.timestamp
        return "remote", []


class NodeLFUPolicy(SimulationPolicy):
    name = "NodeLFU"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        cache = sim.caches[event.cache_key]
        node = sim.nodes[event.node_id]
        node.lfu_count[event.cache_key] = node.lfu_count.get(event.cache_key, 0) + 1
        if node.has_replica(event.cache_key):
            return "local", []
        sim.ensure_space_and_add(event.node_id, cache, "lfu fill", evict="lfu")
        return "remote", []


@dataclass
class StaticNReplicaPolicy(SimulationPolicy):
    n: int = 2
    name: str = "StaticNReplica"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        cache = sim.caches[event.cache_key]
        if sim.nodes[event.node_id].has_replica(event.cache_key):
            return "local", []
        ranked = sorted(sim.nodes)
        for node_id in ranked[: self.n]:
            sim.ensure_space_and_add(node_id, cache, "static replica")
        return ("local" if sim.nodes[event.node_id].has_replica(event.cache_key) else "remote"), []


class AffinityOnlyPolicy(SimulationPolicy):
    name = "AffinityOnly"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        cache = sim.caches[event.cache_key]
        if sim.nodes[event.node_id].has_replica(event.cache_key):
            return "local", []
        counts = sim.access_graph.get(event.cache_key, {})
        total = sum(counts.values())
        node_ratio = counts.get(event.node_id, 0.0) / total if total else 0.0
        if node_ratio >= 0.45 and total >= 3:
            sim.ensure_space_and_add(event.node_id, cache, "affinity replica")
        return ("local" if sim.nodes[event.node_id].has_replica(event.cache_key) else "remote"), []


class SourceAwareReplacementPolicy(SimulationPolicy):
    name = "SourceAwareReplacement"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        cache = sim.caches[event.cache_key]
        node = sim.nodes[event.node_id]
        if node.has_replica(event.cache_key):
            return "local", []
        source = sim.source_resolver.resolve(event.cache_key, event.node_id, sim.nodes, sim.remote_has(event.cache_key), cache.recompute_cost_ms > 0)
        penalty = sim.source_resolver.penalty_ms(source, sim.remote_p99_ms, sim.peer_p99_ms, cache.recompute_cost_ms)
        benefit_density = penalty / max(1.0, cache.size_bytes / (1024 * 1024))
        if benefit_density > 0.15:
            sim.ensure_space_and_add(event.node_id, cache, "alternative-aware fill", evict="value")
        return ("local" if node.has_replica(event.cache_key) else source.value.lower()), [
            Decision(event.cache_key, event.node_id, CacheAction.PROMOTE, source, "alternative penalty based decision", benefit=penalty)
        ]


@dataclass
class WeightedScoreBaselinePolicy(SimulationPolicy):
    name: str = "WeightedScoreBaseline"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        cache = sim.caches[event.cache_key]
        node = sim.nodes[event.node_id]
        if node.has_replica(event.cache_key):
            return "local", []
        reads = sim.access_graph.get(event.cache_key, {}).get(event.node_id, 0.0)
        score = 0.30 * reads + 0.30 * min(cache.recompute_cost_ms, 100.0) / 100.0 - 0.20 * cache.size_bytes / (64 * 1024 * 1024)
        if score > 0.2:
            sim.ensure_space_and_add(event.node_id, cache, "weighted-score fill", evict="value")
        return ("local" if node.has_replica(event.cache_key) else "remote"), []


@dataclass
class EWMAReplacementPolicy(SimulationPolicy):
    estimator: DemandEstimator = field(default_factory=EWMADemandEstimator)
    name: str = "EWMAReplacement"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        cache = sim.caches[event.cache_key]
        node = sim.nodes[event.node_id]
        if node.has_replica(event.cache_key):
            return "local", []
        demand = self.estimator.estimate(event.cache_key, event.node_id, event.timestamp, sim.config.demand_horizon_seconds)
        if demand.lower >= 0.25:
            sim.ensure_space_and_add(event.node_id, cache, "ewma demand fill", evict="value")
        return ("local" if node.has_replica(event.cache_key) else "remote"), []

    def after_access(self, sim: "TraceSimulator", event: AccessEvent) -> None:
        self.estimator.observe(event)


class PrefixSourceAwareReplacementPolicy(SourceAwareReplacementPolicy):
    name = "PrefixSourceAwareReplacement"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        source, decisions = super().on_access(sim, event)
        cache = sim.caches[event.cache_key]
        if cache.parent_cache_key and not sim.nodes[event.node_id].has_replica(cache.parent_cache_key):
            parent = sim.caches.get(cache.parent_cache_key)
            if parent is not None:
                sim.ensure_space_and_add(event.node_id, parent, "effective prefix demand", evict="value")
        return source, decisions


@dataclass
class OracleDemandPolicy(EWMAReplacementPolicy):
    estimator: OracleDemandEstimator = field(default_factory=OracleDemandEstimator)
    name: str = "OracleDemand"

    def set_future_trace(self, trace: list[AccessEvent]) -> None:
        self.estimator.future_trace = trace


class ExhaustiveOptimalPolicy(SimulationPolicy):
    name = "ExhaustiveOptimal"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        # Small-scale oracle baseline: greedily keep the currently requested cache if it fits.
        cache = sim.caches[event.cache_key]
        if sim.nodes[event.node_id].has_replica(event.cache_key):
            return "local", []
        sim.ensure_space_and_add(event.node_id, cache, "small exhaustive optimal proxy", evict="value")
        return ("local" if sim.nodes[event.node_id].has_replica(event.cache_key) else "remote"), []


class IndependentControllersPolicy(SimulationPolicy):
    name = "IndependentControllers"

    def __init__(self) -> None:
        self.replacement = EWMAReplacementPolicy()
        self.replication = AffinityOnlyPolicy()

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        source, decisions = self.replacement.on_access(sim, event)
        self.replication.on_access(sim, event)
        return source, decisions

    def after_access(self, sim: "TraceSimulator", event: AccessEvent) -> None:
        self.replacement.after_access(sim, event)


@dataclass
class AuraKVPolicy(SimulationPolicy):
    demand_estimator: DemandEstimator = field(default_factory=GammaPoissonDemandEstimator)
    classifier: SharednessClassifier = field(default_factory=SharednessClassifier)
    prices: ResourcePrices = field(default_factory=ResourcePrices)
    duplicate_budget_bytes: int = 128 * 1024 * 1024
    node_duplicate_budget_bytes: int = 64 * 1024 * 1024
    minimum_layout_improvement_ms: float = 1.0
    cost_model: SourceCostModel = field(default_factory=SourceCostModel)
    name: str = "AURA-KV"

    def on_access(self, sim: "TraceSimulator", event: AccessEvent) -> tuple[str, list[Decision]]:
        cache = sim.caches[event.cache_key]
        node = sim.nodes[event.node_id]
        decisions: list[Decision] = []
        if node.has_replica(event.cache_key):
            return "local", decisions

        counts = sim.access_graph.get(event.cache_key, {})
        state, shared_metrics = self.classifier.classify(cache, counts, int(sum(counts.values())))
        cache.state = state
        evaluator = LayoutCostEvaluator(
            cost_model=self.cost_model,
            demand_estimator=self.demand_estimator,
            minimum_layout_improvement_ms=self.minimum_layout_improvement_ms,
        )
        source_result = self.cost_model.best_source(cache, event.node_id, sim.nodes, sim.remote_has(event.cache_key), now=event.timestamp)
        source = self.cost_model.to_alternative_source(source_result.best)
        gain = evaluator.replica_gain(cache, event.node_id, sim.nodes, sim.remote_has(event.cache_key), event.timestamp, sim.config.demand_horizon_seconds)
        can_share = state in {SharedState.CLUSTER_SHARED, SharedState.NODE_SHARED, SharedState.GPU_PRIVATE}
        constraints = LayoutConstraints(
            global_duplicate_budget_bytes=self.duplicate_budget_bytes,
            node_duplicate_budget_bytes=self.node_duplicate_budget_bytes,
            foreground_slo_gate=sim.p99_latency() >= sim.config.foreground_slo_ms * 0.95 if sim.latencies_ms else False,
        )
        add_constraints = constraints.can_add(cache, node, sim.nodes)
        if source == AlternativeSource.NONE:
            action = CacheAction.PIN
            reason = "no safe alternative source"
        elif can_share and gain.allowed and gain.gain_ms > self.minimum_layout_improvement_ms and add_constraints.allowed:
            action = CacheAction.REPLICATE
            reason = f"replica gain {gain.gain_ms:.3f} ms, state={state.value}"
            sim.ensure_space_and_add(event.node_id, cache, reason, evict="value")
        elif gain.allowed and gain.gain_density_ms_per_mib > 0.05 and add_constraints.allowed:
            action = CacheAction.PROMOTE
            reason = f"local gain density {gain.gain_density_ms_per_mib:.3f} ms/MiB"
            sim.ensure_space_and_add(event.node_id, cache, reason, evict="value")
        else:
            action = CacheAction.DEFER
            reason = f"{gain.reason}; constraints={add_constraints.checks}"
        decisions.append(
            Decision(
                cache_key=event.cache_key,
                node_id=event.node_id,
                action=action,
                alternative_source=source,
                reason=reason,
                benefit=gain.gain_ms,
                cost=gain.ready_delay_ms,
                confidence=1.0,
            )
        )
        return ("local" if node.has_replica(event.cache_key) else source.value.lower()), decisions

    def after_access(self, sim: "TraceSimulator", event: AccessEvent) -> None:
        self.demand_estimator.observe(event)
        if len(sim.latencies_ms) >= 20:
            self.prices.update(sim.nodes, sim.duplicate_bytes, sim.p99_latency())
