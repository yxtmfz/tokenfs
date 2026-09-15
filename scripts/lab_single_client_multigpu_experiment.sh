#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="${TOKENFS_CONFIG:-$project_root/config/tokenfs.nvmeof.yaml}"
backend_id="${TOKENFS_BACKEND_ID:-remote0}"
result_root="${1:-$project_root/reports/latest/paper-experiments/08_lab_single_client_multigpu}"

gap_dir="$result_root/01_environment_gap"
single_dir="$result_root/02_single_run_speed"
repeat_dir="$result_root/03_repeat_speed"
evidence="$result_root/environment_evidence.txt"
report="$result_root/lab_single_client_multigpu_report.md"

read_backend_value() {
  local key="$1"
  python3 - "$config" "$backend_id" "$key" <<'PY'
import sys
from pathlib import Path

config = Path(sys.argv[1])
backend_id = sys.argv[2]
key = sys.argv[3]
section = ""
current = None
found = {}

def clean(value):
    return value.strip().strip('"').strip("'")

for raw in config.read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].rstrip()
    if not line.strip():
        continue
    if not line.startswith(" ") and line.endswith(":"):
        section = line[:-1]
        current = None
        continue
    stripped = line.strip()
    if section == "backends" and stripped.startswith("- "):
        if found.get("id") == backend_id:
            break
        current = {}
        found = current
        stripped = stripped[2:].strip()
    if current is None or ":" not in stripped:
        continue
    k, v = stripped.split(":", 1)
    current[k.strip()] = clean(v)

if found.get("id") != backend_id:
    found = {}
print(found.get(key, ""))
PY
}

die() {
  echo "error: $*" >&2
  exit 2
}

require_file() {
  [[ -f "$1" ]] || die "missing file: $1"
}

verify_nvmeof_mount() {
  local backend_type root mount_point target_ip source
  backend_type="$(read_backend_value type)"
  root="$(read_backend_value root)"
  mount_point="$(read_backend_value nvme_mount)"
  target_ip="$(read_backend_value nvme_target_ip)"
  mount_point="${mount_point:-$root}"

  [[ "$backend_type" == "nvmeof" ]] || die "backend '$backend_id' must be type=nvmeof"
  [[ -n "$root" ]] || die "backend '$backend_id' root is empty"
  [[ "$root" == "$mount_point" ]] || die "backend root and nvme_mount should point to the same directory"
  [[ -n "$target_ip" && "$target_ip" != "__SSD_TARGET_IP__" ]] || die "nvme_target_ip is not configured"
  [[ "$target_ip" != "localhost" && "$target_ip" != 127.* ]] || die "target IP must be a real remote address, not localhost"
  command -v findmnt >/dev/null 2>&1 || die "findmnt command is required"
  findmnt -rn --target "$root" >/dev/null || die "$root is not mounted"
  source="$(findmnt -rn -o SOURCE --target "$root" | head -n 1)"
  [[ "$source" == /dev/nvme* ]] || die "$root is mounted from '$source', not /dev/nvme*"
}

write_environment_evidence() {
  mkdir -p "$result_root"
  {
    echo "time=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "config=$config"
    echo "backend_id=$backend_id"
    echo "host=$(hostname)"
    echo
    echo "[uname]"
    uname -a || true
    echo
    echo "[ip address]"
    ip -br addr || true
    echo
    echo "[remote backend config]"
    echo "type=$(read_backend_value type)"
    echo "root=$(read_backend_value root)"
    echo "nvme_transport=$(read_backend_value nvme_transport)"
    echo "nvme_target_ip=$(read_backend_value nvme_target_ip)"
    echo "nvme_port=$(read_backend_value nvme_port)"
    echo "nvme_subnqn=$(read_backend_value nvme_subnqn)"
    echo "nvme_device=$(read_backend_value nvme_device)"
    echo "nvme_mount=$(read_backend_value nvme_mount)"
    echo
    echo "[findmnt remote]"
    findmnt --target "$(read_backend_value root)" || true
    echo
    echo "[df]"
    df -h "$(read_backend_value root)" || true
    echo
    echo "[lsblk]"
    lsblk || true
    echo
    echo "[nvme list]"
    if command -v nvme >/dev/null 2>&1; then
      nvme list || true
    else
      echo "nvme command not found"
    fi
  } > "$evidence"
}

