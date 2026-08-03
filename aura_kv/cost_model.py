from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .core import AlternativeSource, CacheObject, NodeState, ReplicaStatus


MIB = 1024 * 1024


class SourceKind(str, Enum):
    LOCAL = "LOCAL"
    PEER = "PEER"
    REMOTE_NVME_OF = "REMOTE_NVME_OF"
    RECOMPUTE = "RECOMPUTE"


@dataclass(frozen=True)
class SourceCostBreakdown:
    source: SourceKind
    source_node_id: str
    queue_delay_ms: float
    fixed_access_latency_ms: float
    transfer_time_ms: float
    deserialize_cost_ms: float
    format_conversion_cost_ms: float
    host_to_device_transfer_cost_ms: float
    total_ms: float
    reachable: bool = True
    compatible: bool = True
    reason: str = ""


@dataclass(frozen=True)
class BestSourceResult:
    cache_key: str
    request_node_id: str
    best: SourceCostBreakdown | None
    second_best: SourceCostBreakdown | None
    all_sources: list[SourceCostBreakdown]
    metrics_version: int
    updated_at: float


def transfer_time_ms(size_bytes: int, bandwidth_bytes_per_second: float) -> float:
    if bandwidth_bytes_per_second <= 0:
        return float("inf")
    return (size_bytes / bandwidth_bytes_per_second) * 1000.0


