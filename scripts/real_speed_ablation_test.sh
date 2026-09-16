#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
result_root="${1:-$project_root/reports/latest/real-speed-ablation}"
base_config="${TOKENFS_CONFIG:-$project_root/config/tokenfs.dev.yaml}"
local_quota_mib="${TOKENFS_ABLATION_LOCAL_QUOTA_MIB:-32}"

tmp_dir="$(mktemp -d /tmp/tokenfs-real-ablation.XXXXXX)"

cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

rm -rf "$result_root"
mkdir -p "$result_root"

make_config() {
  local name="$1"
  local quota_mib="$2"
  local eviction_policy="$3"
  local placement_policy="$4"
  local promote="$5"
  local prefetch="$6"
  local cross_gpu="$7"
  local async_background="$8"
  local read_through="$9"
  local output="$tmp_dir/$name.yaml"

  python3 - "$base_config" "$output" "$quota_mib" "$eviction_policy" \
    "$placement_policy" "$promote" "$prefetch" "$cross_gpu" "$async_background" \
    "$read_through" <<'PY'
import os
import re
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
quota_mib = sys.argv[3]
eviction_policy = sys.argv[4]
placement_policy = sys.argv[5]
promote = sys.argv[6]
prefetch = sys.argv[7]
cross_gpu = sys.argv[8]
async_background = sys.argv[9]
read_through = sys.argv[10]

text = src.read_text(encoding="utf-8")

def replace_scalar(key: str, value: str) -> None:
    global text
    pattern = rf"(^\s*{re.escape(key)}:\s*).*$"
    updated, count = re.subn(pattern, rf"\g<1>{value}", text, flags=re.M)
    if count > 0:
        text = updated
        return
    marker = "  promote_on_read:"
    insert = f"  {key}: {value}\n"
    idx = text.find(marker)
    if idx >= 0:
        text = text[:idx] + insert + text[idx:]
    else:
        text += "\npolicy:\n" + insert

replace_scalar("local_eviction_policy", eviction_policy)
replace_scalar("placement_policy", placement_policy)
replace_scalar("promote_on_read", promote)
replace_scalar("prefetch_on_read", prefetch)
replace_scalar("cross_gpu_local_cache", cross_gpu)
replace_scalar("async_promote_on_read", async_background)
replace_scalar("async_cross_gpu_replica", async_background)
replace_scalar("read_through_cache", read_through)
replace_scalar("read_through_min_reads", os.environ.get("TOKENFS_READ_THROUGH_MIN_READS", "2"))
replace_scalar("value_promote_threshold", "100")
replace_scalar("promote_read_threshold", "2")
replace_scalar("migration_min_reuse_reads", "6")
replace_scalar("migration_min_benefit_x100", "150")
replace_scalar("migration_copy_cost_per_mib", "8")
replace_scalar("durable_local_cache", "false")
replace_scalar("fast_local_cache_hit", "true")
replace_scalar("speculative_copy_may_evict", "false")
replace_scalar(
    "qos_background_mib_per_sec_per_gpu",
    os.environ.get("TOKENFS_ABLATION_BACKGROUND_MIB_PER_SEC", "0"),
)
text = re.sub(r"(^\s*local_quota_mib:\s*)\d+.*$", rf"\g<1>{quota_mib}", text, flags=re.M)
dst.write_text(text, encoding="utf-8")
PY
  echo "$output"
}

run_case() {
  local name="$1"
  local quota_mib="$2"
  local eviction_policy="$3"
  local placement_policy="$4"
  local promote="$5"
  local prefetch="$6"
  local cross_gpu="$7"
  local async_background="$8"
  local read_through="$9"

  local config
  config="$(make_config "$name" "$quota_mib" "$eviction_policy" "$placement_policy" "$promote" "$prefetch" "$cross_gpu" "$async_background" "$read_through")"
  local out="$result_root/$name"
  local run_id="real-${name}-$(date +%s)-$$"
  echo "real-speed ablation: $name"
  TOKENFS_CONFIG="$config" \
  TOKENFS_RUN_ID="$run_id" \
  TOKENFS_SHARD_MIB="${TOKENFS_SHARD_MIB:-8}" \
  TOKENFS_REMOTE_HOT_SHARDS="${TOKENFS_REMOTE_HOT_SHARDS:-2}" \
  TOKENFS_COLD_FILL_SHARDS="${TOKENFS_COLD_FILL_SHARDS:-4}" \
  TOKENFS_CROSS_GPU_READS="${TOKENFS_CROSS_GPU_READS:-64}" \
  TOKENFS_PRESSURE_SHARD_MIB="${TOKENFS_PRESSURE_SHARD_MIB:-8}" \
  TOKENFS_HOT_REHIT_READS="${TOKENFS_HOT_REHIT_READS:-128}" \
  TOKENFS_SEQUENTIAL_REHIT_READS="${TOKENFS_SEQUENTIAL_REHIT_READS:-64}" \
  TOKENFS_CHUNK_MIB="${TOKENFS_CHUNK_MIB:-1}" \
  TOKENFS_FADVISE_DONTNEED="${TOKENFS_FADVISE_DONTNEED:-1}" \
  TOKENFS_DROP_OS_CACHES="${TOKENFS_DROP_OS_CACHES:-1}" \
  TOKENFS_DROP_OS_CACHES_PER_READ="${TOKENFS_DROP_OS_CACHES_PER_READ:-1}" \
    "$project_root/scripts/token_workload_test.sh" "$out" >/dev/null
}

