from __future__ import annotations

import time
from copy import deepcopy
from dataclasses import dataclass, field

from .core import AccessEvent, CacheObject, NodeState, Replica, ReplicaStatus
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
        # Reserve on a private projected layout: repeated accesses in one batch
        # must not emit duplicate copies or oversubscribe capacity/bandwidth.
        projected_nodes = deepcopy(nodes)
        projected_constraints = deepcopy(self.constraints)
        for event in events:
            cache = caches.get(event.cache_key)
            node = projected_nodes.get(event.node_id)
            if cache is None or node is None:
                plan.rejected.append(f"{event.cache_key}@{event.node_id}: unknown cache or node")
                continue
            self.evaluator.demand_estimator.observe(event)
            if cache.identity.cache_key in node.replicas:
                continue

            add = self.evaluator.robust_benefit_for_add(cache, event.node_id, projected_nodes, has_remote, current_time, self.horizon_seconds)
            add_constraint = projected_constraints.can_add(cache, node, projected_nodes)
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
                node.add_replica(Replica(cache.identity.cache_key, event.node_id,
                                         status=ReplicaStatus.RESERVED, size_bytes=cache.size_bytes))
                projected_constraints.active_copy_tasks += 1
                projected_constraints.migration_bytes_this_cycle += cache.size_bytes
                continue

            # Copy-before-delete needs enough space for both replicas. A victim
            # does not make the temporary copy fit, nor waive sharing/SLO gates.
            # Until staging reservations are implemented, reject explicitly.
            failed_checks = [key for key, allowed in add_constraint.checks.items() if not allowed]
            plan.rejected.append(
                f"{cache.identity.cache_key}@{event.node_id}: add rejected "
                f"({add.reason}; failed constraints={failed_checks}; "
                "copy-before-delete cannot borrow unreserved staging space)"
            )
        return plan
