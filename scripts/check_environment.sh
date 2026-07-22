#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="${1:-$project_root/config/tokenfs.dev.yaml}"

ok=0
warn=0
fail=0

pass() {
  echo "[OK]   $1"
  ok=$((ok + 1))
}

note() {
  echo "[WARN] $1"
  warn=$((warn + 1))
}

bad() {
  echo "[FAIL] $1"
  fail=$((fail + 1))
}

need_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "command '$cmd' found"
  else
    bad "command '$cmd' not found"
  fi
}

read_config_value() {
  local section="$1"
  local key="$2"
  python3 - "$config" "$section" "$key" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
want_section = sys.argv[2]
want_key = sys.argv[3]
section = ""

if not path.exists():
    print("")
    raise SystemExit(0)

for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].rstrip()
    if not line.strip():
        continue
    if not line.startswith(" ") and line.endswith(":"):
        section = line[:-1]
        continue
    stripped = line.strip()
    if section == want_section and ":" in stripped and not stripped.startswith("- "):
        key, value = stripped.split(":", 1)
        if key.strip() == want_key:
            print(value.strip().strip('"').strip("'"))
            break
PY
}

read_backend_value() {
  local backend_id="$1"
  local key="$2"
  python3 - "$config" "$backend_id" "$key" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
backend_id = sys.argv[2]
want_key = sys.argv[3]
section = ""
current = None
found = {}

def clean(value):
    return value.strip().strip('"').strip("'")

if not path.exists():
    print("")
    raise SystemExit(0)

for raw in path.read_text(encoding="utf-8").splitlines():
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
    key, value = stripped.split(":", 1)
    current[key.strip()] = clean(value)

if found.get("id") != backend_id:
    found = {}
print(found.get(want_key, ""))
PY
}

echo "TokenFS environment check"
echo "config: $config"
echo

if [[ -f "$config" ]]; then
  pass "config file exists"
else
  bad "config file does not exist: $config"
fi

need_cmd bash
need_cmd python3
need_cmd cmake
need_cmd ninja
need_cmd g++
need_cmd pkg-config
need_cmd fusermount3
need_cmd sqlite3
need_cmd fio
need_cmd nvme

if [[ -e /dev/fuse ]]; then
  pass "/dev/fuse exists"
else
  bad "/dev/fuse does not exist; FUSE cannot mount"
fi

if pkg-config --exists fuse3 2>/dev/null; then
  pass "fuse3 development package found"
else
  bad "fuse3 development package not found"
fi

mount_point="$(read_config_value filesystem mount_point)"
metadata_db="$(read_config_value filesystem metadata_db)"
mount_point="${mount_point:-/mnt/tokenfs}"
metadata_db="${metadata_db:-/var/lib/tokenfs/metadata/tokenfs.db}"

if [[ -d "$mount_point" ]]; then
  pass "mount point exists: $mount_point"
else
  note "mount point does not exist yet: $mount_point"
fi

if [[ -w "$(dirname "$metadata_db")" ]] 2>/dev/null; then
  pass "metadata directory is writable: $(dirname "$metadata_db")"
else
  note "metadata directory may need creation or permission fix: $(dirname "$metadata_db")"
fi

backend_root="$(read_backend_value remote0 root)"
backend_type="$(read_backend_value remote0 type)"
backend_target="$(read_backend_value remote0 nvme_target_ip)"
backend_nqn="$(read_backend_value remote0 nvme_subnqn)"

if [[ -n "$backend_root" && -d "$backend_root" ]]; then
  pass "remote backend root exists: $backend_root"
elif [[ -n "$backend_root" ]]; then
  note "remote backend root does not exist yet: $backend_root"
else
  bad "remote0 backend root is missing"
fi

if [[ "$backend_type" == "nvmeof" ]]; then
  [[ -n "$backend_target" && "$backend_target" != __*__ ]] && pass "NVMe-oF target IP configured" || bad "NVMe-oF target IP is missing"
  [[ -n "$backend_nqn" && "$backend_nqn" != __*__ ]] && pass "NVMe-oF subnqn configured" || bad "NVMe-oF subnqn is missing"
else
  note "remote0 backend type is '$backend_type'; using directory simulation until real NVMe-oF details arrive"
fi

echo
"$project_root/scripts/connect_nvme.sh" --config "$config" --backend remote0 --dry-run >/tmp/tokenfs-nvme-dry-run.log || true
if grep -q "dry-run" /tmp/tokenfs-nvme-dry-run.log; then
  pass "NVMe-oF dry-run path is available"
else
  note "NVMe-oF dry-run produced no command output"
fi

echo
echo "Summary: ok=$ok warn=$warn fail=$fail"
if [[ "$fail" -gt 0 ]]; then
  exit 1
fi
