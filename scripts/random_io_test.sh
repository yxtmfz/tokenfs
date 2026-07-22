#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mount_point="${TOKENFS_MOUNT:-/mnt/tokenfs}"
result_root="${1:-$project_root/reports/latest}"
json_dir="$result_root/fio-json"

run_fio() {
  local name="$1"
  local filename="$2"
  local rw="$3"
  local bs="$4"
  local size="$5"

  mkdir -p "$(dirname "$filename")" "$json_dir"
  fio \
    --name="$name" \
    --filename="$filename" \
    --rw="$rw" \
    --bs="$bs" \
    --size="$size" \
    --ioengine=sync \
    --iodepth=1 \
    --numjobs=1 \
    --direct=0 \
    --fallocate=none \
    --group_reporting \
    --output-format=json \
    --output="$json_dir/$name.json"
}

cleanup() {
  "$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$project_root/scripts/reset_dev_state.sh" "$mount_point" >/dev/null
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$project_root/config/tokenfs.dev.yaml" "$mount_point" >/dev/null

rm -rf "$result_root"
mkdir -p "$json_dir"

echo "random: direct local 4k/16k"
run_fio direct-local-randwrite-4k /var/lib/tokenfs/direct-local/random/direct-local-4k.bin randwrite 4k 16m
run_fio direct-local-randread-4k /var/lib/tokenfs/direct-local/random/direct-local-4k.bin randread 4k 16m
run_fio direct-local-randwrite-16k /var/lib/tokenfs/direct-local/random/direct-local-16k.bin randwrite 16k 16m
run_fio direct-local-randread-16k /var/lib/tokenfs/direct-local/random/direct-local-16k.bin randread 16k 16m

echo "random: TokenFS local 4k/16k"
mkdir -p "$mount_point/gpu0/random"
run_fio tokenfs-local-randwrite-4k "$mount_point/gpu0/random/local-4k.tokens" randwrite 4k 16m
run_fio tokenfs-local-randread-4k "$mount_point/gpu0/random/local-4k.tokens" randread 4k 16m
run_fio tokenfs-local-randwrite-16k "$mount_point/gpu0/random/local-16k.tokens" randwrite 16k 16m
run_fio tokenfs-local-randread-16k "$mount_point/gpu0/random/local-16k.tokens" randread 16k 16m

TOKENFS_PERF_TITLE="TokenFS 随机 I/O 性能报告" \
TOKENFS_PERF_CONTEXT="本报告用于观察 4 KiB 与 16 KiB 小块随机访问下的 IOPS、平均延迟和 P99 延迟。该测试更接近小块 token block 或碎片化访问场景，和 1 MiB 顺序 shard 测试互为补充。" \
"$project_root/scripts/perf_report.py" "$json_dir" "$result_root"

"$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" metrics > "$result_root/metrics.txt"
sqlite3 -header -csv /var/lib/tokenfs/metadata/tokenfs.db \
  "select logical_path,gpu_id,tier,physical_path,size_bytes,checksum,state from files order by logical_path;" \
  > "$result_root/files.csv"

echo "TokenFS random I/O report generated:"
echo "  $result_root/report.md"
echo "  $result_root/report.html"
echo "  $result_root/summary.csv"
