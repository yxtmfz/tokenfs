#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mount_point="${1:-/mnt/tokenfs}"
metadata_db="${TOKENFS_DB:-/var/lib/tokenfs/metadata/tokenfs.db}"
temp_config="$(mktemp /tmp/tokenfs-prefetch.XXXXXX.yaml)"

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
text = text.replace("promote_on_read: false", "promote_on_read: false")
text = text.replace("prefetch_on_read: false", "prefetch_on_read: true")
dst.write_text(text, encoding="utf-8")
PY

"$project_root/scripts/reset_dev_state.sh" "$mount_point" >/dev/null
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$temp_config" "$mount_point" >/dev/null

echo "test: seed two remote sequential token shards"
mkdir -p /var/lib/tokenfs/remote-sim/gpu0/prefetch
python3 - /var/lib/tokenfs/remote-sim/gpu0/prefetch <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
for index in (1, 2):
    path = root / f"shard-{index:06d}.tokens"
    block = (f"prefetch-shard-{index}-".encode() * 4096)
    with path.open("wb") as f:
        for _ in range(64):
            f.write(block)
PY

sha256sum /var/lib/tokenfs/remote-sim/gpu0/prefetch/shard-000001.tokens \
  | awk '{print $1}' >/tmp/tokenfs-prefetch-shard1.sha256
sha256sum /var/lib/tokenfs/remote-sim/gpu0/prefetch/shard-000002.tokens \
  | awk '{print $1}' >/tmp/tokenfs-prefetch-shard2-before.sha256

echo "test: reading shard-000001 triggers prefetch of shard-000002"
sha256sum "$mount_point/gpu0/prefetch/shard-000001.tokens" \
  | awk '{print $1}' >/tmp/tokenfs-prefetch-shard1-read.sha256
cmp -s /tmp/tokenfs-prefetch-shard1.sha256 /tmp/tokenfs-prefetch-shard1-read.sha256

for _ in {1..50}; do
  if [[ -f /var/lib/tokenfs/local/gpu0/prefetch/shard-000002.tokens ]]; then
    break
  fi
  sleep 0.1
done

test -f /var/lib/tokenfs/local/gpu0/prefetch/shard-000002.tokens
test -f /var/lib/tokenfs/remote-sim/gpu0/prefetch/shard-000002.tokens

prefetched_row="$(sqlite3 "$metadata_db" \
  "select tier,backend_id,read_count,state,primary_tier,has_remote_copy,local_cache_owner_gpu,replica_state from files where logical_path='/gpu0/prefetch/shard-000002.tokens';")"
if [[ "$prefetched_row" != "local|local|0|COMMITTED|remote|1|0|REMOTE_WITH_LOCAL_CACHE" ]]; then
  echo "expected shard-000002 to be prefetched as local cache with remote primary"
  echo "actual: $prefetched_row"
  exit 1
fi

echo "test: prefetched shard reads through the local tier"
sha256sum "$mount_point/gpu0/prefetch/shard-000002.tokens" \
  | awk '{print $1}' >/tmp/tokenfs-prefetch-shard2-read.sha256
cmp -s /tmp/tokenfs-prefetch-shard2-before.sha256 /tmp/tokenfs-prefetch-shard2-read.sha256

prefetch_count="$(sqlite3 "$metadata_db" \
  "select coalesce((select value from metrics where name='prefetch_count'),0);")"
if [[ "$prefetch_count" != "1" ]]; then
  echo "expected one successful prefetch"
  echo "actual: $prefetch_count"
  exit 1
fi

"$project_root/scripts/tokenfsctl.py" --config "$temp_config" metrics | grep -q "预取成功次数"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" files | grep -q "/gpu0/prefetch/shard-000002.tokens"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" replicas | grep -q "REMOTE_WITH_LOCAL_CACHE"

echo "TokenFS prefetch test passed."
