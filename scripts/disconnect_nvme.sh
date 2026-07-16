#!/usr/bin/env bash
set -euo pipefail

subnqn="${TOKENFS_NVME_SUBNQN:-}"
mount_point="${TOKENFS_NVME_MOUNT:-/srv/tokenfs/remote0}"

if findmnt -rn "$mount_point" >/dev/null; then
  echo "Unmounting $mount_point"
  sudo umount "$mount_point"
fi

if [[ -n "$subnqn" ]]; then
  echo "Disconnecting subsystem $subnqn"
  sudo nvme disconnect -n "$subnqn" || true
else
  echo "TOKENFS_NVME_SUBNQN is not set; skipping nvme disconnect."
fi
