#!/usr/bin/env bash
set -euo pipefail

mount_point="${1:-/mnt/tokenfs}"
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null 2>&1 || true

rm -rf \
  /var/lib/tokenfs/local \
  /var/lib/tokenfs/direct-local \
  /var/lib/tokenfs/remote-sim \
  /var/lib/tokenfs/metadata

mkdir -p \
  /var/lib/tokenfs/local/gpu0 \
  /var/lib/tokenfs/local/gpu1 \
  /var/lib/tokenfs/direct-local \
  /var/lib/tokenfs/remote-sim/gpu0 \
  /var/lib/tokenfs/remote-sim/gpu1 \
  /var/lib/tokenfs/metadata \
  "$mount_point"

echo "TokenFS development state reset."
