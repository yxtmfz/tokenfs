#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mount_point="${1:-/mnt/tokenfs}"
metadata_db="${TOKENFS_DB:-/var/lib/tokenfs/metadata/tokenfs.db}"
temp_config="$(mktemp /tmp/tokenfs-promote.XXXXXX.yaml)"

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

echo "test: seed a remote-only hot token shard"
mkdir -p /var/lib/tokenfs/remote-sim/gpu0/hot
python3 - /var/lib/tokenfs/remote-sim/gpu0/hot/shard.tokens <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
block = (b"hot-token-shard-" * 4096)
with path.open("wb") as f:
    for _ in range(128):
        f.write(block)
PY

sha256sum /var/lib/tokenfs/remote-sim/gpu0/hot/shard.tokens \
  | awk '{print $1}' >/tmp/tokenfs-promote-before.sha256

echo "test: first read keeps file remote"
sha256sum "$mount_point/gpu0/hot/shard.tokens" \
  | awk '{print $1}' >/tmp/tokenfs-promote-read1.sha256
test -f /var/lib/tokenfs/remote-sim/gpu0/hot/shard.tokens
first_row="$(sqlite3 "$metadata_db" \
  "select tier,read_count from files where logical_path='/gpu0/hot/shard.tokens';")"
if [[ "$first_row" != "remote|1" ]]; then
  echo "expected first read to keep remote|1"
  echo "actual: $first_row"
  exit 1
fi

echo "test: second read promotes hot shard to local"
sha256sum "$mount_point/gpu0/hot/shard.tokens" \
  | awk '{print $1}' >/tmp/tokenfs-promote-read2.sha256
test -f /var/lib/tokenfs/local/gpu0/hot/shard.tokens
test -f /var/lib/tokenfs/remote-sim/gpu0/hot/shard.tokens

second_row="$(sqlite3 "$metadata_db" \
  "select tier,backend_id,read_count,state,primary_tier,has_remote_copy,local_cache_owner_gpu,replica_state from files where logical_path='/gpu0/hot/shard.tokens';")"
if [[ "$second_row" != "local|local|2|COMMITTED|remote|1|0|REMOTE_WITH_LOCAL_CACHE" ]]; then
  echo "expected second read to create a local cache while keeping the remote primary"
  echo "actual: $second_row"
  exit 1
fi

cmp -s /tmp/tokenfs-promote-before.sha256 /tmp/tokenfs-promote-read1.sha256
cmp -s /tmp/tokenfs-promote-before.sha256 /tmp/tokenfs-promote-read2.sha256

promote_count="$(sqlite3 "$metadata_db" \
  "select coalesce((select value from metrics where name='promote_count'),0);")"
if [[ "$promote_count" != "1" ]]; then
  echo "expected one promotion"
  echo "actual: $promote_count"
  exit 1
fi

"$project_root/scripts/tokenfsctl.py" --config "$temp_config" metrics | grep -q "热点提升次数"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" files | grep -q "reads=2"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" replicas | grep -q "REMOTE_WITH_LOCAL_CACHE"

echo "TokenFS promote-on-read test passed."
