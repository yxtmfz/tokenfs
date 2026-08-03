from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol


class AlternativeSource(str, Enum):
    LOCAL_OTHER_TIER = "LOCAL_OTHER_TIER"
    SAME_NODE_REPLICA = "SAME_NODE_REPLICA"
    PEER_NODE_REPLICA = "PEER_NODE_REPLICA"
    REMOTE_NVME_OF = "REMOTE_NVME_OF"
    RECOMPUTE = "RECOMPUTE"
    NONE = "NONE"


class CacheAction(str, Enum):
    KEEP = "KEEP"
    PROMOTE = "PROMOTE"
    REPLICATE = "REPLICATE"
    DEMOTE = "DEMOTE"
    EVICT_LOCAL = "EVICT_LOCAL"
    DROP_RECOMPUTABLE = "DROP_RECOMPUTABLE"
    PIN = "PIN"
    PREFETCH = "PREFETCH"
    DEFER = "DEFER"


class SharedState(str, Enum):
    PROVISIONAL_PRIVATE = "PROVISIONAL_PRIVATE"
    GPU_PRIVATE = "GPU_PRIVATE"
    NODE_SHARED = "NODE_SHARED"
    CLUSTER_SHARED = "CLUSTER_SHARED"
    COOLING = "COOLING"
    COLD = "COLD"
    FORCED_PRIVATE = "FORCED_PRIVATE"


class ReplicaStatus(str, Enum):
    RESERVED = "RESERVED"
    COPYING = "COPYING"
    VERIFYING = "VERIFYING"
    READY = "READY"
    EXPIRED = "EXPIRED"
    DELETING = "DELETING"
    FAILED = "FAILED"


@dataclass(frozen=True)
class CacheIdentity:
    cache_key: str
    sharing_domain: str = "default"
    model_id: str = "unknown-model"
    model_version: str = "unknown-version"
    tokenizer_version: str = "unknown-tokenizer"
    token_prefix_hash: str = ""
    lora_adapter: str = ""
    kv_dtype: str = "fp16"
    layer_range: str = "all"
    position_encoding: str = "default"
    tensor_parallel: str = "tp1"
    pipeline_parallel: str = "pp1"
    cache_schema_version: str = "v1"
    tenant_id: str = "default"

    @property
    def share_safe_key(self) -> tuple[str, ...]:
        return (
            self.sharing_domain,
            self.model_id,
            self.model_version,
            self.tokenizer_version,
            self.token_prefix_hash,
            self.lora_adapter,
            self.kv_dtype,
            self.layer_range,
            self.position_encoding,
            self.tensor_parallel,
            self.pipeline_parallel,
            self.cache_schema_version,
            self.tenant_id,
        )


@dataclass
class CacheObject:
    identity: CacheIdentity
    producer_node_id: str
    producer_gpu_id: int
    size_bytes: int
    token_count: int = 0
    recompute_cost_ms: float = 0.0
    parent_cache_key: str = ""
    sharing_allowed: bool = True
    checksum: str = ""
    created_at: float = 0.0
    last_access_at: float = 0.0
    state: SharedState = SharedState.PROVISIONAL_PRIVATE


@dataclass
class AccessEvent:
    timestamp: float
    request_id: str
    tenant_id: str
    cache_key: str
    parent_cache_key: str
    node_id: str
    gpu_id: int
    operation: str
    bytes: int
    token_count: int
    foreground: bool
    recompute_cost_ms: float
    sharing_domain: str = "default"
    model_id: str = "llm"
    token_prefix_hash: str = ""


@dataclass
class Replica:
    cache_key: str
    node_id: str
    status: ReplicaStatus = ReplicaStatus.READY
    size_bytes: int = 0
    lease_expire_at: float = 0.0
    last_hit_at: float = 0.0
    utility_at_creation: float = 0.0
    latest_utility: float = 0.0
    pin_count: int = 0
    version: int = 1


@dataclass
class NodeState:
    node_id: str
    local_capacity_bytes: int
    local_used_bytes: int = 0
    replicas: dict[str, Replica] = field(default_factory=dict)
    lru_clock: dict[str, float] = field(default_factory=dict)
    lfu_count: dict[str, int] = field(default_factory=dict)

    def has_replica(self, cache_key: str) -> bool:
        replica = self.replicas.get(cache_key)
        return replica is not None and replica.status == ReplicaStatus.READY

    def can_fit(self, size_bytes: int) -> bool:
        return self.local_used_bytes + size_bytes <= self.local_capacity_bytes

    def add_replica(self, replica: Replica) -> bool:
        if self.has_replica(replica.cache_key):
            return True
        if not self.can_fit(replica.size_bytes):
            return False
        self.replicas[replica.cache_key] = replica
        self.local_used_bytes += replica.size_bytes
        return True

    def remove_replica(self, cache_key: str) -> Replica | None:
        replica = self.replicas.pop(cache_key, None)
        if replica is not None:
            self.local_used_bytes = max(0, self.local_used_bytes - replica.size_bytes)
            self.lru_clock.pop(cache_key, None)
            self.lfu_count.pop(cache_key, None)
        return replica


@dataclass
class Prediction:
    future_hits_by_node: dict[str, float]
    next_access_seconds: float
    cold_probability: float
    confidence: float
    cross_node_sharedness: float = 0.0


@dataclass
class Decision:
    cache_key: str
    node_id: str
    action: CacheAction
    alternative_source: AlternativeSource
    reason: str
    benefit: float = 0.0
    cost: float = 0.0
    confidence: float = 1.0


class StorageBackend(Protocol):
    def put(self, key: str, src: Path) -> None: ...

    def get(self, key: str, dst: Path) -> None: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def stat(self, key: str) -> int: ...

    def free_space(self) -> int: ...

    def checksum(self, key: str) -> str: ...

