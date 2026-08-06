#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import signal
import sys
import time
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aura_kv.dashboard import DashboardServer
from aura_kv.monitoring import JsonlRunStore, build_state_snapshot, new_run_id
from aura_kv.simulator import ALL_POLICY_NAMES, MIB, SimulationConfig, TraceSimulator, generate_trace, make_policy


WORKLOADS = {
    "shared-prefix": "cluster_shared",
    "hotspot-migration": "hotspot_shift",
    "local-capacity-pressure": "private",
    "remote-congestion-change": "remote_congestion",
    "mixed-object-size": "high_recompute",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AURA-KV workload with JSONL monitoring and local dashboard.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="运行一个可监控的模拟 workload")
    run.add_argument("--workload", choices=sorted(WORKLOADS), default="hotspot-migration")
    run.add_argument("--policy", choices=ALL_POLICY_NAMES, default="AURA-Joint")
    run.add_argument("--output", default=str(PROJECT_ROOT / "reports/latest/aura-kv-live"))
    run.add_argument("--run-id", default="")
    run.add_argument("--dashboard", action="store_true")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8765)
    run.add_argument("--seed", type=int, default=7)
    run.add_argument("--nodes", type=int, default=2)
    run.add_argument("--gpus-per-node", type=int, default=2)
    run.add_argument("--local-capacity-mib", type=int, default=96)
    run.add_argument("--duplicate-budget-mib", type=int, default=128)
    run.add_argument("--node-duplicate-budget-mib", type=int, default=64)
    run.add_argument("--event-delay-ms", type=float, default=25.0)
    run.add_argument("--no-wait", action="store_true", help="运行结束后不保持 dashboard 服务")

    dash = sub.add_parser("dashboard", help="单独启动 dashboard 查看当前或历史 run")
    dash.add_argument("--run-dir", required=True)
    dash.add_argument("--host", default="127.0.0.1")
    dash.add_argument("--port", type=int, default=8765)

    export = sub.add_parser("export", help="从 JSONL run 目录导出统一结果")
    export.add_argument("--run-dir", required=True)
    return parser.parse_args()


def run_workload(args: argparse.Namespace) -> int:
    scenario = WORKLOADS[args.workload]
    config = SimulationConfig(
        seed=args.seed,
        nodes=args.nodes,
        gpus_per_node=args.gpus_per_node,
        local_capacity_mib=args.local_capacity_mib,
        duplicate_budget_mib=args.duplicate_budget_mib,
        node_duplicate_budget_mib=args.node_duplicate_budget_mib,
    )
    output_root = Path(args.output)
    run_id = args.run_id or new_run_id("aura")
    run_dir = output_root / run_id
    store = JsonlRunStore(run_dir, run_id, simulated=True, policy=args.policy, workload=args.workload, mode="SIMULATED")
    server: DashboardServer | None = None
    if args.dashboard:
        server = DashboardServer(run_dir, args.host, args.port)
        server.start_background()
    dashboard_url = server.url if server else ""

    print("AURA-KV is running")
    print("Mode: SIMULATED")
    print(f"Run ID: {run_id}")
    print(f"Dashboard: {dashboard_url or 'disabled'}")
    print(f"Logs: {run_dir}")
    print(f"Results: {run_dir}")
    print("Latency: PROXY / SIMULATED, not real TTFT")
    sys.stdout.flush()

    caches, trace = generate_trace(scenario, config)
    policy = make_policy(args.policy, config)
    if hasattr(policy, "set_future_trace"):
        policy.set_future_trace(trace)  # type: ignore[attr-defined]
    sim = TraceSimulator(config, caches, trace, policy, scenario, monitor=store, run_id=run_id)
    result = sim.run(event_delay_seconds=max(0.0, args.event_delay_ms) / 1000.0)
    write_result_files(run_dir, result)
    store.write_manifest(status="STOPPED", result="completed")

    if server and not args.no_wait:
        print("AURA-KV workload stopped; dashboard remains available. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            server.stop()
    elif server:
        server.stop()
    return 0


def write_result_files(run_dir: Path, result: object) -> None:
    row = asdict(result)
    (run_dir / "results.json").write_text(
        json.dumps({"notice": "SIMULATED RESULT - latency values are proxy metrics", "result": row}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (run_dir / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
    state = build_state_snapshot(run_dir)
    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_dashboard(args: argparse.Namespace) -> int:
    server = DashboardServer(args.run_dir, args.host, args.port)
    print(f"Dashboard: {server.url}")
    print(f"Run dir: {Path(args.run_dir).resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()
    return 0


def run_export(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    state = build_state_snapshot(run_dir)
    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported: {run_dir / 'state.json'}")
    print(f"Events:   {run_dir / 'events.jsonl'}")
    print(f"Metrics:  {run_dir / 'metrics.jsonl'}")
    print(f"Layout:   {run_dir / 'layout_snapshots.jsonl'}")
    return 0


def main() -> int:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    args = parse_args()
    if args.command == "run":
        return run_workload(args)
    if args.command == "dashboard":
        return run_dashboard(args)
    if args.command == "export":
        return run_export(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
