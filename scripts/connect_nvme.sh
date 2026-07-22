#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="$project_root/config/tokenfs.dev.yaml"
backend_id="${TOKENFS_BACKEND_ID:-remote0}"
dry_run=0

usage() {
  cat <<EOF
Usage: $0 [--config path] [--backend id] [--dry-run]

Environment variables still work and override config values:
  TOKENFS_NVME_TRANSPORT
  TOKENFS_NVME_TARGET_IP
  TOKENFS_NVME_TARGET_PORT
  TOKENFS_NVME_SUBNQN
  TOKENFS_NVME_DEVICE
  TOKENFS_NVME_MOUNT
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      config="$2"
      shift 2
      ;;
    --backend)
      backend_id="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

read_backend_value() {
  local key="$1"
  python3 - "$config" "$backend_id" "$key" <<'PY'
import sys
from pathlib import Path

config = Path(sys.argv[1])
backend_id = sys.argv[2]
key = sys.argv[3]
section = ""
current = None
found = {}

def clean(value):
    return value.strip().strip('"').strip("'")

for raw in config.read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].rstrip()
    if not line.strip():
        continue
    if not line.startswith(" ") and line.endswith(":"):
        section = line[:-1]
        current = None
        continue
    stripped = line.strip()
    if section == "backends" and stripped.startswith("- "):
        if found.get("id") == backend_id:
            break
        current = {}
        found = current
        stripped = stripped[2:].strip()
    if current is None or ":" not in stripped:
        continue
    k, v = stripped.split(":", 1)
    current[k.strip()] = clean(v)

if found.get("id") != backend_id:
    found = {}
print(found.get(key, ""))
PY
}

transport="${TOKENFS_NVME_TRANSPORT:-$(read_backend_value nvme_transport)}"
target_ip="${TOKENFS_NVME_TARGET_IP:-$(read_backend_value nvme_target_ip)}"
target_port="${TOKENFS_NVME_TARGET_PORT:-$(read_backend_value nvme_port)}"
subnqn="${TOKENFS_NVME_SUBNQN:-$(read_backend_value nvme_subnqn)}"
device="${TOKENFS_NVME_DEVICE:-$(read_backend_value nvme_device)}"
mount_point="${TOKENFS_NVME_MOUNT:-$(read_backend_value nvme_mount)}"
root="$(read_backend_value root)"

transport="${transport:-tcp}"
target_port="${target_port:-4420}"
mount_point="${mount_point:-${root:-/srv/tokenfs/remote0}}"

placeholder_re='^(__.*__|/dev/nvmeXnY)$'
if [[ -z "$target_ip" || -z "$subnqn" || "$target_ip" =~ $placeholder_re || "$subnqn" =~ $placeholder_re ]]; then
  cat >&2 <<'EOF'
Missing NVMe-oF settings.

Set real values in config/tokenfs.dev.yaml or environment variables:
  nvme_target_ip / TOKENFS_NVME_TARGET_IP
  nvme_subnqn    / TOKENFS_NVME_SUBNQN

Optional:
  nvme_transport / TOKENFS_NVME_TRANSPORT
  nvme_port      / TOKENFS_NVME_TARGET_PORT
  nvme_device    / TOKENFS_NVME_DEVICE
  nvme_mount     / TOKENFS_NVME_MOUNT

This script never formats devices. Create the filesystem explicitly before use.
EOF
  if [[ "$dry_run" -eq 1 ]]; then
    echo "dry-run: missing values are expected before the lab provides NVMe-oF details."
    exit 0
  fi
  exit 2
fi

run() {
  if [[ "$dry_run" -eq 1 ]]; then
    printf 'dry-run:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

if [[ "$transport" != "tcp" ]]; then
  echo "Only tcp is automated for now. transport=$transport" >&2
  exit 2
fi

run sudo modprobe nvme-tcp
run sudo mkdir -p "$mount_point"

echo "Discovering NVMe-oF target $target_ip:$target_port"
run sudo nvme discover -t "$transport" -a "$target_ip" -s "$target_port"

echo "Connecting subsystem $subnqn"
run sudo nvme connect -t "$transport" -a "$target_ip" -s "$target_port" -n "$subnqn"

if [[ -z "$device" || "$device" =~ $placeholder_re ]]; then
  echo "Set TOKENFS_NVME_DEVICE to the connected namespace, for example /dev/nvme1n1."
  echo "Current NVMe devices:"
  if [[ "$dry_run" -eq 1 ]]; then
    echo "dry-run: nvme list"
  else
    nvme list || true
  fi
  exit 0
fi

if [[ "$dry_run" -eq 0 ]] && findmnt -rn "$mount_point" >/dev/null; then
  echo "$mount_point is already mounted."
  exit 0
fi

echo "Mounting $device at $mount_point"
run sudo mount "$device" "$mount_point"
echo "NVMe-oF backend mounted at $mount_point"