run_case RemoteOnly 0 none remote_only false false false false false
run_case LocalFirst "$local_quota_mib" none local_first false false false false false
run_case LRU-Local "$local_quota_mib" lru local_first false false false false false
run_case LFU-Local "$local_quota_mib" lfu local_first false false false false false
run_case LRU-ReadThrough "$local_quota_mib" lru local_first true false false true true
run_case LFU-ReadThrough "$local_quota_mib" lfu local_first true false false true true
run_case AURA-no-prefetch "$local_quota_mib" value_aware value_aware true false true true false
run_case AURA-no-xgpu "$local_quota_mib" value_aware value_aware true true false true false
run_case AURA-Joint "$local_quota_mib" value_aware value_aware true true true true false

python3 - "$result_root" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
cases = [
    "RemoteOnly",
    "LocalFirst",
    "LRU-Local",
    "LFU-Local",
    "LRU-ReadThrough",
    "LFU-ReadThrough",
    "AURA-no-prefetch",
    "AURA-no-xgpu",
    "AURA-Joint",
]

def metric(metrics: dict, name: str) -> int:
    return int(metrics.get(name, 0))

def workload_seconds(path: Path) -> float:
    total = 0.0
    with path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["operation"] == "cache_control":
                continue
            total += float(row["seconds"])
    return total

rows = []
for case in cases:
    case_dir = root / case
    metrics = json.loads((case_dir / "metrics.json").read_text(encoding="utf-8"))
    read_ops = metric(metrics, "read_ops")
    write_ops = metric(metrics, "write_ops")
    rows.append(
        {
            "case": case,
            "read_local_rate_pct": round(metric(metrics, "read_local_rate_x100") / 100, 2),
            "write_local_rate_pct": round(metric(metrics, "write_local_rate_x100") / 100, 2),
            "remote_read_open": metric(metrics, "remote_read_open_count"),
            "local_read_open": metric(metrics, "local_read_open_count"),
            "promote_count": metric(metrics, "promote_count"),
            "prefetch_count": metric(metrics, "prefetch_count"),
            "evict_count": metric(metrics, "evict_count"),
            "evict_skip_hot": metric(metrics, "evict_skip_hot"),
            "spill_count": metric(metrics, "spill_count"),
            "cross_gpu_replica_create_count": metric(metrics, "cross_gpu_replica_create_count"),
            "cross_gpu_local_replica_hit": metric(metrics, "cross_gpu_local_replica_hit"),
            "prefetch_request_count": metric(metrics, "prefetch_request_count"),
            "local_cache_create_count": metric(metrics, "local_cache_create_count"),
            "local_cache_delete_count": metric(metrics, "local_cache_delete_count"),
            "avg_read_us": round(metric(metrics, "read_latency_us_total") / read_ops, 2) if read_ops else 0,
            "avg_write_us": round(metric(metrics, "write_latency_us_total") / write_ops, 2) if write_ops else 0,
            "workload_seconds": round(workload_seconds(case_dir / "summary.csv"), 4),
        }
    )

with (root / "strategy_summary.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

lines = [
    "# TokenFS 真实速度消融报告",
    "",
    "本报告用真实 TokenFS workload 跑论文消融分类，而不是简单的功能开关分类。",
    "",
    "| 策略 | 本地读命中率 % | 远端打开读取 | 热点提升 | 预取请求/成功 | 本地淘汰 | 跳过热点 | 溢写 | 跨 GPU 副本/命中 | 平均读 us | 平均写 us | workload 总耗时 s |",
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
]
for row in rows:
    lines.append(
        f"| {row['case']} | {row['read_local_rate_pct']} | {row['remote_read_open']} | "
        f"{row['promote_count']} | {row['prefetch_request_count']}/{row['prefetch_count']} | {row['evict_count']} | "
        f"{row['evict_skip_hot']} | {row['spill_count']} | "
        f"{row['cross_gpu_replica_create_count']}/{row['cross_gpu_local_replica_hit']} | {row['avg_read_us']} | "
        f"{row['avg_write_us']} | {row['workload_seconds']} |"
    )

lines.extend(
    [
        "",
        "## 策略含义",
        "",
        "- `RemoteOnly`：完全不用本地缓存，所有数据都从远端容量层读取。",
        "- `LocalFirst`：本地够用就写本地，本地不够就溢写远端，但不主动淘汰旧本地数据。",
        "- `LRU-Local`：本地不够时，淘汰最久没有访问的数据。",
        "- `LFU-Local`：本地不够时，淘汰累计访问次数最少的数据。",
        "- `LRU-ReadThrough`：远端读后也缓存到本地，本地不够时按 LRU 淘汰，是更公平的强 baseline。",
        "- `LFU-ReadThrough`：远端读后也缓存到本地，本地不够时按 LFU 淘汰，是更公平的强 baseline。",
        "- `AURA-no-prefetch`：保留价值感知和跨 GPU 副本，但关闭顺序预取，用于判断预取贡献。",
        "- `AURA-no-xgpu`：保留价值感知和顺序预取，但关闭跨 GPU 本地副本，用于判断 GPU 共享贡献。",
        "- `AURA-Joint`：同时考虑数据价值、GPU 热度/亲和、远端访问代价、容量约束和后台复制/淘汰；本 workload 会显式制造远端热点、本地冷缓存、连续 shard 和跨 GPU 访问，验证后台策略确实被触发。",
    ]
)
(root / "strategy_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

echo "TokenFS real-speed ablation report generated:"
echo "  $result_root/strategy_report.md"
echo "  $result_root/strategy_summary.csv"
