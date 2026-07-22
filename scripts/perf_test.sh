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
  local size="$4"

  mkdir -p "$(dirname "$filename")" "$json_dir"
  fio \
    --name="$name" \
    --filename="$filename" \
    --rw="$rw" \
    --bs=1m \
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

"$project_root/scripts/reset_dev_state.sh" "$mount_point"
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$project_root/config/tokenfs.dev.yaml" "$mount_point" >/dev/null

rm -rf "$result_root"
mkdir -p "$json_dir"

echo "perf: direct local backend write"
run_fio direct-local-write /var/lib/tokenfs/direct-local/perf/direct-local.bin write 32m

echo "perf: direct remote-sim backend write"
run_fio direct-remote-write /var/lib/tokenfs/remote-sim/direct-perf/direct-remote.bin write 32m

echo "perf: TokenFS local write"
run_fio tokenfs-local-write "$mount_point/gpu0/perf/tokenfs-local.tokens" write 32m
sync

echo "perf: TokenFS remote spill write"
run_fio tokenfs-remote-spill-write "$mount_point/gpu0/perf/tokenfs-remote-spill.tokens" write 80m
sync

echo "perf: TokenFS local read"
run_fio tokenfs-local-read "$mount_point/gpu0/perf/tokenfs-local.tokens" read 32m

echo "perf: TokenFS remote read"
run_fio tokenfs-remote-read "$mount_point/gpu0/perf/tokenfs-remote-spill.tokens" read 80m

"$project_root/scripts/perf_report.py" "$json_dir" "$result_root"
"$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null

echo "TokenFS performance report generated:"
echo "  $result_root/report.md"
echo "  $result_root/report.html"
echo "  $result_root/summary.csv"
