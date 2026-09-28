#!/usr/bin/env python3
"""Real FUSE evaluation: immutable inputs, paired traces, outer wall time.

No sudo, global cache dropping, arbitrary reset, synthetic latency or winner selection.
Linux only for execution; trace/config/report unit tests also run on macOS.
"""
from __future__ import annotations

from contextlib import closing
import argparse
import csv
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import random
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time

MIB = 1024 * 1024
STRATEGIES = {
    "RemoteOnly": {"local_eviction_policy": "none", "promote_on_read": False,
                   "cross_gpu_local_cache": False, "placement_policy": "remote_only"},
    "LRU-equal": {"local_eviction_policy": "lru", "read_through_cache": True},
    "LFU-equal": {"local_eviction_policy": "lfu", "read_through_cache": True},
    "AURA-core": {},
    "no-value": {"local_eviction_policy": "lru"},
    "no-gain": {"gain_admission": False},
    "no-affinity": {"affinity_placement": False},
    "no-trend": {"trend_prediction": False},
    "no-xgpu": {"cross_gpu_local_cache": False},
    "AURA-prefetch": {"prefetch_on_read": True},
    "E0A0": {"local_eviction_policy": "lru", "affinity_placement": False},
    "synchronous": {"async_promote_on_read": False, "async_cross_gpu_replica": False},
}
PAPER_MATRIX = {
    "stable": ["RemoteOnly", "LRU-equal", "LFU-equal", "AURA-core", "no-value", "no-gain", "no-affinity", "no-trend", "synchronous"],
    "scan": ["RemoteOnly", "LRU-equal", "LFU-equal", "AURA-core", "no-value", "no-affinity", "E0A0"],
    "mixed": ["RemoteOnly", "LRU-equal", "LFU-equal", "AURA-core", "no-value"],
    "shared_shift": ["RemoteOnly", "LRU-equal", "LFU-equal", "AURA-core", "no-value", "no-affinity", "no-trend", "no-xgpu", "E0A0", "synchronous"],
    "uniform": ["RemoteOnly", "LRU-equal", "LFU-equal", "AURA-core", "no-gain", "no-affinity", "AURA-prefetch"],
    "sequential": ["AURA-core", "AURA-prefetch"],
}
SCENARIOS = ["stable", "scan", "mixed", "shared_shift", "uniform", "sequential"]


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(MIB), b""):
            h.update(block)
    return h.hexdigest()


