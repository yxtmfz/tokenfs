#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aura_kv.simulator import POLICIES, SCENARIOS, SimulationConfig, run_matrix, write_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AURA-KV trace-driven simulator.")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "reports/latest/aura-kv-sim"))
    parser.add_argument("--scenario", action="append", choices=SCENARIOS)
    parser.add_argument("--policy", action="append", choices=POLICIES)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--nodes", type=int, default=2)
    parser.add_argument("--gpus-per-node", type=int, default=2)
    parser.add_argument("--local-capacity-mib", type=int, default=96)
    parser.add_argument("--remote-p99-ms", type=float, default=8.0)
    parser.add_argument("--duplicate-budget-mib", type=int, default=128)
    parser.add_argument("--node-duplicate-budget-mib", type=int, default=64)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = SimulationConfig(
        seed=args.seed,
        nodes=args.nodes,
        gpus_per_node=args.gpus_per_node,
        local_capacity_mib=args.local_capacity_mib,
        remote_read_p99_ms=args.remote_p99_ms,
        duplicate_budget_mib=args.duplicate_budget_mib,
        node_duplicate_budget_mib=args.node_duplicate_budget_mib,
    )
    scenarios = args.scenario or SCENARIOS
    policies = args.policy or POLICIES
    results = run_matrix(config, scenarios, policies)
    output = Path(args.output)
    write_results(results, output)
    print("AURA-KV trace simulator completed.")
    print("SIMULATED RESULT - not real NVMe-oF hardware data.")
    print(f"config={asdict(config)}")
    print(f"scenarios={','.join(scenarios)}")
    print(f"policies={','.join(policies)}")
    print(f"report={output / 'aura_sim_report.md'}")
    print(f"csv={output / 'aura_sim_results.csv'}")
    print(f"json={output / 'aura_sim_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

