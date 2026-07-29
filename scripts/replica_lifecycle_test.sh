#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mount_point="${TOKENFS_MOUNT:-/mnt/tokenfs}"
metadata_db="${TOKENFS_DB:-/var/lib/tokenfs/metadata/tokenfs.db}"
temp_config="$(mktemp /tmp/tokenfs-replica.XXXXXX.yaml)"

cleanup() {
  "$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null 2>&1 || true
  rm -f "$temp_config"
}
trap cleanup EXIT

python3 - "$project_root/config/tokenfs.dev.yaml" "$temp_config" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
text = src.read_text(encoding="utf-8")
text = text.replace("promote_on_read: false", "promote_on_read: true")
text = text.replace("promote_read_threshold: 2", "promote_read_threshold: 2")
dst.write_text(text, encoding="utf-8")
PY

"$project_root/scripts/reset_dev_state.sh" "$mount_point" >/dev/null
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$temp_config" "$mount_point" >/dev/null

echo "replica: seed a remote-primary token cache"
mkdir -p /var/lib/tokenfs/remote-sim/gpu0/cache
python3 - /var/lib/tokenfs/remote-sim/gpu0/cache/hot.tokens <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = b"remote-primary-local-cache-" * 4096
with path.open("wb") as f:
    for _ in range(64):
        f.write(payload)
PY

sha256sum /var/lib/tokenfs/remote-sim/gpu0/cache/hot.tokens \
  | awk '{print $1}' >/tmp/tokenfs-replica-remote.sha256

echo "replica: two reads promote remote data into GPU0 local cache"
sha256sum "$mount_point/gpu0/cache/hot.tokens" >/dev/null
sha256sum "$mount_point/gpu0/cache/hot.tokens" \
  | awk '{print $1}' >/tmp/tokenfs-replica-read.sha256
cmp -s /tmp/tokenfs-replica-remote.sha256 /tmp/tokenfs-replica-read.sha256

test -f /var/lib/tokenfs/remote-sim/gpu0/cache/hot.tokens
test -f /var/lib/tokenfs/local/gpu0/cache/hot.tokens

promoted_row="$(sqlite3 "$metadata_db" \
  "select tier,backend_id,primary_tier,has_remote_copy,local_cache_owner_gpu,replica_state,state from files where logical_path='/gpu0/cache/hot.tokens';")"
if [[ "$promoted_row" != "local|local|remote|1|0|REMOTE_WITH_LOCAL_CACHE|COMMITTED" ]]; then
  echo "expected promoted file to keep remote primary and GPU0 local cache"
  echo "actual: $promoted_row"
  exit 1
fi

"$project_root/scripts/tokenfsctl.py" --config "$temp_config" replicas | grep -q "REMOTE_WITH_LOCAL_CACHE"

echo "replica: cache GC deletes only the local cache copy"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" cache-gc --max-cache-mib 0

test -f /var/lib/tokenfs/remote-sim/gpu0/cache/hot.tokens
test ! -e /var/lib/tokenfs/local/gpu0/cache/hot.tokens

gc_row="$(sqlite3 "$metadata_db" \
  "select tier,backend_id,primary_tier,has_remote_copy,local_cache_owner_gpu,replica_state,state from files where logical_path='/gpu0/cache/hot.tokens';")"
if [[ "$gc_row" != "remote|remote0|remote|1|-1|REMOTE_ONLY|COMMITTED" ]]; then
  echo "expected GC to keep a clean remote-only record"
  echo "actual: $gc_row"
  exit 1
fi

"$project_root/scripts/tokenfsctl.py" --config "$temp_config" check

echo "TokenFS replica lifecycle test passed."
