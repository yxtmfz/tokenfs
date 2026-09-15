#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="$project_root/config/tokenfs.nvmeof.example.yaml"
backend_id="${TOKENFS_BACKEND_ID:-remote0}"
target_override="${TOKENFS_NVME_TARGET_IP:-}"
port_override="${TOKENFS_NVME_TARGET_PORT:-}"

usage() {
  cat <<EOF
Usage: $0 [--config path] [--backend id] [--target-ip ip] [--port port]

This probe is read-only. It does not connect, mount, format, or write data.

Examples:
  $0 --config config/tokenfs.nvmeof.yaml
  $0 --target-ip 28.10.10.13 --port 4420
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
    --target-ip)
      target_override="$2"
      shift 2
      ;;
    --port)
      port_override="$2"
      shift 2
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

def clean(value: str) -> str:
    return value.strip().strip('"').strip("'")

if not config.exists():
    print("")
    raise SystemExit(0)

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

target_ip="${target_override:-$(read_backend_value nvme_target_ip)}"
target_port="${port_override:-$(read_backend_value nvme_port)}"
subnqn="$(read_backend_value nvme_subnqn)"
mount_point="$(read_backend_value nvme_mount)"
root="$(read_backend_value root)"
backend_type="$(read_backend_value type)"

target_port="${target_port:-4420}"
mount_point="${mount_point:-${root:-/srv/tokenfs/remote0}}"

ok=0
warn=0
fail=0

pass() { echo "[OK]   $1"; ok=$((ok + 1)); }
note() { echo "[WARN] $1"; warn=$((warn + 1)); }
bad() { echo "[FAIL] $1"; fail=$((fail + 1)); }

echo "AURA-KV lab network probe"
echo "config: $config"
echo "backend: $backend_id"
echo "target: ${target_ip:-<missing>}:$target_port"
echo "mount:  $mount_point"
echo

if [[ -f "$config" ]]; then
  pass "config file exists"
else
  note "config file does not exist; probing only explicit target values"
fi

if [[ "$backend_type" == "nvmeof" ]]; then
  pass "backend type is nvmeof"
elif [[ -n "$backend_type" ]]; then
  note "backend type is '$backend_type'; real paper runs should use nvmeof"
fi

if [[ -z "$target_ip" || "$target_ip" == __*__ ]]; then
  bad "target IP is missing or still a placeholder"
else
  pass "target IP is configured"
fi

if [[ -n "$subnqn" && "$subnqn" != __*__ ]]; then
  pass "subsystem NQN is configured"
else
  note "subsystem NQN is missing; port probing can still run"
fi

if command -v ip >/dev/null 2>&1 && [[ -n "$target_ip" && "$target_ip" != __*__ ]]; then
  echo
  echo "[route]"
  ip route get "$target_ip" || true
elif command -v route >/dev/null 2>&1; then
  echo
  echo "[route]"
  route -n get "$target_ip" 2>/dev/null || true
else
  note "no ip/route command found"
fi

if [[ -n "$target_ip" && "$target_ip" != __*__ ]]; then
  echo
  echo "[tcp]"
  if python3 - "$target_ip" "$target_port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
try:
    with socket.create_connection((host, port), timeout=5):
        pass
except OSError as exc:
    print(exc)
    raise SystemExit(1)
PY
  then
    pass "TCP $target_ip:$target_port is reachable from this client"
  else
    bad "TCP $target_ip:$target_port is not reachable from this client"
  fi
fi

echo
echo "[local mount]"
if command -v findmnt >/dev/null 2>&1 && findmnt -rn --target "$mount_point" >/dev/null 2>&1; then
  findmnt --target "$mount_point" || true
  source_dev="$(findmnt -rn --target "$mount_point" -o SOURCE 2>/dev/null || true)"
  if [[ "$source_dev" == /dev/nvme* ]]; then
    pass "$mount_point is backed by an NVMe namespace"
  else
    note "$mount_point is mounted, but source is '$source_dev' instead of /dev/nvme*"
  fi
else
  note "$mount_point is not mounted yet"
fi

echo
echo "[tools]"
if command -v nvme >/dev/null 2>&1; then
  pass "nvme-cli is installed"
  nvme list 2>/dev/null || true
  if [[ -n "$target_ip" && "$target_ip" != __*__ && -n "$subnqn" && "$subnqn" != __*__ ]]; then
    echo
    echo "[discover dry check]"
    sudo nvme discover -t tcp -a "$target_ip" -s "$target_port" 2>&1 | sed -n '1,120p' || note "nvme discover failed; check target, ACL, firewall, and Host NQN"
  fi
else
  note "nvme-cli is not installed"
fi

if command -v fusermount3 >/dev/null 2>&1; then
  pass "fuse3 userspace tool is installed"
else
  note "fusermount3 is not installed"
fi

echo
echo "Summary: ok=$ok warn=$warn fail=$fail"
if [[ "$fail" -gt 0 ]]; then
  exit 1
fi
