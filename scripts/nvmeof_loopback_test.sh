#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
subnqn="${TOKENFS_TARGET_SUBNQN:-nqn.2026-07.local.tokenfs:remote0}"
target_ip="${TOKENFS_TARGET_IP:-127.0.0.1}"
target_port="${TOKENFS_TARGET_PORT:-4420}"
mount_point="${TOKENFS_NVME_MOUNT:-/srv/tokenfs/remote0}"
image="${TOKENFS_TARGET_IMAGE:-/var/lib/tokenfs/nvmeof-target/remote0.img}"

cleanup() {
  sudo umount "$mount_point" >/dev/null 2>&1 || true
  sudo nvme disconnect -n "$subnqn" >/dev/null 2>&1 || true
  "$project_root/scripts/cleanup_nvme_target.sh" --subnqn "$subnqn" --image "$image" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup

TOKENFS_TARGET_IP="$target_ip" \
TOKENFS_TARGET_PORT="$target_port" \
TOKENFS_TARGET_SUBNQN="$subnqn" \
TOKENFS_TARGET_IMAGE="$image" \
  "$project_root/scripts/setup_nvme_target.sh"

sudo modprobe nvme-tcp
sudo nvme discover -t tcp -a "$target_ip" -s "$target_port"
sudo nvme connect -t tcp -a "$target_ip" -s "$target_port" -n "$subnqn"

echo "Waiting for connected NVMe namespace..."
device=""
for _ in $(seq 1 20); do
  device="$(nvme list -o json 2>/dev/null | python3 - "$subnqn" <<'PY' || true
import json
import sys

subnqn = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit

for dev in data.get("Devices", []):
    if dev.get("SubsystemNQN") == subnqn:
        print(dev.get("DevicePath", ""))
        break
PY
)"
  if [[ -n "$device" && -b "$device" ]]; then
    break
  fi
  sleep 0.5
done

if [[ -z "$device" || ! -b "$device" ]]; then
  echo "Could not find connected NVMe namespace for $subnqn" >&2
  nvme list || true
  exit 1
fi

echo "Connected namespace: $device"
sudo mkdir -p "$mount_point"

if ! sudo blkid "$device" >/dev/null 2>&1; then
  echo "Formatting loopback NVMe namespace as ext4: $device"
  sudo mkfs.ext4 -F "$device" >/dev/null
fi

sudo mount "$device" "$mount_point"
sudo mkdir -p "$mount_point/gpu0" "$mount_point/gpu1"
sudo chown -R "$(id -u):$(id -g)" "$mount_point"

echo "hello nvmeof tokenfs" > "$mount_point/gpu0/protocol-check.txt"
grep -q "hello nvmeof tokenfs" "$mount_point/gpu0/protocol-check.txt"
sync

echo "NVMe-oF loopback test passed."
echo "target=$target_ip:$target_port"
echo "subnqn=$subnqn"
echo "device=$device"
echo "mount=$mount_point"
