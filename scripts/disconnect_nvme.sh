#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="$project_root/config/tokenfs.dev.yaml"
backend_id="${TOKENFS_BACKEND_ID:-remote0}"
dry_run=0

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
      echo "Usage: $0 [--config path] [--backend id] [--dry-run]"
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
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

subnqn="${TOKENFS_NVME_SUBNQN:-$(read_backend_value nvme_subnqn)}"
mount_point="${TOKENFS_NVME_MOUNT:-$(read_backend_value nvme_mount)}"
root="$(read_backend_value root)"
mount_point="${mount_point:-${root:-/srv/tokenfs/remote0}}"

run() {
  if [[ "$dry_run" -eq 1 ]]; then
    printf 'dry-run:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

if [[ "$dry_run" -eq 0 ]] && findmnt -rn "$mount_point" >/dev/null; then
  echo "Unmounting $mount_point"
  run sudo umount "$mount_point"
elif [[ "$dry_run" -eq 1 ]]; then
  echo "dry-run: findmnt -rn $mount_point && sudo umount $mount_point"
fi

if [[ -n "$subnqn" && "$subnqn" != __*__ ]]; then
  echo "Disconnecting subsystem $subnqn"
  run sudo nvme disconnect -n "$subnqn"
else
  echo "NVMe-oF subnqn is not set; skipping nvme disconnect."
fi
