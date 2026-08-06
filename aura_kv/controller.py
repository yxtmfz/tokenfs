from __future__ import annotations

import time
from dataclasses import dataclass, field

from .core import AccessEvent, CacheObject, NodeState
from .layout import LayoutCostEvaluator
from .optimization import LayoutConstraints
from .tasks import BackgroundTask, TaskType


@dataclass
class ActionPlan:
    layout_version: int
    tasks: list[BackgroundTask] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)


class AuraController:
    """Builds background task plans from foreground access events.

    The controller is deliberately separated from task execution. Foreground
    access only records demand and asks for a plan; the durable queue/executor
    performs copying or deletion later.
    """

    def __init__(
        self,
        evaluator: LayoutCostEvaluator,
        constraints: LayoutConstraints,
        horizon_seconds: float = 300.0,
    ) -> None:
        self.evaluator = evaluator
        self.constraints = constraints
        self.horizon_seconds = horizon_seconds

    def plan_from_accesses(
        self,
        events: list[AccessEvent],
        caches: dict[str, CacheObject],
        nodes: dict[str, NodeState],
        has_remote: bool,
        layout_version: int,
        now: float | None = None,
    ) -> ActionPlan:
        current_time = time.time() if now is None else now
        plan = ActionPlan(layout_version)
        for event in events:
            cache = caches.get(event.cache_key)
            node = nodes.get(event.node_id)
            if cache is None or node is None:
                plan.rejected.append(f"{event.cache_key}@{event.node_id}: unknown cache or node")
                continue
            self.evaluator.demand_estimator.observe(event)
            if node.has_replica(cache.identity.cache_key):
                continue

            add = self.evaluator.robust_benefit_for_add(cache, event.node_id, nodes, has_remote, current_time, self.horizon_seconds)
            add_constraint = self.constraints.can_add(cache, node, nodes)
            if add.allowed and add_constraint.allowed:
                plan.tasks.append(
                    BackgroundTask(
                        action_type=TaskType.PROMOTE if event.foreground else TaskType.PREFETCH,
                        cache_key=cache.identity.cache_key,
                        source="remote",
                        target=event.node_id,
                        layout_version=layout_version,
                        reserved_bytes=cache.size_bytes,
                        expected_benefit_ms=add.benefit_ms,
                    )
                )
                continue

            victim = self._choose_swap_victim(cache, event.node_id, caches, nodes, has_remote, current_time, add.benefit_ms)
            if victim is None:
                plan.rejected.append(
                    f"{cache.identity.cache_key}@{event.node_id}: add rejected ({add.reason}; {add_constraint.reason})"
                )
                continue
            victim_cache, victim_loss = victim
            replicate = BackgroundTask(
                action_type=TaskType.REPLICATE,
                cache_key=cache.identity.cache_key,
                source="remote",
                target=event.node_id,
                layout_version=layout_version,
                reserved_bytes=cache.size_bytes,
                expected_benefit_ms=add.benefit_ms,
            )
            evict = BackgroundTask(
                action_type=TaskType.EVICT,
                cache_key=victim_cache.identity.cache_key,
                source=f"node:{event.node_id}",
                target=event.node_id,
                layout_version=layout_version,
                expected_benefit_ms=-victim_loss,
                dependency_task_ids=[replicate.task_id],
            )
            swap = BackgroundTask(
                action_type=TaskType.SWAP,
                cache_key=f"{cache.identity.cache_key}<->{victim_cache.identity.cache_key}",
                source=replicate.task_id,
                target=evict.task_id,
                layout_version=layout_version,
                expected_benefit_ms=add.benefit_ms - victim_loss,
                dependency_task_ids=[replicate.task_id, evict.task_id],
            )
            plan.tasks.extend([replicate, evict, swap])
        return plan

    def _choose_swap_victim(
        self,
        incoming: CacheObject,
        node_id: str,
        caches: dict[str, CacheObject],
        nodes: dict[str, NodeState],
        has_remote: bool,
        now: float,
        incoming_gain_ms: float,
    ) -> tuple[CacheObject, float] | None:
        node = nodes[node_id]
        best: tuple[CacheObject, float] | None = None
        for victim_key in list(node.replicas):
            victim_cache = caches.get(victim_key)
            if victim_cache is None:
                continue
            remove_constraint = self.constraints.can_remove(victim_key, node, now)
            if not remove_constraint.allowed:
                continue
            loss = self.evaluator.eviction_loss(victim_cache, node_id, nodes, has_remote, now, self.horizon_seconds)
            if not loss.allowed:
                continue
            frees_enough = node.local_used_bytes - victim_cache.size_bytes + incoming.size_bytes <= node.local_capacity_bytes
            net_positive = incoming_gain_ms - loss.loss_ms > self.evaluator.minimum_layout_improvement_ms
            if not frees_enough or not net_positive:
                continue
            if best is None or loss.loss_ms < best[1]:
                best = (victim_cache, loss.loss_ms)
        return best
