#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target_ip="${TOKENFS_NVME_TARGET_IP:-${1:-}}"
target_port="${TOKENFS_NVME_TARGET_PORT:-4420}"
subnqn="${TOKENFS_NVME_SUBNQN:-nqn.2026-07.local.tokenfs:remote0}"
remote_mount="${TOKENFS_NVME_MOUNT:-/srv/tokenfs/remote0}"
tokenfs_mount="${TOKENFS_MOUNT:-/mnt/tokenfs}"
result_root="${TOKENFS_RESULT_ROOT:-$project_root/reports/nvmeof-perf/latest}"
json_dir="$result_root/fio-json"
temp_config="/tmp/tokenfs.nvmeof.perf.yaml"

small_size="${TOKENFS_PERF_SMALL_SIZE:-32m}"
large_size="${TOKENFS_PERF_LARGE_SIZE:-96m}"
block_size="${TOKENFS_PERF_BS:-1m}"

if [[ -z "$target_ip" ]]; then
  cat >&2 <<EOF
Usage: TOKENFS_NVME_TARGET_IP=<target-vm-ip> $0
   or: $0 <target-vm-ip>

Run this on tokenfs-dev after tokenfs-target has started setup_nvme_target.sh.
EOF
  exit 2
fi

cleanup() {
  "$project_root/scripts/stop_tokenfs.sh" "$tokenfs_mount" >/dev/null 2>&1 || true
}
trap cleanup EXIT

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
    --bs="$block_size" \
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

echo "Preparing NVMe-oF backend $target_ip:$target_port"
TOKENFS_NVME_TARGET_IP="$target_ip" \
TOKENFS_NVME_TARGET_PORT="$target_port" \
TOKENFS_NVME_SUBNQN="$subnqn" \
TOKENFS_NVME_MOUNT="$remote_mount" \
  "$project_root/scripts/connect_nvme.sh" --allow-format --chown-current

python3 - "$project_root/config/tokenfs.dev.yaml" "$temp_config" "$remote_mount" "$target_ip" "$target_port" "$subnqn" <<'PY'
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
mount = sys.argv[3]
target_ip = sys.argv[4]
target_port = sys.argv[5]
subnqn = sys.argv[6]

text = source.read_text(encoding="utf-8")
text = text.replace("root: /var/lib/tokenfs/remote-sim", f"root: {mount}")
text = text.replace("type: directory", "type: nvmeof", 1)
text = text.replace('nvme_target_ip: "__SSD_TARGET_IP__"', f'nvme_target_ip: "{target_ip}"')
text = text.replace('nvme_subnqn: "__SUBSYSTEM_NQN__"', f'nvme_subnqn: "{subnqn}"')
text = text.replace('nvme_port: "4420"', f'nvme_port: "{target_port}"')
target.write_text(text, encoding="utf-8")
PY

"$project_root/scripts/reset_dev_state.sh" "$tokenfs_mount" >/dev/null
rm -rf "$remote_mount/gpu0/perf" "$remote_mount/gpu1/perf"
mkdir -p "$remote_mount/gpu0/perf" "$remote_mount/gpu1/perf"
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$temp_config" "$tokenfs_mount" >/dev/null

rm -rf "$result_root"
mkdir -p "$json_dir"

echo "perf: direct local backend write/read"
run_fio direct-local-write /var/lib/tokenfs/local/gpu0/perf/direct-local.bin write "$small_size"
sync
run_fio direct-local-read /var/lib/tokenfs/local/gpu0/perf/direct-local.bin read "$small_size"

echo "perf: direct NVMe-oF backend write/read"
run_fio direct-remote-write "$remote_mount/gpu0/perf/direct-remote.bin" write "$small_size"
sync
run_fio direct-remote-read "$remote_mount/gpu0/perf/direct-remote.bin" read "$small_size"

echo "perf: TokenFS local write/read"
run_fio tokenfs-local-write "$tokenfs_mount/gpu0/perf/tokenfs-local.tokens" write "$small_size"
sync
run_fio tokenfs-local-read "$tokenfs_mount/gpu0/perf/tokenfs-local.tokens" read "$small_size"

echo "perf: TokenFS NVMe-oF remote spill write/read"
run_fio tokenfs-remote-spill-write "$tokenfs_mount/gpu0/perf/tokenfs-remote-spill.tokens" write "$large_size"
sync
run_fio tokenfs-remote-read "$tokenfs_mount/gpu0/perf/tokenfs-remote-spill.tokens" read "$large_size"

TOKENFS_PERF_TITLE="TokenFS 双 VM NVMe-oF 性能基线报告" \
TOKENFS_PERF_CONTEXT="本报告使用两台 Ubuntu VM 运行真实 Linux NVMe/TCP Host/Target 链路。远端后端挂载点为 $remote_mount，Target 为 $target_ip:$target_port。结果可用于验证协议接入和相对开销，最终论文性能数据仍应在真实 SSD 与实验室网络上重新采集。" \
  "$project_root/scripts/perf_report.py" "$json_dir" "$result_root"

"$project_root/scripts/tokenfsctl.py" --config "$temp_config" metrics > "$result_root/metrics.txt"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" status > "$result_root/status.txt"
sqlite3 -header -csv /var/lib/tokenfs/metadata/tokenfs.db \
  "select logical_path,gpu_id,tier,physical_path,size_bytes,checksum,state from files order by logical_path;" \
  > "$result_root/files.csv"
findmnt "$remote_mount" > "$result_root/mount.txt" || true
nvme list > "$result_root/nvme-list.txt" || true
uname -a > "$result_root/uname.txt"

echo "TokenFS NVMe-oF performance report generated:"
echo "  $result_root/report.md"
echo "  $result_root/report.html"
echo "  $result_root/summary.csv"
echo "  $result_root/metrics.txt"
echo "  $result_root/files.csv"
