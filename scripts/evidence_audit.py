#!/usr/bin/env python3
"""Audit a whole frozen batch before interpreting any speed comparison."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import random

from evidence_benchmark import MIB, PAPER_MATRIX, config_for, dump, trace_for


def audit(root):
    manifest = json.loads((root / "manifest.json").read_text())
    args = manifest["args"]
    expected = set()
    errors = []
    if (root / "INVALIDATED.json").exists(): errors.append("batch explicitly invalidated; preserve but do not interpret")
    checked = 0
    total_bytes = 0
    for scenario in args["scenarios"]:
        for seed in args["seeds"]:
            block = root / f"{scenario}-seed-{seed}"
            sizes, trace = trace_for(scenario, seed, args["requests"], args["shard_mib"])
            strategies = [s for s in args["strategies"]
                          if args.get("profile") != "paper" or s in PAPER_MATRIX[scenario]]
            random.Random(seed).shuffle(strategies)
            expected.update((block.name, s) for s in strategies)
            if not (block / "trace.json").exists():
                errors.append(f"{block.name}: missing block")
                continue
            if json.loads((block / "trace.json").read_text()) != trace:
                errors.append(f"{block.name}: trace differs from frozen generator")
            if json.loads((block / "order.json").read_text()) != strategies:
                errors.append(f"{block.name}: strategy order differs")
            for strategy in strategies:
                case = block / strategy
                path = case / "result.json"
                if not path.exists():
                    errors.append(f"{block.name}/{strategy}: missing result")
                    continue
                r = json.loads(path.read_text())
                cfg = json.loads((case / "config.json").read_text())
                remote_case = Path(args["output"]) / block.name / strategy
                remote_data = Path(args["remote_root"]) / ("eval-" + Path(args["output"]).name) / block.name
                reference = config_for(strategy, remote_case, remote_data, args["quota_mib"], args["backend_direct"])
                problems = []
                if cfg != reference: problems.append("configuration differs")
                if r["strategy"] != strategy or r["status"] != "ok": problems.append("status/strategy")
                rows = json.loads((case / "requests.json").read_text())
                if len(rows) != len(trace): problems.append("request count")
                if any(any(row[k] != event[k] for k in event) for row,event in zip(rows,trace)):
                    problems.append("requests differ from trace")
                byte_count = sum(e["bytes"] for e in trace)
                m = r["metrics"]
                if r["logical_bytes"] != byte_count or m.get("read_bytes",0) != byte_count:
                    problems.append("byte accounting")
                if m.get("read_local_bytes",0) + m.get("read_remote_bytes",0) != byte_count:
                    problems.append("source byte accounting")
                if m.get("read_open_count",0) != len(trace): problems.append("logical opens")
                if m.get("background_submitted",0) != m.get("background_completed",0):
                    problems.append("unfinished background")
                if any(v for k,v in m.items() if k.endswith("error_count")):
                    problems.append("error metric")
                if r["job_wall_s"] <= 0 or abs(r["effective_mib_s"] - byte_count/MIB/r["job_wall_s"]) > 1e-8:
                    problems.append("wall/throughput identity")
                if r["verify_every_request"] != args["verify"]: problems.append("mixed verification mode")
                if max(r["retained_cache_bytes"], default=0) > args["quota_mib"]*MIB:
                    problems.append("retained quota")
                if problems: errors.append(f"{block.name}/{strategy}: {', '.join(problems)}")
                checked += 1
                total_bytes += byte_count
    actual = {(p.parent.parent.name, p.parent.name) for p in root.glob("*-seed-*/*/result.json")}
    if actual - expected: errors.append(f"unexpected runs: {sorted(actual - expected)}")
    failures = [str(p.relative_to(root)) for p in root.rglob("failure.json")]
    if failures: errors.append(f"failed runs: {failures}")
    result = dict(passed=not errors, expected_runs=len(expected), checked_runs=checked,
                  logical_bytes=total_bytes, errors=errors,
                  limitations="Post-run audit; does not establish peak occupancy, crash atomicity, target cache coldness or physical GPU behavior.")
    dump(root / "batch-audit.json", result)
    return result


if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("root",type=Path)
    result=audit(p.parse_args().root)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["passed"] else 1)