write_lab_report() {
  python3 - "$result_root" "$config" "$evidence" "$report" <<'PY'
from __future__ import annotations

import csv
import sys
from pathlib import Path

root = Path(sys.argv[1])
config = Path(sys.argv[2])
evidence = Path(sys.argv[3])
report = Path(sys.argv[4])

def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

gap_rows = read_csv(root / "01_environment_gap" / "storage_gap_summary.csv")
single_rows = read_csv(root / "02_single_run_speed" / "real_speed_summary.csv")
repeat_rows = read_csv(root / "03_repeat_speed" / "repeat_summary.csv")

lines = [
    "# 单客户端多逻辑 GPU + 真实 NVMe-oF 实验汇总",
    "",
    "本报告对应当前推荐真实实验路线：在一个 Ubuntu 客户端中模拟 `gpu0/gpu1/gpu2` 等多逻辑 GPU 本地缓存目录，远端容量层必须是通过 Linux NVMe/TCP 挂载到 `/srv/tokenfs/remote0` 的真实 NVMe-oF 目录。",
    "",
    "```text",
    "Ubuntu VM / 内网客户端",
    "  ├── TokenFS / AURA-KV",
    "  ├── gpu0/gpu1/gpu2 本地缓存目录",
    "  └── /srv/tokenfs/remote0  ->  远端服务器 NVMe-oF Target",
    "```",
    "",
    f"- 配置文件：`{config}`",
    f"- 环境证据：`{evidence}`",
    "",
    "## 1. 环境差距诊断",
    "",
]

if gap_rows:
    lines += [
        "| 层级 | 写吞吐 MiB/s | 读吞吐 MiB/s |",
        "|---|---:|---:|",
    ]
    for row in gap_rows:
        lines.append(f"| {row.get('tier','')} | {row.get('write_mib_s','')} | {row.get('read_mib_s','')} |")
else:
    lines.append("尚未生成环境差距诊断结果。")

lines += [
    "",
    "## 2. 单轮真实速度消融",
    "",
]
if single_rows:
    lines += [
        "| 策略 | 总数据 MiB | 总耗时 s | 有效吞吐 MiB/s | 加速比 | 本地读命中率 % | 远端打开读取 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in single_rows:
        lines.append(
            f"| `{row.get('case','')}` | {row.get('total_mib','')} | {row.get('wall_time_s','')} | "
            f"{row.get('effective_mib_s','')} | {row.get('speedup_vs_baseline','')} | "
            f"{row.get('local_read_hit_rate_pct','')} | {row.get('remote_read_open','')} |"
        )
else:
    lines.append("尚未生成单轮真实速度结果。")

lines += [
    "",
    "## 3. 三轮重复真实速度消融",
    "",
]
if repeat_rows:
    lines += [
        "| 策略 | 轮数 | 平均总耗时 s | 耗时范围 s | 平均有效吞吐 MiB/s | 平均加速比 | 本地读命中率均值 % | 远端打开读取均值 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in repeat_rows:
        lines.append(
            f"| `{row.get('case','')}` | {row.get('runs','')} | {row.get('wall_time_s_mean','')} | "
            f"{row.get('wall_time_s_min','')}-{row.get('wall_time_s_max','')} | "
            f"{row.get('effective_mib_s_mean','')} | {row.get('speedup_vs_baseline_mean','')} | "
            f"{row.get('local_read_hit_rate_pct_mean','')} | {row.get('remote_read_open_mean','')} |"
        )
else:
    lines.append("尚未生成三轮重复真实速度结果。")

lines += [
    "",
    "## 4. 论文解释口径",
    "",
    "- 这套实验可以证明：TokenFS/FUSE、AURA 策略、后台任务、元数据反馈和真实 NVMe-oF 远端容量层已经接在同一条运行路径上。",
    "- `gpu0/gpu1/gpu2` 是同一客户端内的逻辑 GPU 节点，用来验证多 GPU 访问分布、亲和副本选择和本地缓存保留策略。",
    "- 它不能直接等同于多台真实 GPU 物理服务器并发访问同一个远端 SSD 池；如果论文写作需要多物理节点结论，还需要额外机器。",
    "- 判断速度是否提升优先看三轮重复结果中的 `wall_time_s_mean`、`effective_mib_s_mean` 和 `speedup_vs_baseline_mean`，机制是否生效则看本地命中率、远端打开读取次数、promote/prefetch/evict/cross-GPU 副本统计。",
]

report.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

require_file "$config"
mkdir -p "$result_root"

echo "AURA-KV lab single-client multigpu experiment"
echo "  config=$config"
echo "  result_root=$result_root"
echo

"$project_root/scripts/check_environment.sh" "$config"
verify_nvmeof_mount
write_environment_evidence

echo
echo "==> environment gap diagnostic"
TOKENFS_CONFIG="$config" \
TOKENFS_BACKEND_ID="$backend_id" \
TOKENFS_GAP_SIZE_MIB="${TOKENFS_GAP_SIZE_MIB:-512}" \
  "$project_root/scripts/nvmeof_gap_diagnostic.sh" "$gap_dir"

echo
echo "==> single-run real speed ablation"
TOKENFS_CONFIG="$config" \
TOKENFS_BACKEND_ID="$backend_id" \
TOKENFS_SHARD_MIB="${TOKENFS_SHARD_MIB:-32}" \
TOKENFS_ABLATION_LOCAL_QUOTA_MIB="${TOKENFS_ABLATION_LOCAL_QUOTA_MIB:-160}" \
TOKENFS_REAL_SPEED_ENV="${TOKENFS_REAL_SPEED_ENV:-Single-client multi-logical-GPU TokenFS workload on verified remote NVMe-oF}" \
  "$project_root/scripts/real_speed_benchmark.sh" "$single_dir"

echo
echo "==> repeated real speed ablation"
TOKENFS_CONFIG="$config" \
TOKENFS_BACKEND_ID="$backend_id" \
TOKENFS_REPEAT_RUNS="${TOKENFS_REPEAT_RUNS:-3}" \
TOKENFS_REPEAT_SHARD_MIB="${TOKENFS_REPEAT_SHARD_MIB:-32}" \
TOKENFS_REPEAT_LOCAL_QUOTA_MIB="${TOKENFS_REPEAT_LOCAL_QUOTA_MIB:-160}" \
TOKENFS_REPEAT_LABEL="${TOKENFS_REPEAT_LABEL:-single-client multi-logical-GPU, remote NVMe-oF, 32MiB shards, 160MiB quota, 3 runs}" \
  "$project_root/scripts/real_speed_repeat_benchmark.sh" "$repeat_dir"

write_lab_report

echo
echo "AURA-KV lab experiment generated:"
echo "  $report"
echo "  $evidence"
echo "  $gap_dir/storage_gap_report.md"
echo "  $single_dir/real_speed_report.md"
echo "  $repeat_dir/repeat_report.md"
