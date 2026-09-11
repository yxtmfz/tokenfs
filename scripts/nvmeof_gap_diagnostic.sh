#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="${TOKENFS_CONFIG:-$project_root/config/tokenfs.nvmeof.yaml}"
result_root="${1:-$project_root/reports/latest/paper-experiments/06_real_speed_benchmark/environment-gap}"
size_mib="${TOKENFS_GAP_SIZE_MIB:-256}"

mkdir -p "$result_root"

python3 - "$config" "$result_root" "$size_mib" <<'PY'
from __future__ import annotations

import csv
import os
import re
import sys
import time
from pathlib import Path

config = Path(sys.argv[1])
result = Path(sys.argv[2])
size_mib = int(sys.argv[3])
MIB = 1024 * 1024

text = config.read_text(encoding="utf-8")


def first_value_after(anchor: str, key: str) -> str:
    start = text.find(anchor)
    if start < 0:
        raise SystemExit(f"missing config section: {anchor}")
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", text[start:], re.M)
    if not match:
        raise SystemExit(f"missing config key after {anchor}: {key}")
    return match.group(1).strip().strip('"').strip("'")


local_root = Path(first_value_after("gpu_id: 0", "local_root"))
remote_root = Path(first_value_after("backends:", "root"))
local_dir = local_root / "__gap_diagnostic__"
remote_dir = remote_root / "__gap_diagnostic__"
local_dir.mkdir(parents=True, exist_ok=True)
remote_dir.mkdir(parents=True, exist_ok=True)

pattern = b"AURA-KV-GAP-DIAGNOSTIC\n"
block = (pattern * ((MIB // len(pattern)) + 1))[:MIB]


def advise(fd: int) -> None:
    if hasattr(os, "posix_fadvise") and hasattr(os, "POSIX_FADV_DONTNEED"):
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        except OSError:
            pass


def write_file(path: Path) -> float:
    start = time.perf_counter()
    with path.open("wb", buffering=0) as f:
        for _ in range(size_mib):
            written = f.write(block)
            if written != len(block):
                raise SystemExit(f"short write to {path}: {written}")
        f.flush()
        os.fsync(f.fileno())
        advise(f.fileno())
    return time.perf_counter() - start


def read_file(path: Path) -> float:
    start = time.perf_counter()
    total = 0
    with path.open("rb", buffering=0) as f:
        while True:
            data = f.read(MIB)
            if not data:
                break
            total += len(data)
        advise(f.fileno())
    if total != size_mib * MIB:
        raise SystemExit(f"short read from {path}: {total}")
    return time.perf_counter() - start


rows = []
for tier, directory in [("local", local_dir), ("remote", remote_dir)]:
    path = directory / f"gap-{os.getpid()}.bin"
    write_s = write_file(path)
    read_s = read_file(path)
    rows.append(
        {
            "tier": tier,
            "path": str(path),
            "size_mib": size_mib,
            "write_s": round(write_s, 6),
            "write_mib_s": round(size_mib / write_s, 2) if write_s else 0,
            "read_s": round(read_s, 6),
            "read_mib_s": round(size_mib / read_s, 2) if read_s else 0,
        }
    )

local = rows[0]
remote = rows[1]
read_gap = (
    float(local["read_mib_s"]) / float(remote["read_mib_s"])
    if float(remote["read_mib_s"])
    else 0.0
)
write_gap = (
    float(local["write_mib_s"]) / float(remote["write_mib_s"])
    if float(remote["write_mib_s"])
    else 0.0
)

with (result / "storage_gap_summary.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

mount_info = os.popen(f"findmnt -rn -o SOURCE,FSTYPE,TARGET --target {remote_root} 2>/dev/null").read().strip()
with (result / "storage_gap_report.md").open("w", encoding="utf-8") as f:
    f.write("# NVMe-oF 本地/远端环境差距诊断\n\n")
    f.write(f"- 配置文件：`{config}`\n")
    f.write(f"- 本地目录：`{local_root}`\n")
    f.write(f"- 远端目录：`{remote_root}`\n")
    f.write(f"- 远端挂载证据：`{mount_info or '未检测到挂载'}`\n")
    f.write(f"- 测试数据量：`{size_mib} MiB`\n\n")
    f.write("| 层级 | 写吞吐 MiB/s | 读吞吐 MiB/s |\n")
    f.write("|---|---:|---:|\n")
    for row in rows:
        f.write(f"| {row['tier']} | {row['write_mib_s']} | {row['read_mib_s']} |\n")
    f.write("\n")
    f.write(f"- 本地/远端读吞吐比：`{read_gap:.3f}x`\n")
    f.write(f"- 本地/远端写吞吐比：`{write_gap:.3f}x`\n\n")
    if read_gap < 1.25:
        f.write(
            "结论：当前环境中本地层和 NVMe-oF 远端层读性能差距很小，"
            "即使策略显著减少远端访问，也不容易转化为明显端到端提速。"
            "这种环境适合验证协议接入、元数据、后台动作和远端访问减少，"
            "但不适合单独支撑“大幅速度提升”的论文结论。\n"
        )
    else:
        f.write(
            "结论：当前环境已经存在可观的本地/远端读性能差距，"
            "AURA 的本地缓存、预取和跨 GPU 副本策略有条件转化为端到端速度收益。\n"
        )

print(result / "storage_gap_summary.csv")
print(result / "storage_gap_report.md")
PY
