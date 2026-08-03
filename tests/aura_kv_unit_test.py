#!/usr/bin/env python3
from __future__ import annotations

import unittest

from aura_kv.core import AccessEvent, CacheIdentity
from aura_kv.policies import SharednessClassifier
from aura_kv.prediction import EWMAAccessPredictor
from aura_kv.simulator import POLICIES, SCENARIOS, SimulationConfig, generate_trace, run_matrix


class AuraKVUnitTest(unittest.TestCase):
    def test_cache_identity_blocks_cross_domain_sharing(self) -> None:
        a = CacheIdentity(cache_key="same", sharing_domain="tenantA", token_prefix_hash="p")
        b = CacheIdentity(cache_key="same", sharing_domain="tenantB", token_prefix_hash="p")
        self.assertNotEqual(a.share_safe_key, b.share_safe_key)

    def test_ewma_predictor_falls_back_with_low_confidence(self) -> None:
        predictor = EWMAAccessPredictor(min_confidence_samples=5)
        pred = predictor.predict("missing", 100.0, ["node0", "node1"])
        self.assertEqual(pred.confidence, 0.0)
        self.assertEqual(pred.cold_probability, 1.0)

    def test_ewma_predictor_detects_node_demand(self) -> None:
        predictor = EWMAAccessPredictor(min_confidence_samples=2)
        for i in range(3):
            predictor.observe(
                AccessEvent(i, f"r{i}", "t", "k", "", "node1", 0, "read", 1024, 1, True, 1.0)
            )
        pred = predictor.predict("k", 3.0, ["node0", "node1"])
        self.assertGreater(pred.future_hits_by_node["node1"], pred.future_hits_by_node["node0"])
        self.assertGreaterEqual(pred.confidence, 1.0)

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


if __name__ == "__main__":
    unittest.main()

