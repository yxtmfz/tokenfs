from __future__ import annotations

from dataclasses import dataclass, field

from .core import CacheObject, NodeState, ReplicaStatus


@dataclass
class ConstraintResult:
    allowed: bool
    checks: dict[str, bool]
    reason: str = ""


@dataclass
class LayoutConstraints:
    global_duplicate_budget_bytes: int
    node_duplicate_budget_bytes: int
    background_bandwidth_budget_bytes_per_cycle: int = 1024 * 1024 * 1024
    max_concurrent_copy_tasks: int = 2
    minimum_residence_seconds: float = 60.0
    foreground_slo_gate: bool = False
    active_copy_tasks: int = 0
    migration_bytes_this_cycle: int = 0

    def duplicate_bytes(self, nodes: dict[str, NodeState]) -> int:
        return sum(replica.size_bytes for node in nodes.values() for replica in node.replicas.values())

    def node_duplicate_bytes(self, node: NodeState) -> int:
        return sum(replica.size_bytes for replica in node.replicas.values())

    def can_add(
        self,
        cache: CacheObject,
        node: NodeState,
        nodes: dict[str, NodeState],
        *,
        require_sharing_allowed: bool = True,
    ) -> ConstraintResult:
        checks = {
            "node_capacity": node.local_used_bytes + cache.size_bytes <= node.local_capacity_bytes,
            "global_duplicate_budget": self.duplicate_bytes(nodes) + cache.size_bytes <= self.global_duplicate_budget_bytes,
            "node_duplicate_budget": self.node_duplicate_bytes(node) + cache.size_bytes <= self.node_duplicate_budget_bytes,
            "background_bandwidth": self.migration_bytes_this_cycle + cache.size_bytes <= self.background_bandwidth_budget_bytes_per_cycle,
            "copy_concurrency": self.active_copy_tasks < self.max_concurrent_copy_tasks,
            "foreground_slo_gate": not self.foreground_slo_gate,
            "sharing_allowed": cache.sharing_allowed or not require_sharing_allowed,
        }
        allowed = all(checks.values())
        return ConstraintResult(allowed, checks, "" if allowed else "add violates hard constraints")

    def can_remove(self, cache_key: str, node: NodeState, now: float) -> ConstraintResult:
        replica = node.replicas.get(cache_key)
        checks = {
            "replica_exists": replica is not None,
            "replica_ready": replica is not None and replica.status == ReplicaStatus.READY,
            "not_pinned": replica is not None and replica.pin_count == 0,
            "minimum_residence": replica is not None and now - replica.last_hit_at >= self.minimum_residence_seconds,
        }
        allowed = all(checks.values())
        return ConstraintResult(allowed, checks, "" if allowed else "remove violates hard constraints")


class SafetyGuard:
    def can_delete_low_loss_candidate(self, loss_allowed: bool, constraint: ConstraintResult) -> ConstraintResult:
        checks = dict(constraint.checks)
        checks["reliable_source_after_remove"] = loss_allowed
        allowed = constraint.allowed and loss_allowed
        return ConstraintResult(allowed, checks, "" if allowed else "delete blocked by safety guard")
