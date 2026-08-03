from __future__ import annotations

from dataclasses import dataclass, field

from .core import CacheObject, NodeState
from .cost_model import BestSourceResult, SourceCostModel
from .demand import DemandEstimate, DemandEstimator


MIB = 1024 * 1024


@dataclass
class LayoutBreakdown:
    cache_key: str
    node_id: str
    demand: DemandEstimate
    before: BestSourceResult
    after: BestSourceResult
    delta_ms_per_access: float
    contribution_ms: float


@dataclass
class EvictionLossResult:
    cache_key: str
    node_id: str
    loss_ms: float
    loss_density_ms_per_mib: float
    allowed: bool
    reason: str
    breakdown: list[LayoutBreakdown] = field(default_factory=list)


@dataclass
class ReplicaGainResult:
    cache_key: str
    node_id: str
    gain_ms: float
    gain_density_ms_per_mib: float
    ready_delay_ms: float
    remaining_horizon_seconds: float
    allowed: bool
    reason: str
    breakdown: list[LayoutBreakdown] = field(default_factory=list)


@dataclass
class RobustBenefitResult:
    action: str
    benefit_ms: float
    allowed: bool
    reason: str
    positive_ms: float = 0.0
    negative_ms: float = 0.0
    constraints: dict[str, bool] = field(default_factory=dict)
    breakdown: list[LayoutBreakdown] = field(default_factory=list)


def _source_total(result: BestSourceResult) -> float:
    if result.best is None:
        return float("inf")
    return result.best.total_ms


@dataclass
class LayoutCostEvaluator:
    cost_model: SourceCostModel
    demand_estimator: DemandEstimator
    minimum_layout_improvement_ms: float = 1.0
    copy_queue_delay_ms: float = 0.0
    available_background_bandwidth_bytes_per_s: float = 800 * MIB
    verification_ms_per_mib: float = 0.01
    metadata_commit_ms: float = 0.2

    def ready_delay_ms(self, cache: CacheObject) -> float:
        copy_ms = self.cost_model.remote_source(cache).total_ms
        transfer_ms = (cache.size_bytes / max(1.0, self.available_background_bandwidth_bytes_per_s)) * 1000.0
        verify_ms = (cache.size_bytes / MIB) * self.verification_ms_per_mib
        return self.copy_queue_delay_ms + copy_ms + transfer_ms + verify_ms + self.metadata_commit_ms

    def eviction_loss(
        self,
        cache: CacheObject,
        node_id: str,
        nodes: dict[str, NodeState],
        has_remote: bool,
        now: float,
        horizon_seconds: float,
    ) -> EvictionLossResult:
        if not nodes[node_id].has_replica(cache.identity.cache_key):
            return EvictionLossResult(cache.identity.cache_key, node_id, 0.0, 0.0, False, "replica is not READY on node")
        total_loss = 0.0
        rows: list[LayoutBreakdown] = []
        for request_node_id in nodes:
            demand = self.demand_estimator.estimate(cache.identity.cache_key, request_node_id, now, horizon_seconds)
            before = self.cost_model.best_source(cache, request_node_id, nodes, has_remote, now=now)
            after = self.cost_model.best_source(
                cache,
                request_node_id,
                nodes,
                has_remote,
                now=now,
                removed_replica=(cache.identity.cache_key, node_id),
            )
            if after.best is None:
                return EvictionLossResult(
                    cache.identity.cache_key,
                    node_id,
                    float("inf"),
                    float("inf"),
                    False,
                    "deleting would leave no reliable source",
                    rows,
                )
            delta = max(_source_total(after) - _source_total(before), 0.0)
            contribution = demand.upper * delta
            total_loss += contribution
            rows.append(LayoutBreakdown(cache.identity.cache_key, request_node_id, demand, before, after, delta, contribution))
        density = total_loss / max(1.0, cache.size_bytes / MIB)
        return EvictionLossResult(cache.identity.cache_key, node_id, total_loss, density, True, "safe candidate", rows)

    def replica_gain(
        self,
        cache: CacheObject,
        node_id: str,
        nodes: dict[str, NodeState],
        has_remote: bool,
        now: float,
        horizon_seconds: float,
    ) -> ReplicaGainResult:
        if nodes[node_id].has_replica(cache.identity.cache_key):
            return ReplicaGainResult(cache.identity.cache_key, node_id, 0.0, 0.0, 0.0, horizon_seconds, False, "replica already exists")
        ready_ms = self.ready_delay_ms(cache)
        remaining = max(horizon_seconds - ready_ms / 1000.0, 0.0)
        if remaining <= 0:
            return ReplicaGainResult(cache.identity.cache_key, node_id, 0.0, 0.0, ready_ms, 0.0, False, "replica would be ready after horizon")
        total_gain = 0.0
        rows: list[LayoutBreakdown] = []
        for request_node_id in nodes:
            demand = self.demand_estimator.estimate(cache.identity.cache_key, request_node_id, now, remaining)
            before = self.cost_model.best_source(cache, request_node_id, nodes, has_remote, now=now)
            after = self.cost_model.best_source(
                cache,
                request_node_id,
                nodes,
                has_remote,
                now=now,
                extra_replica=(cache.identity.cache_key, node_id),
            )
            delta = max(_source_total(before) - _source_total(after), 0.0)
            contribution = demand.lower * delta
            total_gain += contribution
            rows.append(LayoutBreakdown(cache.identity.cache_key, request_node_id, demand, before, after, delta, contribution))
        density = total_gain / max(1.0, cache.size_bytes / MIB)
        return ReplicaGainResult(
            cache.identity.cache_key,
            node_id,
            total_gain,
            density,
            ready_ms,
            remaining,
            total_gain > 0.0,
            "positive robust gain" if total_gain > 0.0 else "no conservative gain",
            rows,
        )

    def robust_benefit_for_add(
        self,
        cache: CacheObject,
        node_id: str,
        nodes: dict[str, NodeState],
        has_remote: bool,
        now: float,
        horizon_seconds: float,
    ) -> RobustBenefitResult:
        gain = self.replica_gain(cache, node_id, nodes, has_remote, now, horizon_seconds)
        allowed = gain.allowed and gain.gain_ms > self.minimum_layout_improvement_ms
        return RobustBenefitResult(
            action="ADD",
            benefit_ms=gain.gain_ms,
            allowed=allowed,
            reason=gain.reason if allowed else f"{gain.reason}; below minimum improvement",
            positive_ms=gain.gain_ms,
            constraints={"ready_before_horizon": gain.remaining_horizon_seconds > 0},
            breakdown=gain.breakdown,
        )

    def robust_benefit_for_remove(
        self,
        cache: CacheObject,
        node_id: str,
        nodes: dict[str, NodeState],
        has_remote: bool,
        now: float,
        horizon_seconds: float,
    ) -> RobustBenefitResult:
        loss = self.eviction_loss(cache, node_id, nodes, has_remote, now, horizon_seconds)
        allowed = loss.allowed and loss.loss_ms < self.minimum_layout_improvement_ms
        return RobustBenefitResult(
            action="REMOVE",
            benefit_ms=-loss.loss_ms,
            allowed=allowed,
            reason="safe low-loss removal" if allowed else loss.reason,
            negative_ms=loss.loss_ms,
            constraints={"has_reliable_source_after_remove": loss.allowed},
            breakdown=loss.breakdown,
        )
