#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
result_root="${1:-$project_root/reports/latest/paper-experiments/07_real_speed_repeat}"
runs="${TOKENFS_REPEAT_RUNS:-3}"
shard_mib="${TOKENFS_REPEAT_SHARD_MIB:-32}"
quota_mib="${TOKENFS_REPEAT_LOCAL_QUOTA_MIB:-$((shard_mib * 5))}"
label="${TOKENFS_REPEAT_LABEL:-${shard_mib}MiB shards, ${quota_mib}MiB local quota, ${runs} repeated runs, verified NVMe-oF}"

rm -rf "$result_root"
mkdir -p "$result_root/runs"

echo "TokenFS repeated real-speed benchmark"
echo "  result_root=$result_root"
echo "  runs=$runs"
echo "  shard_mib=$shard_mib"
echo "  local_quota_mib=$quota_mib"

for run in $(seq 1 "$runs"); do
  run_name="$(printf 'run-%02d' "$run")"
  run_dir="$result_root/runs/$run_name"
  echo "==> $run_name/$runs"
  TOKENFS_SHARD_MIB="$shard_mib" \
  TOKENFS_ABLATION_LOCAL_QUOTA_MIB="$quota_mib" \
  TOKENFS_REAL_SPEED_ENV="${TOKENFS_REAL_SPEED_ENV:-Repeated real TokenFS workload on verified NVMe-oF, $label}" \
    "$project_root/scripts/real_speed_benchmark.sh" "$run_dir"
done

python3 "$project_root/scripts/real_speed_repeat_report.py" "$result_root" --label "$label"

echo "TokenFS repeated benchmark generated:"
echo "  $result_root/repeat_report.md"
echo "  $result_root/repeat_summary.csv"
echo "  $result_root/repeat_runs.csv"
