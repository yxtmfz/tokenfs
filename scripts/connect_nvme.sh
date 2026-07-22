#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="$project_root/config/tokenfs.dev.yaml"
backend_id="${TOKENFS_BACKEND_ID:-remote0}"
dry_run=0
allow_format=0
chown_current=0

usage() {
  cat <<EOF
Usage: $0 [--config path] [--backend id] [--dry-run] [--allow-format] [--chown-current]

Environment variables still work and override config values:
  TOKENFS_NVME_TRANSPORT
  TOKENFS_NVME_TARGET_IP
  TOKENFS_NVME_TARGET_PORT
  TOKENFS_NVME_SUBNQN
  TOKENFS_NVME_DEVICE
  TOKENFS_NVME_MOUNT
  TOKENFS_NVME_SERIAL

Safety:
  --allow-format    format the connected namespace only when it has no filesystem
  --chown-current   chown the mounted backend to the current user after mount
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
    --allow-format)
      allow_format=1
      shift
      ;;
    --chown-current)
      chown_current=1
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
filesystem="${TOKENFS_NVME_FILESYSTEM:-$(read_backend_value nvme_filesystem)}"
serial="${TOKENFS_NVME_SERIAL:-$(read_backend_value nvme_serial)}"
root="$(read_backend_value root)"

transport="${transport:-tcp}"
target_port="${target_port:-4420}"
mount_point="${mount_point:-${root:-/srv/tokenfs/remote0}}"
filesystem="${filesystem:-ext4}"

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
  if [[ "$dry_run" -eq 1 ]]; then
    echo "dry-run: auto-detect connected namespace for subnqn=$subnqn"
  else
    echo "Detecting connected namespace for $subnqn"
    for _ in $(seq 1 30); do
      device="$(nvme list -o json 2>/dev/null | python3 -c '
import json
import sys

subnqn = sys.argv[1]
serial = sys.argv[2]
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit

devices = data.get("Devices", [])
for dev in data.get("Devices", []):
    if dev.get("SubsystemNQN") == subnqn:
        print(dev.get("DevicePath", ""))
        raise SystemExit

if serial:
    for dev in devices:
        if dev.get("SerialNumber") == serial:
            print(dev.get("DevicePath", ""))
            raise SystemExit

if len(devices) == 1:
    print(devices[0].get("DevicePath", ""))
' "$subnqn" "$serial" || true)"
      if [[ -n "$device" && -b "$device" ]]; then
        break
      fi
      sleep 0.5
    done
  fi
fi

if [[ "$dry_run" -eq 0 && ( -z "$device" || ! -b "$device" ) ]]; then
  echo "Could not find connected namespace for $subnqn." >&2
  echo "Set TOKENFS_NVME_DEVICE manually, for example /dev/nvme1n1." >&2
  nvme list || true
  exit 1
fi

if [[ "$dry_run" -eq 0 ]] && findmnt -rn "$mount_point" >/dev/null; then
  echo "$mount_point is already mounted."
  exit 0
fi

if [[ "$allow_format" -eq 1 ]]; then
  echo "Formatting is explicitly allowed for empty namespaces."
  if [[ "$dry_run" -eq 1 ]]; then
    echo "dry-run: blkid $device || mkfs.$filesystem -F $device"
  elif ! sudo blkid "$device" >/dev/null 2>&1; then
    echo "No filesystem found on $device; creating $filesystem"
    run sudo "mkfs.$filesystem" -F "$device"
  fi
else
  echo "Formatting is disabled. Use --allow-format only for fresh simulated namespaces."
fi

echo "Mounting $device at $mount_point"
run sudo mount "$device" "$mount_point"
if [[ "$chown_current" -eq 1 ]]; then
  run sudo chown -R "$(id -u):$(id -g)" "$mount_point"
fi
echo "NVMe-oF backend mounted at $mount_point"
