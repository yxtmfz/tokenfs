import math
import sys
from pathlib import Path
import tempfile
import unittest

from aura_kv.core import AccessEvent, ReplicaStatus
from aura_kv.simulator import MIB, SimulationConfig, TraceSimulator, make_cache, make_policy
from scripts.evidence_benchmark import config_for, paired_interval, trace_for
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evidence_report import holm, paired_p


class EvidenceRegression(unittest.TestCase):
    def make_sim(self, policy, times=(0, .01, 2), capacity=8):
        cfg = SimulationConfig(nodes=1, local_capacity_mib=capacity, background_bandwidth_mib_s=8)
        caches = {"k": make_cache("k", "node0", 0, 8, 80)}
        trace = [AccessEvent(t, str(i), "default", "k", "", "node0", 0, "read", 8*MIB, 1, True, 80)
                 for i, t in enumerate(times)]
        return TraceSimulator(cfg, caches, trace, make_policy(policy, cfg), "private")

    def test_miss_and_read_during_copy_are_charged_remote_for_both_policies(self):
        for policy in ["AURA-Joint", "LRU-Local", "LFU-Local"]:
            sim = self.make_sim(policy)
            result = sim.run()
            self.assertEqual(result.remote_read_bytes, 16*MIB, policy)
            self.assertEqual(sim.local_hits, 1, policy)
            self.assertEqual(result.migration_bytes, 8*MIB, policy)

    def test_pending_copy_is_reserved_once_and_cannot_be_evicted(self):
        sim = self.make_sim("LRU-Local", times=())
        cache = sim.caches["k"]
        self.assertTrue(sim.ensure_space_and_add("node0", cache, "test"))
        self.assertTrue(sim.ensure_space_and_add("node0", cache, "test"))
        self.assertEqual(sim.nodes["node0"].local_used_bytes, 8*MIB)
        self.assertEqual(sim.nodes["node0"].replicas["k"].status, ReplicaStatus.COPYING)
        self.assertIsNone(sim.choose_victim(sim.nodes["node0"], "lru"))
        sim.advance_copies(2)
        self.assertTrue(sim.nodes["node0"].has_replica("k"))

    def test_full_capacity_can_replace_ready_victim(self):
        sim = self.make_sim("AURA-Joint", times=(0, 2))
        sim.run()
        sim.caches["next"] = make_cache("next", "node0", 0, 8, 80)
        self.assertTrue(sim.ensure_space_and_add("node0", sim.caches["next"], "pressure", evict="value"))
        self.assertNotIn("k", sim.nodes["node0"].replicas)
        self.assertEqual(sim.nodes["node0"].local_used_bytes, 8*MIB)

    def test_global_victim_cannot_remove_copying_reservation(self):
        sim = self.make_sim("LRU-Local", times=())
        sim.ensure_space_and_add("node0", sim.caches["k"], "test")
        self.assertIsNone(sim.choose_global_victim("lru"))
        self.assertIsNone(sim.choose_global_victim("lfu"))

    def test_sign_flip_and_holm_use_run_blocks(self):
        self.assertEqual(paired_p([1.0] * 10), 2/1024)
        rows=[{"p_raw": .01}, {"p_raw": .04}, {"p_raw": .9}]
        holm(rows)
        self.assertEqual([r["p_holm"] for r in rows], [.03, .08, .9])

    def test_trace_pairing_and_byte_budget(self):
        for scenario in ["stable", "scan", "mixed", "shared_shift", "uniform"]:
            sizes, trace = trace_for(scenario, 19)
            self.assertEqual((sizes, trace), trace_for(scenario, 19))
            self.assertEqual(len(trace), 160)
            self.assertTrue(all(e["bytes"] == sizes[e["key"]]*MIB for e in trace))

    def test_ablation_changes_only_intended_config(self):
        with tempfile.TemporaryDirectory() as d:
            base = config_for("AURA-core", Path(d), Path("/remote"), 32)
            for name, key in [("no-value", "local_eviction_policy"), ("no-gain", "gain_admission"),
                              ("no-affinity", "affinity_placement"), ("no-trend", "trend_prediction"),
                              ("no-xgpu", "cross_gpu_local_cache"), ("AURA-prefetch", "prefetch_on_read")]:
                cfg = config_for(name, Path(d), Path("/remote"), 32)
                differences = {k for k,v in base["policy"].items() if cfg["policy"][k] != v}
                self.assertEqual(differences, {key})
                self.assertEqual(cfg["gpus"], base["gpus"])

    def test_interval_does_not_invent_precision_from_one_run(self):
        self.assertEqual(paired_interval([0]), [None, None])
        lo, hi = paired_interval([math.log(.8)] * 5)
        self.assertAlmostEqual(lo, .8)
        self.assertAlmostEqual(hi, .8)


if __name__ == "__main__":
    unittest.main()
