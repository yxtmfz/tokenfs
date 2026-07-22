#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mount_point="${TOKENFS_MOUNT:-/mnt/tokenfs}"
metadata_db="${TOKENFS_DB:-/var/lib/tokenfs/metadata/tokenfs.db}"
result_root="${1:-$project_root/reports/latest}"

shard_mib="${TOKENFS_SHARD_MIB:-16}"
large_shard_mib="${TOKENFS_LARGE_SHARD_MIB:-96}"
normal_shards="${TOKENFS_NORMAL_SHARDS:-4}"
chunk_mib="${TOKENFS_CHUNK_MIB:-1}"

cleanup() {
  "$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$project_root/scripts/reset_dev_state.sh" "$mount_point" >/dev/null
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$project_root/config/tokenfs.dev.yaml" "$mount_point" >/dev/null

rm -rf "$result_root"
mkdir -p "$result_root"

python3 - "$mount_point" "$result_root" "$shard_mib" "$large_shard_mib" "$normal_shards" "$chunk_mib" <<'PY'
import csv
import os
import sqlite3
import sys
import time
from pathlib import Path

mount = Path(sys.argv[1])
result = Path(sys.argv[2])
shard_mib = int(sys.argv[3])
large_shard_mib = int(sys.argv[4])
normal_shards = int(sys.argv[5])
chunk_mib = int(sys.argv[6])
chunk_bytes = chunk_mib * 1024 * 1024

rows = []

def token_chunk(gpu_id: int, shard_id: int, chunk_id: int, size: int) -> bytes:
    header = f"gpu={gpu_id};shard={shard_id};chunk={chunk_id};".encode()
    pattern = (header + b"tokenfs-sequential-token-data\n")
    return (pattern * ((size // len(pattern)) + 1))[:size]

def write_shard(gpu_id: int, shard_id: int, size_mib: int, preallocate: bool) -> Path:
    path = mount / f"gpu{gpu_id}" / "dataset-a" / f"shard-{shard_id:06d}.tokens"
    path.parent.mkdir(parents=True, exist_ok=True)
    size = size_mib * 1024 * 1024
    start = time.perf_counter()
    with path.open("wb", buffering=0) as f:
        if preallocate:
            os.posix_fallocate(f.fileno(), 0, size)
        written = 0
        chunk_id = 0
        while written < size:
            n = min(chunk_bytes, size - written)
            f.write(token_chunk(gpu_id, shard_id, chunk_id, n))
            written += n
            chunk_id += 1
        os.fsync(f.fileno())
    elapsed = time.perf_counter() - start
    rows.append({
        "operation": "write",
        "gpu_id": gpu_id,
        "path": str(path),
        "size_mib": size_mib,
        "preallocate": int(preallocate),
        "seconds": f"{elapsed:.6f}",
        "mib_per_sec": f"{(size_mib / elapsed) if elapsed else 0:.2f}",
    })
    return path

def read_shard(path: Path, gpu_id: int, shard_id: int) -> None:
    size_mib = path.stat().st_size / 1024 / 1024
    start = time.perf_counter()
    total = 0
    first = b""
    with path.open("rb", buffering=0) as f:
        while True:
            data = f.read(chunk_bytes)
            if not data:
                break
            if not first:
                first = data[:128]
            total += len(data)
    elapsed = time.perf_counter() - start
    expected = f"gpu={gpu_id};shard={shard_id};chunk=0;".encode()
    if expected not in first:
        raise RuntimeError(f"unexpected shard content in {path}")
    rows.append({
        "operation": "read",
        "gpu_id": gpu_id,
        "path": str(path),
        "size_mib": f"{size_mib:.2f}",
        "preallocate": "",
        "seconds": f"{elapsed:.6f}",
        "mib_per_sec": f"{(size_mib / elapsed) if elapsed else 0:.2f}",
    })

paths = []
for i in range(normal_shards):
    paths.append((write_shard(0, i, shard_mib, True), 0, i))
paths.append((write_shard(0, 900000, large_shard_mib, True), 0, 900000))
paths.append((write_shard(1, 0, shard_mib, True), 1, 0))

for path, gpu_id, shard_id in paths:
    read_shard(path, gpu_id, shard_id)

with (result / "summary.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["operation", "gpu_id", "path", "size_mib", "preallocate", "seconds", "mib_per_sec"],
    )
    writer.writeheader()
    writer.writerows(rows)

lines = [
    "# TokenFS Token Workload Report",
    "",
    "This workload simulates large ML token shard files with preallocation and sequential I/O.",
    "",
    "| operation | gpu | size MiB | preallocate | seconds | MiB/s | path |",
    "|---|---:|---:|---:|---:|---:|---|",
]
for row in rows:
    lines.append(
        f"| {row['operation']} | {row['gpu_id']} | {row['size_mib']} | "
        f"{row['preallocate']} | {row['seconds']} | {row['mib_per_sec']} | `{row['path']}` |"
    )
(result / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

"$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" metrics > "$result_root/metrics.txt"
sqlite3 -header -csv "$metadata_db" \
  "select logical_path,gpu_id,tier,physical_path,size_bytes,checksum,state from files order by logical_path;" \
  > "$result_root/files.csv"

echo "TokenFS token workload report generated:"
echo "  $result_root/report.md"
echo "  $result_root/summary.csv"
echo "  $result_root/metrics.txt"
echo "  $result_root/files.csv"
