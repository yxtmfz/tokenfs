#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
result_root="${1:-$project_root/reports/latest}"
config_file="${TOKENFS_CONFIG:-$project_root/config/tokenfs.dev.yaml}"
mount_point="${TOKENFS_MOUNT:-}"
metadata_db="${TOKENFS_DB:-}"

if [[ -z "$mount_point" || -z "$metadata_db" ]]; then
  config_values="$(
    python3 - "$project_root" "$config_file" <<'PY'
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
config_file = Path(sys.argv[2])
sys.path.insert(0, str(project_root / "scripts"))
from tokenfsctl import parse_config  # noqa: E402

config = parse_config(config_file)
print(config.mount_point)
print(config.metadata_db)
PY
  )"
  if [[ -z "$mount_point" ]]; then
    mount_point="$(printf '%s\n' "$config_values" | sed -n '1p')"
  fi
  if [[ -z "$metadata_db" ]]; then
    metadata_db="$(printf '%s\n' "$config_values" | sed -n '2p')"
  fi
fi

shard_mib="${TOKENFS_SHARD_MIB:-8}"
remote_hot_shards="${TOKENFS_REMOTE_HOT_SHARDS:-2}"
cold_fill_shards="${TOKENFS_COLD_FILL_SHARDS:-4}"
cross_gpu_reads="${TOKENFS_CROSS_GPU_READS:-16}"
pressure_shard_mib="${TOKENFS_PRESSURE_SHARD_MIB:-8}"
hot_rehit_reads="${TOKENFS_HOT_REHIT_READS:-32}"
sequential_rehit_reads="${TOKENFS_SEQUENTIAL_REHIT_READS:-12}"
chunk_mib="${TOKENFS_CHUNK_MIB:-1}"
fadvise_dontneed="${TOKENFS_FADVISE_DONTNEED:-0}"
drop_os_caches="${TOKENFS_DROP_OS_CACHES:-0}"
drop_os_caches_per_read="${TOKENFS_DROP_OS_CACHES_PER_READ:-0}"

cleanup() {
  "$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ -e "$result_root" ]]; then
  echo "Refusing to overwrite results: $result_root" >&2
  exit 1
fi
mkdir -p "$result_root"


TOKENFS_CONFIG="$config_file" "$project_root/scripts/reset_dev_state.sh" "$mount_point" >/dev/null
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$config_file" "$mount_point" >/dev/null

python3 - "$project_root" "$mount_point" "$metadata_db" "$config_file" "$result_root" \
  "$shard_mib" "$remote_hot_shards" "$cold_fill_shards" "$cross_gpu_reads" \
  "$pressure_shard_mib" "$hot_rehit_reads" "$sequential_rehit_reads" "$chunk_mib" \
  "$fadvise_dontneed" "$drop_os_caches" "$drop_os_caches_per_read" <<'PY'
import csv
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

project_root = Path(sys.argv[1])
mount = Path(sys.argv[2])
metadata_db = Path(sys.argv[3])
config_file = Path(sys.argv[4])
result = Path(sys.argv[5])
shard_mib = int(sys.argv[6])
remote_hot_shards = int(sys.argv[7])
cold_fill_shards = int(sys.argv[8])
cross_gpu_reads = int(sys.argv[9])
pressure_shard_mib = int(sys.argv[10])
hot_rehit_reads = int(sys.argv[11])
sequential_rehit_reads = int(sys.argv[12])
chunk_mib = int(sys.argv[13])
fadvise_dontneed = sys.argv[14] == "1"
drop_os_caches = sys.argv[15] == "1"
drop_os_caches_per_read = sys.argv[16] == "1"

sys.path.insert(0, str(project_root / "scripts"))
from tokenfsctl import parse_config  # noqa: E402

MIB = 1024 * 1024
chunk_bytes = chunk_mib * MIB
config = parse_config(config_file)
backends = config.backends
gpus_by_id = {gpu.gpu_id: gpu for gpu in config.gpus}

rows: list[dict[str, object]] = []
run_id = os.environ.get("TOKENFS_RUN_ID")
if not run_id:
    run_id = f"run-{int(time.time())}-{os.getpid()}"
run_id = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in run_id)
dataset_dir = f"{run_id}/dataset-a"
shared_dir = f"{run_id}/shared"


def remote_root(gpu_id: int) -> Path:
    backend_id = gpus_by_id[gpu_id].remote_backend
    return backends[backend_id].root


