#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mount_point="${1:-/mnt/tokenfs}"
metadata_db="${TOKENFS_DB:-/var/lib/tokenfs/metadata/tokenfs.db}"

require_row() {
  local sql="$1"
  local expected="$2"
  local actual
  actual="$(sqlite3 "$metadata_db" "$sql")"
  if [[ "$actual" != "$expected" ]]; then
    echo "expected: $expected"
    echo "actual:   $actual"
    exit 1
  fi
}

"$project_root/scripts/reset_dev_state.sh" "$mount_point"
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$project_root/config/tokenfs.dev.yaml" "$mount_point" >/dev/null

echo "test: local write"
mkdir -p "$mount_point/gpu0/demo"
printf "hello tokenfs\n" > "$mount_point/gpu0/demo/a.tokens"
grep -q "hello tokenfs" "$mount_point/gpu0/demo/a.tokens"
test -f /var/lib/tokenfs/local/gpu0/demo/a.tokens
require_row \
  "select tier,state from files where logical_path='/gpu0/demo/a.tokens';" \
  "local|COMMITTED"

echo "test: remote spill when local quota is exceeded"
truncate -s 80M "$mount_point/gpu0/big.tokens"
sync
test -f /var/lib/tokenfs/remote-sim/gpu0/big.tokens
require_row \
  "select tier,state,size_bytes from files where logical_path='/gpu0/big.tokens';" \
  "remote|COMMITTED|83886080"

echo "test: preallocated sequential shard"
python3 - "$mount_point/gpu0/demo/preallocated.tokens" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open("wb", buffering=0) as f:
    os.posix_fallocate(f.fileno(), 0, 4 * 1024 * 1024)
    f.write(b"tokenfs-preallocated-shard\n" * 1024)
    os.fsync(f.fileno())
PY
test -f /var/lib/tokenfs/local/gpu0/demo/preallocated.tokens

echo "test: gpu1 namespace"
mkdir -p "$mount_point/gpu1/demo"
printf "gpu1 token data\n" > "$mount_point/gpu1/demo/b.tokens"
grep -q "gpu1 token data" "$mount_point/gpu1/demo/b.tokens"
require_row \
  "select gpu_id,tier,state from files where logical_path='/gpu1/demo/b.tokens';" \
  "1|local|COMMITTED"

echo "test: checksum metadata"
checksum="$(sqlite3 "$metadata_db" "select checksum from files where logical_path='/gpu0/demo/a.tokens';")"
if [[ "$checksum" != fnv1a64:* ]]; then
  echo "checksum was not recorded: $checksum"
  exit 1
fi

echo "test: tokenfsctl status"
"$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" status | grep -q "TokenFS 状态"
"$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" files | grep -q "/gpu1/demo/b.tokens"
"$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" metrics | grep -q "溢写次数"
spill_count="$(sqlite3 "$metadata_db" "select value from metrics where name='spill_count';")"
if [[ "${spill_count:-0}" -lt 1 ]]; then
  echo "spill metric was not recorded"
  exit 1
fi

echo "test: delete removes file and metadata"
rm "$mount_point/gpu0/demo/a.tokens"
if sqlite3 "$metadata_db" "select count(*) from files where logical_path='/gpu0/demo/a.tokens';" | grep -vq '^0$'; then
  echo "metadata still contains deleted file"
  exit 1
fi
if [[ -e /var/lib/tokenfs/local/gpu0/demo/a.tokens ]]; then
  echo "physical file still exists after delete"
  exit 1
fi

"$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null

echo "test: startup recovery removes incomplete files"
mkdir -p /var/lib/tokenfs/local/gpu0/recovery
printf "partial" > /var/lib/tokenfs/local/gpu0/recovery/partial.tokens
sqlite3 "$metadata_db" \
  "insert into files(logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,checksum,state,created_at,updated_at,last_access_at) values('/gpu0/recovery/partial.tokens',0,'local','local','/var/lib/tokenfs/local/gpu0/recovery/partial.tokens',7,'','CREATING',0,0,0);"
"$project_root/scripts/start_tokenfs.sh" "$project_root/config/tokenfs.dev.yaml" "$mount_point" >/dev/null
if [[ -e /var/lib/tokenfs/local/gpu0/recovery/partial.tokens ]]; then
  echo "incomplete physical file was not cleaned"
  exit 1
fi
require_row \
  "select count(*) from files where logical_path='/gpu0/recovery/partial.tokens';" \
  "0"

"$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null
echo "TokenFS integration test passed."
