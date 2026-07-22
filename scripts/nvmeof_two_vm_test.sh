#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target_ip="${TOKENFS_NVME_TARGET_IP:-${1:-}}"
target_port="${TOKENFS_NVME_TARGET_PORT:-4420}"
subnqn="${TOKENFS_NVME_SUBNQN:-nqn.2026-07.local.tokenfs:remote0}"
mount_point="${TOKENFS_NVME_MOUNT:-/srv/tokenfs/remote0}"
tokenfs_mount="${TOKENFS_MOUNT:-/mnt/tokenfs}"
metadata_db="${TOKENFS_DB:-/var/lib/tokenfs/metadata/tokenfs.db}"
result_root="${TOKENFS_RESULT_ROOT:-$project_root/reports/latest}"
temp_config="/tmp/tokenfs.nvmeof.yaml"

if [[ -z "$target_ip" ]]; then
  cat >&2 <<EOF
Usage: TOKENFS_NVME_TARGET_IP=<target-vm-ip> $0
   or: $0 <target-vm-ip>

Run this on the TokenFS client VM after running setup_nvme_target.sh on the target VM.
EOF
  exit 2
fi

cleanup() {
  "$project_root/scripts/stop_tokenfs.sh" "$tokenfs_mount" >/dev/null 2>&1 || true
}
trap cleanup EXIT

mkdir -p "$result_root"

echo "Connecting real NVMe/TCP path to $target_ip:$target_port"
TOKENFS_NVME_TARGET_IP="$target_ip" \
TOKENFS_NVME_TARGET_PORT="$target_port" \
TOKENFS_NVME_SUBNQN="$subnqn" \
TOKENFS_NVME_MOUNT="$mount_point" \
  "$project_root/scripts/connect_nvme.sh" --allow-format --chown-current

python3 - "$project_root/config/tokenfs.dev.yaml" "$temp_config" "$mount_point" "$target_ip" "$target_port" "$subnqn" <<'PY'
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
text = text.replace('type: directory', 'type: nvmeof', 1)
text = text.replace('nvme_target_ip: "__SSD_TARGET_IP__"', f'nvme_target_ip: "{target_ip}"')
text = text.replace('nvme_subnqn: "__SUBSYSTEM_NQN__"', f'nvme_subnqn: "{subnqn}"')
text = text.replace('nvme_port: "4420"', f'nvme_port: "{target_port}"')
target.write_text(text, encoding="utf-8")
PY

"$project_root/scripts/reset_dev_state.sh" "$tokenfs_mount" >/dev/null
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$temp_config" "$tokenfs_mount" >/dev/null

echo "Writing TokenFS local and NVMe-oF spill files"
mkdir -p "$tokenfs_mount/gpu0/nvmeof-demo"
printf "hello local tokenfs over nvmeof test\n" > "$tokenfs_mount/gpu0/nvmeof-demo/local.tokens"
python3 - "$tokenfs_mount/gpu0/nvmeof-demo/remote-spill.tokens" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
size = 96 * 1024 * 1024
chunk = b"tokenfs-nvmeof-sequential-shard\n" * 1024
with path.open("wb", buffering=0) as f:
    os.posix_fallocate(f.fileno(), 0, size)
    written = 0
    while written < size:
        n = min(len(chunk), size - written)
        f.write(chunk[:n])
        written += n
    os.fsync(f.fileno())
PY

grep -q "hello local" "$tokenfs_mount/gpu0/nvmeof-demo/local.tokens"
python3 - "$tokenfs_mount/gpu0/nvmeof-demo/remote-spill.tokens" <<'PY'
import sys
from pathlib import Path

data = Path(sys.argv[1]).read_bytes()[:128]
if b"tokenfs-nvmeof-sequential-shard" not in data:
    raise SystemExit("remote spill content check failed")
PY

sqlite3 -header -csv "$metadata_db" \
  "select logical_path,gpu_id,tier,physical_path,size_bytes,checksum,state from files order by logical_path;" \
  > "$result_root/files.csv"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" status > "$result_root/status.txt"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" metrics > "$result_root/metrics.txt"

cat > "$result_root/report.md" <<EOF
# TokenFS NVMe-oF Two-VM Test Report

This test uses a real Linux NVMe/TCP Host/Target path between two Ubuntu VMs.

- Target IP: \`$target_ip\`
- Target port: \`$target_port\`
- Subsystem NQN: \`$subnqn\`
- Mounted backend: \`$mount_point\`
- TokenFS mount: \`$tokenfs_mount\`

## Expected Result

- \`local.tokens\` should stay in the local tier.
- \`remote-spill.tokens\` should exceed the GPU local quota and spill to the NVMe-oF mounted backend.

## Artifacts

- \`files.csv\`: logical path, tier, physical path, size, checksum, state.
- \`status.txt\`: TokenFS mount and quota status.
- \`metrics.txt\`: read/write/spill/fallocate counters and latency totals.
EOF

echo "TokenFS NVMe-oF two-VM test passed."
echo "Report:"
echo "  $result_root/report.md"
echo "  $result_root/files.csv"
echo "  $result_root/status.txt"
echo "  $result_root/metrics.txt"
