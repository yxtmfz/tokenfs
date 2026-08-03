#!/usr/bin/env python3
from __future__ import annotations

import itertools
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aura_kv.core import AccessEvent, CacheIdentity, NodeState, Replica, ReplicaStatus
from aura_kv.cost_model import SourceCostModel, transfer_time_ms
from aura_kv.demand import EWMADemandEstimator, GammaPoissonDemandEstimator
from aura_kv.layout import LayoutCostEvaluator
from aura_kv.optimization import LayoutConstraints
from aura_kv.policies import SharednessClassifier
from aura_kv.simulator import MIB, POLICIES, SCENARIOS, SimulationConfig, generate_trace, make_cache, run_matrix


class AuraKVUnitTest(unittest.TestCase):
    def test_cache_identity_blocks_cross_domain_sharing(self) -> None:
        a = CacheIdentity(cache_key="same", sharing_domain="tenantA", token_prefix_hash="p")
        b = CacheIdentity(cache_key="same", sharing_domain="tenantB", token_prefix_hash="p")
        self.assertNotEqual(a.share_safe_key, b.share_safe_key)

    def test_transfer_units_are_bytes_per_second_to_ms(self) -> None:
        self.assertAlmostEqual(transfer_time_ms(1024, 1024), 1000.0)
        self.assertAlmostEqual(transfer_time_ms(10 * MIB, 100 * MIB), 100.0)

    def test_ewma_demand_falls_back_with_empty_history(self) -> None:
        estimator = EWMADemandEstimator()
        demand = estimator.estimate("missing", "node0", 100.0, 60.0)
        self.assertEqual(demand.mean, 0.0)
        self.assertEqual(demand.lower, 0.0)
        self.assertGreater(demand.upper, 0.0)

    def test_gamma_poisson_detects_node_demand_and_uncertainty_bounds(self) -> None:
        estimator = GammaPoissonDemandEstimator(a0=1.0, b0=60.0, tau_seconds=60.0, bucket_seconds=10.0)
        for i in range(3):
            estimator.observe(AccessEvent(i * 10.0, f"r{i}", "t", "k", "", "node1", 0, "read", 1024, 1, True, 1.0))
        hot = estimator.estimate("k", "node1", 40.0, 60.0)
        cold = estimator.estimate("k", "node0", 40.0, 60.0)
        self.assertGreater(hot.mean, cold.mean)
        self.assertLessEqual(hot.lower, hot.mean)
        self.assertGreaterEqual(hot.upper, hot.mean)

    def test_prefix_demand_deduplicates_request_id(self) -> None:
        estimator = GammaPoissonDemandEstimator(a0=0.0, b0=60.0, tau_seconds=60.0)
        event = AccessEvent(1.0, "req1", "t", "child", "parent", "node0", 0, "read", 1024, 1, True, 1.0)
        estimator.observe(event)
        estimator.observe(event)
        parent = estimator.estimate("parent", "node0", 2.0, 60.0)
        child = estimator.estimate("child", "node0", 2.0, 60.0)
        self.assertLess(parent.mean, 2.0)
        self.assertAlmostEqual(parent.mean, child.mean)

    def test_best_source_is_not_higher_than_available_sources(self) -> None:
        config = SimulationConfig(local_capacity_mib=64)
        caches, _ = generate_trace("cluster_shared", config)
        cache = caches["common-prefix"]
        nodes = {f"node{i}": NodeState(f"node{i}", 64 * MIB) for i in range(2)}
        nodes["node0"].add_replica(Replica(cache.identity.cache_key, "node0", size_bytes=cache.size_bytes))
        model = SourceCostModel()
        result = model.best_source(cache, "node1", nodes, True)
        self.assertIsNotNone(result.best)
        self.assertLessEqual(result.best.total_ms, min(src.total_ms for src in result.all_sources if src.reachable))

    def test_add_ready_source_does_not_increase_best_cost(self) -> None:
        cache = make_cache("k", "node0", 0, 8, 50)
        nodes = {f"node{i}": NodeState(f"node{i}", 64 * MIB) for i in range(2)}
        model = SourceCostModel(remote_fixed_latency_ms=5.0)
        before = model.best_source(cache, "node0", nodes, True).best.total_ms
        after = model.best_source(cache, "node0", nodes, True, extra_replica=("k", "node0")).best.total_ms
        self.assertLessEqual(after, before)

    def test_remove_source_does_not_lower_frozen_best_cost(self) -> None:
        cache = make_cache("k", "node0", 0, 8, 50)
        nodes = {f"node{i}": NodeState(f"node{i}", 64 * MIB) for i in range(2)}
        nodes["node0"].add_replica(Replica("k", "node0", size_bytes=cache.size_bytes))
        model = SourceCostModel()
        before = model.best_source(cache, "node0", nodes, True).best.total_ms
        after = model.best_source(cache, "node0", nodes, True, removed_replica=("k", "node0")).best.total_ms
        self.assertGreaterEqual(after, before)

    def test_eviction_loss_and_replica_gain_are_non_negative(self) -> None:
        cache = make_cache("k", "node0", 0, 8, 50)
        nodes = {f"node{i}": NodeState(f"node{i}", 64 * MIB) for i in range(2)}
        nodes["node0"].add_replica(Replica("k", "node0", size_bytes=cache.size_bytes, last_hit_at=-1000.0))
        estimator = GammaPoissonDemandEstimator()
        for i in range(5):
            estimator.observe(AccessEvent(i, f"r{i}", "t", "k", "", "node0", 0, "read", 1024, 1, True, 1.0))
        evaluator = LayoutCostEvaluator(SourceCostModel(), estimator)
        loss = evaluator.eviction_loss(cache, "node0", nodes, True, 10.0, 60.0)
        gain = evaluator.replica_gain(cache, "node1", nodes, True, 10.0, 60.0)
        self.assertGreaterEqual(loss.loss_ms, 0.0)
        self.assertGreaterEqual(gain.gain_ms, 0.0)

    def test_no_layout_change_has_zero_robust_benefit(self) -> None:
        cache = make_cache("k", "node0", 0, 8, 50)
        nodes = {"node0": NodeState("node0", 64 * MIB)}
        nodes["node0"].add_replica(Replica("k", "node0", size_bytes=cache.size_bytes))
        evaluator = LayoutCostEvaluator(SourceCostModel(), GammaPoissonDemandEstimator())
        result = evaluator.replica_gain(cache, "node0", nodes, True, 0.0, 60.0)
        self.assertEqual(result.gain_ms, 0.0)

    def test_zero_future_demand_or_ready_after_horizon_has_zero_replica_gain(self) -> None:
        cache = make_cache("k", "node0", 0, 512, 50)
        nodes = {"node0": NodeState("node0", 1024 * MIB)}
        evaluator = LayoutCostEvaluator(
            SourceCostModel(remote_bandwidth_bytes_per_s=1),
            GammaPoissonDemandEstimator(a0=0.0, b0=600.0),
        )
        result = evaluator.replica_gain(cache, "node0", nodes, True, 0.0, 1.0)
        self.assertEqual(result.gain_ms, 0.0)

    def test_delete_without_reliable_source_is_blocked(self) -> None:
        cache = make_cache("k", "node0", 0, 8, 0)
        nodes = {"node0": NodeState("node0", 64 * MIB)}
        nodes["node0"].add_replica(Replica("k", "node0", size_bytes=cache.size_bytes))
        evaluator = LayoutCostEvaluator(SourceCostModel(), GammaPoissonDemandEstimator())
        loss = evaluator.eviction_loss(cache, "node0", nodes, False, 0.0, 60.0)
        self.assertFalse(loss.allowed)
        self.assertEqual(loss.loss_ms, float("inf"))

    def test_same_node_multiple_gpus_share_one_physical_replica(self) -> None:
        config = SimulationConfig(nodes=1, gpus_per_node=2, local_capacity_mib=64)
        results = run_matrix(config, ["node_shared"], ["StaticNReplica"])
        self.assertEqual(results[0].replica_count, 1)

    def test_capacity_and_duplicate_budget_constraints(self) -> None:
        cache = make_cache("k", "node0", 0, 64, 10)
        node_state = NodeState("node0", 64 * MIB)
        constraints = LayoutConstraints(global_duplicate_budget_bytes=32 * MIB, node_duplicate_budget_bytes=32 * MIB)
        result = constraints.can_add(cache, node_state, {"node0": node_state})
        self.assertFalse(result.allowed)
        self.assertFalse(result.checks["global_duplicate_budget"])
        self.assertFalse(result.checks["node_duplicate_budget"])

    def test_lease_expiry_does_not_mean_unconditional_delete(self) -> None:
        node_state = NodeState("node0", 64 * MIB)
        node_state.add_replica(Replica("k", "node0", status=ReplicaStatus.READY, size_bytes=8 * MIB, lease_expire_at=1.0, last_hit_at=0.0))
        constraints = LayoutConstraints(128 * MIB, 64 * MIB, minimum_residence_seconds=600.0)
        result = constraints.can_remove("k", node_state, now=10.0)
        self.assertFalse(result.allowed)
        self.assertFalse(result.checks["minimum_residence"])

    def test_uncertainty_makes_add_and_remove_conservative(self) -> None:
        sparse = GammaPoissonDemandEstimator(a0=1.0, b0=600.0, delta=0.1)
        certain = GammaPoissonDemandEstimator(a0=100.0, b0=600.0, delta=0.1)
        sparse_demand = sparse.estimate("k", "node0", 0.0, 60.0)
        certain_demand = certain.estimate("k", "node0", 0.0, 60.0)
        self.assertEqual(sparse_demand.lower, 0.0)
        self.assertGreater(sparse_demand.upper - sparse_demand.mean, 0.0)
        self.assertLess(certain_demand.lower / certain_demand.mean, 1.0)

    def test_sharedness_requires_samples(self) -> None:
        classifier = SharednessClassifier(min_access_samples=5)
        cache, _ = generate_trace("cluster_shared", SimulationConfig())
        obj = cache["common-prefix"]
        state, metrics = classifier.classify(obj, {"node0": 1, "node1": 1}, 2)
        self.assertEqual(state.value, "PROVISIONAL_PRIVATE")
        self.assertIn("samples", metrics)

    def test_simulator_runs_all_required_baselines(self) -> None:
        config = SimulationConfig(seed=3, local_capacity_mib=48)
        results = run_matrix(config, ["cluster_shared"], POLICIES)
        self.assertEqual(len(results), len(POLICIES))
        self.assertEqual({r.policy for r in results}, set(POLICIES))
        self.assertTrue(all(r.simulated_result for r in results))

    def test_aura_runs_core_scenarios(self) -> None:
        config = SimulationConfig(seed=5, local_capacity_mib=48)
        results = run_matrix(config, SCENARIOS[:4], ["AURA-KV"])
        self.assertEqual(len(results), 4)
        self.assertTrue(all(r.requests > 0 for r in results))

    def test_small_layout_enumeration_computes_best_j(self) -> None:
        cache_a = make_cache("a", "node0", 0, 4, 40)
        cache_b = make_cache("b", "node0", 0, 4, 20)
        nodes = {f"node{i}": NodeState(f"node{i}", 8 * MIB) for i in range(2)}
        model = SourceCostModel(remote_fixed_latency_ms=5.0)
        layouts = []
        for bits in itertools.product([0, 1], repeat=4):
            mapping = {("a", "node0"): bits[0], ("a", "node1"): bits[1], ("b", "node0"): bits[2], ("b", "node1"): bits[3]}
            for node in nodes.values():
                node.replicas.clear()
                node.local_used_bytes = 0
            legal = True
            for (key, node_id), enabled in mapping.items():
                cache = cache_a if key == "a" else cache_b
                if enabled and not nodes[node_id].add_replica(Replica(key, node_id, size_bytes=cache.size_bytes)):
                    legal = False
            if not legal:
                continue
            j = 0.0
            for cache in [cache_a, cache_b]:
                for node_id in nodes:
                    j += model.best_source(cache, node_id, nodes, True).best.total_ms
            layouts.append(j)
        self.assertGreater(len(layouts), 0)
        self.assertEqual(min(layouts), sorted(layouts)[0])


if __name__ == "__main__":
    unittest.main()
