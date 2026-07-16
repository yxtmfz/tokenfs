#!/usr/bin/env bash
set -euo pipefail

target_ip="${TOKENFS_NVME_TARGET_IP:-}"
target_port="${TOKENFS_NVME_TARGET_PORT:-4420}"
subnqn="${TOKENFS_NVME_SUBNQN:-}"
device="${TOKENFS_NVME_DEVICE:-}"
mount_point="${TOKENFS_NVME_MOUNT:-/srv/tokenfs/remote0}"

if [[ -z "$target_ip" || -z "$subnqn" ]]; then
  cat >&2 <<'EOF'
Missing NVMe-oF settings.

Set at least:
  TOKENFS_NVME_TARGET_IP=<ssd target ip>
  TOKENFS_NVME_SUBNQN=<subsystem nqn>

Optional:
  TOKENFS_NVME_TARGET_PORT=4420
  TOKENFS_NVME_DEVICE=/dev/nvmeXnY
  TOKENFS_NVME_MOUNT=/srv/tokenfs/remote0

This script never formats devices. Create the filesystem explicitly before use.
EOF
  exit 2
fi

sudo modprobe nvme-tcp
sudo mkdir -p "$mount_point"

echo "Discovering NVMe-oF target $target_ip:$target_port"
sudo nvme discover -t tcp -a "$target_ip" -s "$target_port" || true

echo "Connecting subsystem $subnqn"
sudo nvme connect -t tcp -a "$target_ip" -s "$target_port" -n "$subnqn" || true

if [[ -z "$device" ]]; then
  echo "Set TOKENFS_NVME_DEVICE to the connected namespace, for example /dev/nvme1n1."
  echo "Current NVMe devices:"
  nvme list || true
  exit 0
fi

if findmnt -rn "$mount_point" >/dev/null; then
  echo "$mount_point is already mounted."
  exit 0
fi

echo "Mounting $device at $mount_point"
sudo mount "$device" "$mount_point"
echo "NVMe-oF backend mounted at $mount_point"
