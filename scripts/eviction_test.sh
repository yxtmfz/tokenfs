#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mount_point="${TOKENFS_MOUNT:-/mnt/tokenfs}"
metadata_db="${TOKENFS_DB:-/var/lib/tokenfs/metadata/tokenfs.db}"

cleanup() {
  "$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$project_root/scripts/reset_dev_state.sh" "$mount_point" >/dev/null
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$project_root/config/tokenfs.dev.yaml" "$mount_point" >/dev/null

echo "eviction: seed local files with different heat"
mkdir -p "$mount_point/gpu0/evict"
truncate -s 20M "$mount_point/gpu0/evict/hot.tokens"
truncate -s 30M "$mount_point/gpu0/evict/cold-big.tokens"
truncate -s 8M "$mount_point/gpu0/evict/warm.tokens"
sync

sqlite3 "$metadata_db" \
  "update files set read_count=10,last_access_at=9999999999 where logical_path='/gpu0/evict/hot.tokens';"
sqlite3 "$metadata_db" \
  "update files set read_count=1,last_access_at=9999999999 where logical_path='/gpu0/evict/warm.tokens';"
sqlite3 "$metadata_db" \
  "update files set read_count=0,last_access_at=1 where logical_path='/gpu0/evict/cold-big.tokens';"

echo "eviction: write another local file and force value-aware eviction"
truncate -s 32M "$mount_point/gpu0/evict/new.tokens"
sync

sqlite3 "$metadata_db" \
  "select tier from files where logical_path='/gpu0/evict/new.tokens';" | grep -q '^local$'
sqlite3 "$metadata_db" \
  "select tier from files where logical_path='/gpu0/evict/cold-big.tokens';" | grep -q '^remote$'
sqlite3 "$metadata_db" \
  "select primary_tier,has_remote_copy,local_cache_owner_gpu,replica_state from files where logical_path='/gpu0/evict/cold-big.tokens';" \
  | grep -q '^remote|1|-1|REMOTE_ONLY$'
sqlite3 "$metadata_db" \
  "select tier from files where logical_path='/gpu0/evict/hot.tokens';" | grep -q '^local$'
test -f /var/lib/tokenfs/remote-sim/gpu0/evict/cold-big.tokens
test ! -e /var/lib/tokenfs/local/gpu0/evict/cold-big.tokens

evict_count="$(sqlite3 "$metadata_db" "select coalesce((select value from metrics where name='evict_count'),0);")"
if [[ "$evict_count" -lt 1 ]]; then
  echo "expected evict_count metric"
  exit 1
fi
"$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" check

echo "TokenFS value-aware eviction test passed."
