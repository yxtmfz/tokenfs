import math
import json
import sys
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from aura_kv.core import AccessEvent, ReplicaStatus
from aura_kv.simulator import MIB, SimulationConfig, TraceSimulator, make_cache, make_policy
from scripts.evidence_benchmark import config_for, paired_interval, trace_for
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evidence_report import holm, paired_p
from evidence_audit import audit
from scripts.evidence_benchmark import dump
from aura_kv.controller import AuraController
from aura_kv.core import NodeState, Replica
from aura_kv.optimization import LayoutConstraints


class EvidenceRegression(unittest.TestCase):
    def test_batch_audit_rejects_missing_runs_and_changed_bytes(self):
        # Synthetic unit fixture only; no fixture timing is published as evidence.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"fixture";root.mkdir()
            args=dict(output=str(root),remote_root="/remote",requests=3,shard_mib=1,quota_mib=8,
                      scenarios=["stable"],strategies=["AURA-core"],seeds=[2],backend_direct=True,verify=False)
            dump(root/"manifest.json",dict(args=args))
            self.assertFalse(audit(root)["passed"])
            block=root/"stable-seed-2";block.mkdir();case=block/"AURA-core";case.mkdir()
            _,trace=trace_for("stable",2,3,1)
            dump(block/"trace.json",trace);dump(block/"order.json",["AURA-core"])
            dump(case/"config.json",config_for("AURA-core",case,Path("/remote/eval-fixture/stable-seed-2"),8,True))
            dump(case/"requests.json",trace)
            result=dict(strategy="AURA-core",status="ok",logical_bytes=3*MIB,job_wall_s=1,effective_mib_s=3,
                        metrics=dict(read_open_count=3,read_bytes=3*MIB,read_remote_bytes=3*MIB,qos_gpu0_read_bytes=3*MIB),
                        verify_every_request=False,retained_cache_bytes=[0,0,0])
            dump(case/"result.json",result)
            self.assertTrue(audit(root)["passed"])
            result["metrics"]["read_remote_bytes"]-=1;dump(case/"result.json",result)
            self.assertFalse(audit(root)["passed"])
            self.assertIn("source byte accounting",audit(root)["errors"][0])

    def test_controller_reserves_batch_and_never_bypasses_hard_constraints_for_swap(self):
        evaluator = SimpleNamespace(
            demand_estimator=SimpleNamespace(observe=lambda event: None),
            robust_benefit_for_add=lambda *args: SimpleNamespace(allowed=True, benefit_ms=100, reason="gain"))
        caches = {k: make_cache(k, "node0", 0, 1, 80) for k in ["a", "b", "old"]}
        events = [AccessEvent(i, str(i), "default", k, "", "node0", 0, "read", MIB, 1, True, 80)
                  for i,k in enumerate(["a", "a", "b"])]
        nodes = {"node0": NodeState("node0", MIB)}
        constraints = LayoutConstraints(10*MIB, 10*MIB)
        plan = AuraController(evaluator, constraints).plan_from_accesses(events,caches,nodes,True,1,now=10)
        self.assertEqual([t.cache_key for t in plan.tasks], ["a"])
        self.assertEqual(nodes["node0"].local_used_bytes, 0)  # Planning is not committing.
        self.assertIn("node_capacity", plan.rejected[0])
        nodes["node0"].add_replica(Replica("old", "node0", size_bytes=MIB))
        full = AuraController(evaluator, constraints).plan_from_accesses(events,caches,nodes,True,1,now=10)
        self.assertEqual(full.tasks, [])
        self.assertTrue(nodes["node0"].has_replica("old"))
        nodes = {"node0": NodeState("node0", 8*MIB)}
        for gate in ["foreground_slo_gate", "background_bandwidth_budget_bytes_per_cycle"]:
            constrained = LayoutConstraints(10*MIB,10*MIB)
            setattr(constrained,gate,True if gate == "foreground_slo_gate" else 0)
            plan=AuraController(evaluator,constrained).plan_from_accesses(events,caches,nodes,True,1,now=10)
            self.assertEqual(plan.tasks, [], gate)

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