@dataclass
class SourceCostModel:
    local_fixed_latency_ms: float = 0.08
    peer_fixed_latency_ms: float = 0.35
    remote_fixed_latency_ms: float = 1.20
    local_bandwidth_bytes_per_s: float = 3500 * MIB
    peer_bandwidth_bytes_per_s: float = 800 * MIB
    remote_bandwidth_bytes_per_s: float = 1200 * MIB
    host_to_device_bandwidth_bytes_per_s: float = 12000 * MIB
    remote_queue_delay_ms: float = 0.0
    peer_queue_delay_ms: float = 0.0
    local_queue_delay_ms: float = 0.0
    deserialize_cost_per_mib_ms: float = 0.0
    format_conversion_cost_per_mib_ms: float = 0.0
    metrics_version: int = 1
    _cache: dict[tuple[str, str, int, tuple[tuple[str, tuple[str, ...]], ...]], BestSourceResult] = field(default_factory=dict)

    def _common_costs(self, cache: CacheObject, fixed_ms: float, queue_ms: float, bandwidth: float) -> tuple[float, float, float, float]:
        size_mib = cache.size_bytes / MIB
        transfer = transfer_time_ms(cache.size_bytes, bandwidth)
        deserialize = size_mib * self.deserialize_cost_per_mib_ms
        convert = size_mib * self.format_conversion_cost_per_mib_ms
        h2d = transfer_time_ms(cache.size_bytes, self.host_to_device_bandwidth_bytes_per_s)
        return transfer, deserialize, convert, queue_ms + fixed_ms + transfer + deserialize + convert + h2d

    def local_source(self, cache: CacheObject, node_id: str) -> SourceCostBreakdown:
        transfer, deserialize, convert, total = self._common_costs(
            cache, self.local_fixed_latency_ms, self.local_queue_delay_ms, self.local_bandwidth_bytes_per_s
        )
        return SourceCostBreakdown(
            source=SourceKind.LOCAL,
            source_node_id=node_id,
            queue_delay_ms=self.local_queue_delay_ms,
            fixed_access_latency_ms=self.local_fixed_latency_ms,
            transfer_time_ms=transfer,
            deserialize_cost_ms=deserialize,
            format_conversion_cost_ms=convert,
            host_to_device_transfer_cost_ms=transfer_time_ms(cache.size_bytes, self.host_to_device_bandwidth_bytes_per_s),
            total_ms=total,
        )

    def peer_source(self, cache: CacheObject, source_node_id: str) -> SourceCostBreakdown:
        transfer, deserialize, convert, total = self._common_costs(
            cache, self.peer_fixed_latency_ms, self.peer_queue_delay_ms, self.peer_bandwidth_bytes_per_s
        )
        return SourceCostBreakdown(
            source=SourceKind.PEER,
            source_node_id=source_node_id,
            queue_delay_ms=self.peer_queue_delay_ms,
            fixed_access_latency_ms=self.peer_fixed_latency_ms,
            transfer_time_ms=transfer,
            deserialize_cost_ms=deserialize,
            format_conversion_cost_ms=convert,
            host_to_device_transfer_cost_ms=transfer_time_ms(cache.size_bytes, self.host_to_device_bandwidth_bytes_per_s),
            total_ms=total,
        )

    def remote_source(self, cache: CacheObject) -> SourceCostBreakdown:
        transfer, deserialize, convert, total = self._common_costs(
            cache, self.remote_fixed_latency_ms, self.remote_queue_delay_ms, self.remote_bandwidth_bytes_per_s
        )
        return SourceCostBreakdown(
            source=SourceKind.REMOTE_NVME_OF,
            source_node_id="remote",
            queue_delay_ms=self.remote_queue_delay_ms,
            fixed_access_latency_ms=self.remote_fixed_latency_ms,
            transfer_time_ms=transfer,
            deserialize_cost_ms=deserialize,
            format_conversion_cost_ms=convert,
            host_to_device_transfer_cost_ms=transfer_time_ms(cache.size_bytes, self.host_to_device_bandwidth_bytes_per_s),
            total_ms=total,
        )

    def recompute_source(self, cache: CacheObject, node_id: str, gpu_queue_delay_ms: float = 0.0) -> SourceCostBreakdown:
        total = gpu_queue_delay_ms + cache.recompute_cost_ms
        return SourceCostBreakdown(
            source=SourceKind.RECOMPUTE,
            source_node_id=node_id,
            queue_delay_ms=gpu_queue_delay_ms,
            fixed_access_latency_ms=0.0,
            transfer_time_ms=0.0,
            deserialize_cost_ms=0.0,
            format_conversion_cost_ms=0.0,
            host_to_device_transfer_cost_ms=0.0,
            total_ms=total,
            reachable=cache.recompute_cost_ms > 0,
            reason="" if cache.recompute_cost_ms > 0 else "not recomputable",
        )

    def compatible_sources(
        self,
        cache: CacheObject,
        request_node_id: str,
        nodes: dict[str, NodeState],
        has_remote: bool,
        extra_replica: tuple[str, str] | None = None,
        removed_replica: tuple[str, str] | None = None,
    ) -> list[SourceCostBreakdown]:
        sources: list[SourceCostBreakdown] = []
        for node_id, node in nodes.items():
            has_replica = node.has_replica(cache.identity.cache_key)
            if extra_replica == (cache.identity.cache_key, node_id):
                has_replica = True
            if removed_replica == (cache.identity.cache_key, node_id):
                has_replica = False
            replica = node.replicas.get(cache.identity.cache_key)
            if replica is not None and replica.status != ReplicaStatus.READY and extra_replica != (cache.identity.cache_key, node_id):
                has_replica = False
            if not has_replica:
                continue
            if node_id == request_node_id:
                sources.append(self.local_source(cache, node_id))
            else:
                sources.append(self.peer_source(cache, node_id))
        if has_remote:
            sources.append(self.remote_source(cache))
        recompute = self.recompute_source(cache, request_node_id)
        if recompute.reachable:
            sources.append(recompute)
        return sources

    def best_source(
        self,
        cache: CacheObject,
        request_node_id: str,
        nodes: dict[str, NodeState],
        has_remote: bool,
        now: float = 0.0,
        extra_replica: tuple[str, str] | None = None,
        removed_replica: tuple[str, str] | None = None,
    ) -> BestSourceResult:
        sources = self.compatible_sources(cache, request_node_id, nodes, has_remote, extra_replica, removed_replica)
        ordered = sorted((src for src in sources if src.reachable and src.compatible), key=lambda src: src.total_ms)
        return BestSourceResult(
            cache_key=cache.identity.cache_key,
            request_node_id=request_node_id,
            best=ordered[0] if ordered else None,
            second_best=ordered[1] if len(ordered) > 1 else None,
            all_sources=sources,
            metrics_version=self.metrics_version,
            updated_at=now,
        )

    @staticmethod
    def to_alternative_source(source: SourceCostBreakdown | None) -> AlternativeSource:
        if source is None:
            return AlternativeSource.NONE
        if source.source == SourceKind.LOCAL:
            return AlternativeSource.SAME_NODE_REPLICA
        if source.source == SourceKind.PEER:
            return AlternativeSource.PEER_NODE_REPLICA
        if source.source == SourceKind.REMOTE_NVME_OF:
            return AlternativeSource.REMOTE_NVME_OF
        if source.source == SourceKind.RECOMPUTE:
            return AlternativeSource.RECOMPUTE
        return AlternativeSource.NONE