def trace_for(scenario, seed, requests=160, shard_mib=8):
    rng = random.Random(seed)
    sizes = {i: shard_mib * (4 if scenario == "mixed" and i >= 8 else 1) for i in range(24)}
    events = []
    for n in range(requests):
        if scenario == "stable":
            key = rng.randrange(4) if rng.random() < .85 else rng.randrange(4, 24)
        elif scenario == "scan":
            key = rng.randrange(4) if n % 32 < 22 else 4 + n % 20
        elif scenario == "mixed":
            key = rng.randrange(8) if rng.random() < .8 else rng.randrange(8, 24)
        elif scenario == "shared_shift":
            key = rng.randrange(6)
        elif scenario == "sequential":
            key = n % 24
        else:
            key = rng.randrange(24)
        caller = (n // max(1, requests // 3)) % 3 if scenario == "shared_shift" else 0
        events.append({"index": n, "key": key, "caller": caller, "bytes": sizes[key] * MIB})
    return sizes, events


def config_for(strategy, case, remote, quota_mib, backend_direct=False):
    policy = dict(local_eviction_policy="value_aware", placement_policy="value_aware",
                  promote_on_read=True, async_promote_on_read=True, cross_gpu_local_cache=True,
                  async_cross_gpu_replica=True, prefetch_on_read=False, read_through_cache=False,
                  read_through_min_reads=2, promote_read_threshold=2, migration_min_reuse_reads=2,
                  migration_min_benefit_x100=100, migration_copy_cost_per_mib=4,
                  default_recompute_cost=10, default_remote_access_cost=10, value_promote_threshold=10,
                  affinity_placement=True, gain_admission=True, trend_prediction=True,
                  affinity_short_window_sec=2, affinity_long_window_sec=10,
                  affinity_replica_cooldown_sec=0, affinity_replica_min_residency_sec=0,
                  max_local_replicas_per_file=3, speculative_copy_may_evict=True,
                  adaptive_migration=False, durable_local_cache=False,
                  checksum="fnv1a64", fuse_direct_io=True, backend_direct_io=backend_direct, readonly_canonical=True)
    policy.update(STRATEGIES[strategy])
    return dict(filesystem=dict(mount_point=str(case / "mnt"), metadata_db=str(case / "state.db")),
                policy=policy,
                gpus=[dict(gpu_id=i, logical_root=f"/gpu{i}", local_root=str(case / f"cache{i}"),
                           local_quota_mib=0 if strategy == "RemoteOnly" else quota_mib,
                           remote_backend="remote") for i in range(3)],
                backends=[dict(id="remote", type="nvmeof", root=str(remote))])


def worker(connection, gpu, mount, verify, diagnostic=False):
    # Use exec: /proc/PID/environ must expose TOKENFS_GPU_ID to FUSE.
    env = dict(os.environ, TOKENFS_GPU_ID=str(gpu))
    if diagnostic: env["TOKENFS_REQUEST_DIAGNOSTIC"]="1"
    proc = subprocess.Popen([sys.executable, __file__, "--loader", str(mount),
                             "--verify" if verify else "--no-verify"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    if json.loads(proc.stdout.readline()) != {"ready": True}:
        raise RuntimeError("loader handshake failed")
    connection.send({"ready": True})
    try:
        while True:
            event = connection.recv()
            if event is None: break
            proc.stdin.write(json.dumps(event) + "\n"); proc.stdin.flush()
            line = proc.stdout.readline()
            if not line: raise RuntimeError("loader exited")
            connection.send(json.loads(line))
    except Exception as exc:
        connection.send({"error": str(exc)})
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)


def loader(mount, verify):
    diagnostic=os.environ.get("TOKENFS_REQUEST_DIAGNOSTIC")=="1"
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        event = json.loads(line)
        start = time.monotonic_ns()
        count = 0
        h = hashlib.sha256() if verify else None
        try:
            with (Path(mount) / "gpu0" / f"shard-{event['key']:06d}.tokens").open("rb", buffering=0) as f:
                opened=time.monotonic_ns() if diagnostic else 0
                for data in iter(lambda: f.read(MIB), b""):
                    count += len(data)
                    if h: h.update(data)
                read_done=time.monotonic_ns() if diagnostic else 0
            closed=time.monotonic_ns() if diagnostic else 0
            result = {"bytes": count, "seconds": (time.monotonic_ns() - start) / 1e9,
                      "sha256": h.hexdigest() if h else None}
            if diagnostic: result.update(start_ns=start,opened_ns=opened,read_done_ns=read_done,closed_ns=closed)
        except Exception as exc:
            result = {"error": repr(exc)}
        print(json.dumps(result), flush=True)


def metrics(db):
    with closing(sqlite3.connect(db, timeout=30)) as con:
        return dict(con.execute("SELECT name,value FROM metrics"))


def drain(db, timeout=120):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        m = metrics(db)
        if m.get("background_submitted", 0) == m.get("background_completed", 0):
            if m.get("background_error_count", 0): raise RuntimeError("background task error")
            return time.monotonic() - start
        time.sleep(.02)
    raise TimeoutError("background queue did not drain")


def finalize_case_metrics(case, result, returncode):
    if returncode != 0: raise RuntimeError("daemon exit failed")
    final_metrics=metrics(case / "state.db")
    for key in ["read_bytes","read_open_count","read_local_bytes","read_remote_bytes","read_inflight_bytes","background_submitted","background_completed"]:
        if final_metrics.get(key,0)!=result["metrics"].get(key,0):
            raise RuntimeError("final I/O accounting changed: "+key)
    result["metrics"]=final_metrics
    result["metrics_snapshot"]="after_daemon_shutdown"
    dump(case / "result.json",result)


def run_case(binary, case, remote, strategy, events, expected, quota_mib, verify, backend_direct=False, configuration=None):
    case.mkdir()
    config = configuration if configuration is not None else config_for(strategy, case, remote, quota_mib, backend_direct)
    dump(case / "config.json", config)
    mount = case / "mnt"; mount.mkdir()
    # Equal explicit warm-backend initialization, with empty TokenFS caches.
    for path in sorted((remote / "gpu0").glob("*.tokens")):
        with path.open("rb") as f:
            if backend_direct:
                os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
            else:
                while f.read(MIB): pass
    log = (case / "tokenfs.log").open("w")
    proc = subprocess.Popen([str(binary), "--config", str(case / "config.json"), "-f", str(mount)],
                            stdout=log, stderr=log)
    workers = []
    started = time.monotonic()
    try:
        while not os.path.ismount(mount):
            if proc.poll() is not None: raise RuntimeError("FUSE startup failed")
            if time.monotonic() - started > 15: raise TimeoutError("FUSE startup")
            time.sleep(.02)
        for gpu in range(3):
            parent, child = mp.Pipe()
            w = mp.Process(target=worker, args=(child, gpu, mount, verify, bool(configuration and configuration["policy"].get("request_trace_path"))))
            w.start()
            if not parent.poll(15) or not parent.recv().get("ready"): raise RuntimeError("loader startup")
            workers.append((parent, w))
        rows = []
        def cpu_seconds():
            parts=Path(f"/proc/{proc.pid}/stat").read_text().split()
            return (int(parts[13])+int(parts[14]))/os.sysconf("SC_CLK_TCK")
        cpu_start=cpu_seconds()
        outer_start = time.monotonic_ns()
        for event in events:
            conn, _ = workers[event["caller"]]
            if "release_s" in event:
                delay=event["release_s"]-(time.monotonic_ns()-outer_start)/1e9
                if delay>0:time.sleep(delay)
            request_start = time.monotonic_ns()
            conn.send(event)
            if not conn.poll(120): raise TimeoutError("request timeout")
            result = conn.recv()
            if "error" in result: raise RuntimeError(result["error"])
            if result["bytes"] != event["bytes"]: raise RuntimeError("short read")
            if verify and result["sha256"] != expected[str(event["key"])]: raise RuntimeError("content mismatch")
            rows.append(dict(event, **result, response_seconds=(time.monotonic_ns() - request_start) / 1e9,
                             issued_s=(request_start-outer_start)/1e9,
                             completed_s=(time.monotonic_ns()-outer_start)/1e9))
        wall = (time.monotonic_ns() - outer_start) / 1e9
        drain_seconds = drain(case / "state.db")
        daemon_cpu_s=cpu_seconds()-cpu_start
        status_text=Path(f"/proc/{proc.pid}/status").read_text()
        rss_match=re.search(r"^VmHWM:\s+(\d+) kB",status_text,re.MULTILINE)
        data_bytes = sum(e["bytes"] for e in events)
        stats_deadline = time.monotonic() + 10
        while True:
            m = metrics(case / "state.db")
            if m.get("read_open_count", 0) == len(events) and m.get("read_bytes", 0) == data_bytes: break
            if time.monotonic() > stats_deadline:
                dump(case / "accounting-failure.json", {"expected_requests": len(events), "expected_bytes": data_bytes, "metrics": m})
                raise RuntimeError("FUSE accounting did not settle")
            time.sleep(.01)
        # Full retained-replica validation is outside the timing interval.
        cache_bytes = []
        checked = 0
        for gpu in range(3):
            paths = list((case / f"cache{gpu}").rglob("*.tokens"))
            used = sum(p.stat().st_size for p in (case / f"cache{gpu}").rglob("*") if p.is_file())
            cache_bytes.append(used)
            if used > quota_mib * MIB: raise RuntimeError("cache quota exceeded")
            for path in paths:
                key = str(int(path.stem.split("-")[-1]))
                if sha(path) != expected[key]: raise RuntimeError("retained replica checksum mismatch")
                checked += 1
        if m.get("read_open_count", 0) != len(events): raise RuntimeError("logical request accounting mismatch")
        if m.get("copy_checksum_error_count", 0): raise RuntimeError("copy checksum error")
        data_bytes = sum(e["bytes"] for e in events)
        if m.get("read_bytes", 0) != data_bytes: raise RuntimeError("FUSE read bytes mismatch")
        result = dict(status="ok", strategy=strategy, job_wall_s=wall,
                      daemon_cpu_s=daemon_cpu_s,daemon_peak_rss_kib=int(rss_match.group(1)) if rss_match else None,
                      effective_mib_s=data_bytes / MIB / wall, logical_bytes=data_bytes,
                      foreground_service_sum_s=sum(r["seconds"] for r in rows),
                      drain_s=drain_seconds, completed_with_background_s=wall + drain_seconds,
                      metrics=m, retained_cache_bytes=cache_bytes, verified_replicas=checked,
                      verify_every_request=verify, cache_mode=("client O_DIRECT disk tiers; bounded captured-memory sharing" if configuration and configuration.get("policy",{}).get("coalesce_pending_reads") else "client O_DIRECT both tiers; server caches uncontrolled" if backend_direct else "warm backend; empty application cache; FUSE direct_io"),
                      request_p50_s=percentile([r["response_seconds"] for r in rows], .5),
                      request_p99_s=percentile([r["response_seconds"] for r in rows], .99))
        with closing(sqlite3.connect(case / "state.db")) as con:
            con.row_factory = sqlite3.Row
            dump(case / "policy-events.json", [dict(r) for r in con.execute("SELECT * FROM policy_events ORDER BY seq")])
            dump(case / "files.json", [dict(r) for r in con.execute("SELECT * FROM files ORDER BY logical_path")])
        dump(case / "requests.json", rows)
        dump(case / "result.json", result)
        return result
    except Exception as exc:
        dump(case / "failure.json", {"error": repr(exc), "strategy": strategy})
        raise
    finally:
        for conn, w in workers:
            try: conn.send(None)
            except (BrokenPipeError, EOFError): pass
            w.join(10)
            if w.is_alive(): w.terminate(); w.join()
        subprocess.run(["fusermount3", "-u", str(mount)], capture_output=True)
        try: proc.wait(timeout=120)
        except subprocess.TimeoutExpired: proc.terminate(); proc.wait(timeout=10)
        log.close()
        # Buffered non-I/O decision metrics can be flushed only by the daemon's
        # destructor after the final background task. Preserve measured timings,
        # but publish the final durable counters rather than an earlier snapshot.
        if (case / "result.json").exists() and not (case / "failure.json").exists():
            finalize_case_metrics(case,result,proc.returncode)


def percentile(values, p):
    return sorted(values)[min(len(values) - 1, max(0, math.ceil(p * len(values)) - 1))]


def paired_interval(log_ratios, seed=421, samples=5000):
    if len(log_ratios) < 2: return [None, None]
    rng = random.Random(seed)
    boot = [math.exp(statistics.mean(rng.choices(log_ratios, k=len(log_ratios)))) for _ in range(samples)]
    return [percentile(boot, .025), percentile(boot, .975)]


def report(root):
    results = []
    for p in root.glob("*-seed-*/*/result.json"):
        r = json.loads(p.read_text())
        r["block"] = p.parent.parent.name
        r["scenario"] = r["block"].split("-seed-")[0]
        results.append(r)
    rows = []
    for scenario in sorted({r["scenario"] for r in results}):
        for name in sorted({r["strategy"] for r in results}):
            subset = [r for r in results if r["scenario"] == scenario and r["strategy"] == name]
            if not subset: continue
            baseline = {r["block"]: r for r in results if r["scenario"] == scenario and r["strategy"] == "LRU-equal"}
            logs = [math.log(r["job_wall_s"] / baseline[r["block"]]["job_wall_s"]) for r in subset if r["block"] in baseline]
            rows.append(dict(scenario=scenario, strategy=name, n=len(subset),
                             mean_wall_s=statistics.mean(r["job_wall_s"] for r in subset),
                             mean_mib_s=statistics.mean(r["effective_mib_s"] for r in subset),
                             paired_n=len(logs), time_ratio_vs_lru=math.exp(statistics.mean(logs)) if logs else None,
                             ratio_ci95=paired_interval(logs),
                             evictions=sum(r["metrics"].get("evict_count", 0) for r in subset)))
    dump(root / "summary.json", rows)
    with (root / "summary.csv").open("w", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return rows


def main():
    if "--loader" in sys.argv:
        return loader(sys.argv[sys.argv.index("--loader") + 1], "--verify" in sys.argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--remote-root", type=Path)
    parser.add_argument("--expected-target", default="28.10.10.13")
    parser.add_argument("--expected-nqn", default="nqn.2026-09.local.aura-kv:remote-cn7")
    parser.add_argument("--binary", type=Path, default=Path(__file__).resolve().parents[1] / "build/tokenfs")
    parser.add_argument("--profile", choices=["custom", "paper"], default="custom")
    parser.add_argument("--strategies", nargs="+", choices=STRATEGIES, default=None)
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=SCENARIOS[:5])
    parser.add_argument("--seeds", nargs="+", type=int, default=list(range(101, 111)))
    parser.add_argument("--requests", type=int, default=160)
    parser.add_argument("--shard-mib", type=int, default=8)
    parser.add_argument("--quota-mib", type=int, default=32)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--backend-direct", action="store_true", help="O_DIRECT for foreground reads in BOTH tiers; does not claim target cache bypass")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if args.strategies is None:
        args.strategies = list(STRATEGIES) if args.profile == "paper" else ["RemoteOnly", "LRU-equal", "LFU-equal", "AURA-core"]
    root = args.output.resolve()
    if args.report_only: report(root); return
    if not args.remote_root: parser.error("--remote-root is required")
    if min(args.requests, args.shard_mib, args.quota_mib) <= 0: parser.error("sizes and requests must be positive")
    if len(set(args.seeds)) != len(args.seeds): parser.error("duplicate seed")
    cache_path = args.binary.resolve().parent / "CMakeCache.txt"
    build_type = None
    if cache_path.exists():
        match = re.search(r"^CMAKE_BUILD_TYPE:STRING=(.*)$", cache_path.read_text(), re.MULTILINE)
        if match: build_type = match.group(1)
    if args.profile == "paper" and not args.verify and build_type != "Release":
        raise RuntimeError("formal paper profile requires a verified CMake Release build")
    # This check makes accidental execution on an unmounted fallback directory fail closed.
    mount = subprocess.check_output(["findmnt", "-J", "--target", str(args.remote_root.resolve())], text=True)
    mount_info = json.loads(mount)["filesystems"][0]
    match = re.fullmatch(r"/dev/(nvme[0-9]+)n[0-9]+(?:p[0-9]+)?", str(mount_info["source"]))
    if not match: raise RuntimeError("remote root is not on NVMe device")
    ctl = Path("/sys/class/nvme") / match.group(1)
    identity = {name: (ctl / name).read_text().strip() for name in ["transport", "address", "subsysnqn"]}
    if identity["transport"] != "tcp" or identity["subsysnqn"] != args.expected_nqn:
        raise RuntimeError("NVMe transport/NQN mismatch")
    if ("traddr=" + args.expected_target) not in identity["address"].split(","):
        raise RuntimeError("NVMe target mismatch")
    root.mkdir(parents=True, exist_ok=False)
    remote_run = args.remote_root.resolve() / ("eval-" + root.name)
    remote_run.mkdir(exist_ok=False)
    dump(root / "manifest.json", {"args": {k: str(v) if isinstance(v, Path) else v for k,v in vars(args).items()},
                                  "binary_sha256": sha(args.binary), "build_type": build_type,
                                  "mount": mount_info, "nvme_identity": identity,
                                  "source_sha256": sha(Path(__file__).resolve().parents[1] / "src/main.cpp"),
                                  "harness_sha256": sha(__file__),
                                  "kernel": subprocess.check_output(["uname", "-a"], text=True).strip(),
                                  "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                  "cache_mode": "client O_DIRECT, server caches uncontrolled" if args.backend_direct else "warm backend; FUSE direct_io",
                                  "synthetic_workload": True, "primary_metric": "job_wall_s"})
    for scenario in args.scenarios:
        for seed in args.seeds:
            block = root / f"{scenario}-seed-{seed}"; block.mkdir()
            data = remote_run / block.name; (data / "gpu0").mkdir(parents=True)
            sizes, events = trace_for(scenario, seed, args.requests, args.shard_mib)
            expected = {}
            for key, mib in sizes.items():
                path = data / "gpu0" / f"shard-{key:06d}.tokens"
                content = random.Random(seed * 1000 + key).randbytes(MIB)
                with path.open("wb") as f:
                    for _ in range(mib): f.write(content)
                    f.flush(); os.fsync(f.fileno())
                expected[str(key)] = sha(path)
            dump(block / "trace.json", events); dump(block / "objects.json", {"sizes_mib": sizes, "sha256": expected})
            order = [s for s in args.strategies if args.profile == "custom" or s in PAPER_MATRIX[scenario]]
            random.Random(seed).shuffle(order); dump(block / "order.json", order)
            for strategy in order:
                result = run_case(args.binary.resolve(), block / strategy, data, strategy, events, expected, args.quota_mib, args.verify, args.backend_direct)
                print(json.dumps({"block": block.name, "strategy": strategy, "wall_s": result["job_wall_s"],
                                  "mib_s": result["effective_mib_s"], "evictions": result["metrics"].get("evict_count", 0)}), flush=True)
            report(root)
    report(root)


if __name__ == "__main__":
    main()