def token_chunk(owner_gpu: int, shard_id: int, chunk_id: int, size: int) -> bytes:
    header = f"gpu={owner_gpu};shard={shard_id};chunk={chunk_id};".encode()
    pattern = header + b"aura-kv-sequential-token-data\n"
    return (pattern * ((size // len(pattern)) + 1))[:size]


def write_pattern_file(path: Path, owner_gpu: int, shard_id: int, size_mib: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total = size_mib * MIB
    with path.open("wb", buffering=0) as f:
        try:
            os.posix_fallocate(f.fileno(), 0, total)
        except OSError:
            pass
        written = 0
        chunk_id = 0
        while written < total:
            n = min(chunk_bytes, total - written)
            f.write(token_chunk(owner_gpu, shard_id, chunk_id, n))
            written += n
            chunk_id += 1
        os.fsync(f.fileno())


def upsert_remote_meta(logical_path: str, owner_gpu: int, physical: Path, size_mib: int,
                       recompute_cost: int = 80, remote_access_cost: int = 80) -> None:
    now = int(time.time())
    backend_id = gpus_by_id[owner_gpu].remote_backend
    with sqlite3.connect(metadata_db) as conn:
        conn.execute(
            """
            insert into files(
              logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,
              checksum,state,created_at,updated_at,last_access_at,read_count,
              recompute_cost,remote_access_cost,producer_gpu,share_count,
              primary_tier,has_remote_copy,local_cache_owner_gpu,replica_state,
              cache_generation,last_promoted_at,last_demoted_at,
              dominant_gpu_id,dominant_gpu_read_share_x100,
              recent_dominant_gpu_id,recent_dominant_gpu_read_share_x100,
              recent_read_count,affinity_trend,target_local_replica_count,
              affinity_state,affinity_updated_at
            )
            values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            on conflict(logical_path) do update set
              gpu_id=excluded.gpu_id,
              tier=excluded.tier,
              backend_id=excluded.backend_id,
              physical_path=excluded.physical_path,
              size_bytes=excluded.size_bytes,
              state=excluded.state,
              read_count=0,
              recompute_cost=excluded.recompute_cost,
              remote_access_cost=excluded.remote_access_cost,
              producer_gpu=excluded.producer_gpu,
              share_count=excluded.share_count,
              primary_tier=excluded.primary_tier,
              has_remote_copy=excluded.has_remote_copy,
              local_cache_owner_gpu=excluded.local_cache_owner_gpu,
              replica_state=excluded.replica_state,
              updated_at=excluded.updated_at
            """,
            (
                logical_path,
                owner_gpu,
                "remote",
                backend_id,
                str(physical),
                size_mib * MIB,
                "",
                "COMMITTED",
                now,
                now,
                now,
                0,
                recompute_cost,
                remote_access_cost,
                owner_gpu,
                1,
                "remote",
                1,
                -1,
                "REMOTE_ONLY",
                0,
                0,
                0,
                -1,
                0,
                -1,
                0,
                0,
                "STABLE",
                0,
                "REMOTE_ONLY",
                now,
            ),
        )
        conn.commit()


def mark_cold(logical_prefix: str) -> None:
    with sqlite3.connect(metadata_db) as conn:
        conn.execute(
            """
            update files set
              recompute_cost=1,
              remote_access_cost=1,
              read_count=0,
              last_access_at=1,
              producer_gpu=gpu_id,
              share_count=1,
              affinity_state='REMOTE_COLD',
              affinity_trend='STABLE',
              target_local_replica_count=0
            where logical_path like ?
            """,
            (logical_prefix + "%",),
        )
        conn.commit()


def record(operation: str, group: str, owner_gpu: int, caller_gpu: int, path: Path,
           size_mib: float, seconds: float, note: str = "") -> None:
    rows.append(
        {
            "operation": operation,
            "group": group,
            "owner_gpu": owner_gpu,
            "caller_gpu": caller_gpu,
            "path": str(path),
            "size_mib": f"{size_mib:.2f}",
            "seconds": f"{seconds:.6f}",
            "mib_per_sec": f"{(size_mib / seconds) if seconds else 0:.2f}",
            "note": note,
        }
    )


def drop_page_cache(stage: str) -> None:
    if not drop_os_caches:
        return
    start = time.perf_counter()
    proc = subprocess.run(
        ["sudo", "-n", "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"],
        text=True,
        capture_output=True,
    )
    elapsed = time.perf_counter() - start
    note = "Linux page cache dropped before storage-tier measurement"
    if proc.returncode != 0:
        raise RuntimeError("cold-cache precondition failed: " + proc.stderr.strip())
    record("cache_control", stage, -1, -1, Path("/proc/sys/vm/drop_caches"), 0.0, elapsed, note)


def write_via_fuse(owner_gpu: int, shard_id: int, size_mib: int, group: str) -> Path:
    path = mount / f"gpu{owner_gpu}" / dataset_dir / f"shard-{shard_id:06d}.tokens"
    start = time.perf_counter()
    write_pattern_file(path, owner_gpu, shard_id, size_mib)
    elapsed = time.perf_counter() - start
    record("write", group, owner_gpu, owner_gpu, path, size_mib, elapsed)
    return path


def append_via_fuse(owner_gpu: int, shard_id: int, append_mib: int, group: str) -> Path:
    path = mount / f"gpu{owner_gpu}" / dataset_dir / f"shard-{shard_id:06d}.tokens"
    start_size = path.stat().st_size
    append_bytes = append_mib * MIB
    start = time.perf_counter()
    with path.open("ab", buffering=0) as f:
        written = 0
        chunk_id = start_size // chunk_bytes
        while written < append_bytes:
            n = min(chunk_bytes, append_bytes - written)
            f.write(token_chunk(owner_gpu, shard_id, chunk_id, n))
            written += n
            chunk_id += 1
        os.fsync(f.fileno())
    elapsed = time.perf_counter() - start
    record("write", group, owner_gpu, owner_gpu, path, append_mib, elapsed, "append existing local cache to force eviction")
    return path


def read_via_fuse(owner_gpu: int, caller_gpu: int, shard_id: int, group: str,
                  subdir: str | None = None) -> Path:
    return read_many_via_fuse(owner_gpu, caller_gpu, shard_id, group, 1, subdir)


def read_many_via_fuse(owner_gpu: int, caller_gpu: int, shard_id: int, group: str,
                       repeats: int, subdir: str | None = None) -> Path:
    if subdir is None:
        subdir = dataset_dir
    path = mount / f"gpu{owner_gpu}" / subdir / f"shard-{shard_id:06d}.tokens"
    code = r"""
import sys
import os
import subprocess
import time
from pathlib import Path
p = Path(sys.argv[1])
owner = int(sys.argv[2])
shard = int(sys.argv[3])
chunk = int(sys.argv[4])
repeats = int(sys.argv[5])
drop_cache = sys.argv[6] == "1"
drop_os_cache_per_read = sys.argv[7] == "1"
total = 0
elapsed = 0.0
for _ in range(repeats):
    first = b""
    if drop_os_cache_per_read:
        subprocess.run(
            ["sudo", "-n", "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    start = time.perf_counter()
    with p.open("rb", buffering=0) as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            if not first:
                first = data[:128]
            total += len(data)
        if drop_cache and hasattr(os, "posix_fadvise"):
            try:
                os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
            except OSError:
                pass
    elapsed += time.perf_counter() - start
expected = f"gpu={owner};shard={shard};chunk=0;".encode()
if expected not in first:
    raise SystemExit(f"unexpected content in {p}")
print(total)
print(elapsed)
"""
    env = os.environ.copy()
    env["TOKENFS_GPU_ID"] = str(caller_gpu)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(path),
            str(owner_gpu),
            str(shard_id),
            str(chunk_bytes),
            str(repeats),
            "1" if fadvise_dontneed else "0",
            "1" if drop_os_caches_per_read else "0",
        ],
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    stdout = proc.stdout.strip().splitlines()
    size_mib = int(stdout[0]) / MIB
    elapsed = float(stdout[1]) if len(stdout) > 1 else 0.0
    note = "" if repeats == 1 else f"batched {repeats} repeated reads in one loader process"
    if drop_os_caches_per_read:
        note = (note + "; " if note else "") + "Linux page cache dropped before each logical read"
    record("read", group, owner_gpu, caller_gpu, path, size_mib, elapsed, note)
    return path


def seed_remote_shard(owner_gpu: int, shard_id: int, size_mib: int, group: str,
                      subdir: str | None = None) -> Path:
    if subdir is None:
        subdir = dataset_dir
    physical = remote_root(owner_gpu) / f"gpu{owner_gpu}" / subdir / f"shard-{shard_id:06d}.tokens"
    write_pattern_file(physical, owner_gpu, shard_id, size_mib)
    logical = f"/gpu{owner_gpu}/{subdir}/shard-{shard_id:06d}.tokens"
    upsert_remote_meta(logical, owner_gpu, physical, size_mib)
    record("seed_remote", group, owner_gpu, owner_gpu, physical, size_mib, 0.0, "pre-existing remote canonical cache")
    return physical


# 1. 远端先存在权威 KV Cache，模拟真实场景里远端 canonical cache 已经准备好。
for i in range(remote_hot_shards):
    seed_remote_shard(0, 100 + i, shard_mib, "remote-canonical-hot")
seed_remote_shard(0, 200, shard_mib, "remote-canonical-cross-gpu", shared_dir)

job_start = time.monotonic_ns()

# 2. 本地缓存先被低价值旧 shard 占满，后续热点提升/预取必须与淘汰协同。
for i in range(cold_fill_shards):
    write_via_fuse(0, i, shard_mib, "cold-local-cache-fill")
mark_cold(f"/gpu0/{dataset_dir}/shard-00000")

# 3. 访问一个本地冷文件，提供本地直接命中的对照。
drop_page_cache("before-cold-local-read")
read_via_fuse(0, 0, 0, "cold-local-read")

# 4. 扩展已有本地文件制造容量压力，LRU/LFU/AURA 会被迫执行淘汰。
append_via_fuse(0, 0, pressure_shard_mib, "capacity-pressure-append-existing")

# 5. 重复访问远端热点 shard，第二次以后 AURA 可以触发热点提升。
drop_page_cache("before-remote-hot-first-read")
read_via_fuse(0, 0, 100, "remote-hot-first-read")
read_via_fuse(0, 0, 100, "remote-hot-second-read-promote")
time.sleep(1.0)
drop_page_cache("before-hot-rehit-after-promote")
read_many_via_fuse(0, 0, 100, "hot-rehit-after-promote", hot_rehit_reads)

# 6. 连续访问下一片 shard；开启预取时，这里应尽量变成本地读取。
if remote_hot_shards > 1:
    time.sleep(1.0)
    drop_page_cache("before-sequential-next-read-after-prefetch")
    read_via_fuse(0, 0, 101, "sequential-next-read-after-prefetch")
    drop_page_cache("before-sequential-rehit-after-prefetch")
    read_many_via_fuse(0, 0, 101, "sequential-rehit-after-prefetch", sequential_rehit_reads)

# 7. GPU1 多次访问 GPU0 的共享 KV Cache，触发跨 GPU 本地副本与后续命中。
drop_page_cache("before-cross-gpu-first-read")
read_via_fuse(0, 1, 200, "cross-gpu-first-read-create-replica", shared_dir)
if cross_gpu_reads > 1:
    time.sleep(1.0)
    drop_page_cache("before-cross-gpu-rehit-after-replica")
    read_many_via_fuse(0, 1, 200, "cross-gpu-rehit-after-replica", cross_gpu_reads - 1, shared_dir)

(result / "timing.json").write_text(json.dumps({"job_wall_s": (time.monotonic_ns() - job_start) / 1e9, "clock": "monotonic", "includes_workload_waits": True}) + "\n")

with (result / "summary.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "operation",
            "group",
            "owner_gpu",
            "caller_gpu",
            "path",
            "size_mib",
            "seconds",
            "mib_per_sec",
            "note",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)

lines = [
    "# TokenFS Token Workload 报告",
    "",
    f"实验命名空间：`{run_id}`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。",
    "",
    "| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |",
    "|---|---|---:|---:|---:|---:|---:|---|",
]
for row in rows:
    lines.append(
        f"| {row['operation']} | {row['group']} | {row['owner_gpu']} | {row['caller_gpu']} | "
        f"{row['size_mib']} | {row['seconds']} | {row['mib_per_sec']} | {row['note']} |"
    )
(result / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

"$project_root/scripts/tokenfsctl.py" --config "$config_file" metrics > "$result_root/metrics.txt"
"$project_root/scripts/tokenfsctl.py" --config "$config_file" metrics-json > "$result_root/metrics.json"
sqlite3 -header -csv "$metadata_db" "select name,value from metrics order by name;" > "$result_root/metrics.csv"
sqlite3 -header -csv "$metadata_db" \
  "select logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,read_count,affinity_state,target_local_replica_count,state from files order by logical_path;" \
  > "$result_root/files.csv"
sqlite3 -header -csv "$metadata_db" \
  "select logical_path,gpu_id,physical_path,size_bytes,state from local_replicas order by logical_path,gpu_id;" \
  > "$result_root/local_replicas.csv"

echo "TokenFS token workload report generated:"
echo "  $result_root/report.md"
echo "  $result_root/summary.csv"
echo "  $result_root/metrics.txt"
echo "  $result_root/metrics.json"
echo "  $result_root/metrics.csv"
echo "  $result_root/files.csv"
echo "  $result_root/local_replicas.csv"
