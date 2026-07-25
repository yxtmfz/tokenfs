#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mount_point="${TOKENFS_MOUNT:-/mnt/tokenfs}"
metadata_db="${TOKENFS_DB:-/var/lib/tokenfs/metadata/tokenfs.db}"
temp_config="$(mktemp /tmp/tokenfs-advanced.XXXXXX.yaml)"

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
text = text.replace("adaptive_migration: false", "adaptive_migration: true")
text = text.replace("adaptive_remote_promote_us: 10000", "adaptive_remote_promote_us: 0")
text = text.replace("value_promote_threshold: 100", "value_promote_threshold: 999999")
text = text.replace("qos_read_iops_per_gpu: 0", "qos_read_iops_per_gpu: 2")
dst.write_text(text, encoding="utf-8")
PY

"$project_root/scripts/reset_dev_state.sh" "$mount_point" >/dev/null
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$temp_config" "$mount_point" >/dev/null

echo "advanced: physical dedup uses one inode for duplicate content"
mkdir -p "$mount_point/gpu0/dedup" "$mount_point/gpu1/dedup"
printf "shared prompt prefix kv cache\n" >"$mount_point/gpu0/dedup/prefix.tokens"
printf "shared prompt prefix kv cache\n" >"$mount_point/gpu1/dedup/prefix-copy.tokens"
sync

inode_a=""
inode_b=""
for _ in {1..20}; do
  inode_a="$(stat -c '%i' /var/lib/tokenfs/local/gpu0/dedup/prefix.tokens)"
  inode_b="$(stat -c '%i' /var/lib/tokenfs/local/gpu1/dedup/prefix-copy.tokens)"
  [[ "$inode_a" == "$inode_b" ]] && break
  sleep 0.1
done
if [[ "$inode_a" != "$inode_b" ]]; then
  echo "expected duplicate files to share one inode"
  echo "gpu0 inode: $inode_a"
  echo "gpu1 inode: $inode_b"
  exit 1
fi

refs="$(sqlite3 "$metadata_db" "select max(ref_count) from content_refs;")"
if [[ "$refs" != "2" ]]; then
  echo "expected content ref_count=2"
  echo "actual: $refs"
  exit 1
fi

echo "advanced: slow remote read triggers adaptive promotion"
mkdir -p /var/lib/tokenfs/remote-sim/gpu0/adaptive
python3 - /var/lib/tokenfs/remote-sim/gpu0/adaptive/slow.tokens <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open("wb") as f:
    f.write((b"adaptive-remote-token-shard\n" * 4096) * 16)
PY

cat "$mount_point/gpu0/adaptive/slow.tokens" >/dev/null
test -f /var/lib/tokenfs/local/gpu0/adaptive/slow.tokens
sqlite3 "$metadata_db" \
  "select tier,state from files where logical_path='/gpu0/adaptive/slow.tokens';" \
  | grep -q '^local|COMMITTED$'

adaptive_count="$(sqlite3 "$metadata_db" \
  "select coalesce((select value from metrics where name='adaptive_promote_trigger_count'),0);")"
if [[ "$adaptive_count" -lt 1 ]]; then
  echo "expected adaptive_promote_trigger_count"
  exit 1
fi

echo "advanced: QoS limiter records per-GPU delay"
cat "$mount_point/gpu0/dedup/prefix.tokens" >/dev/null
cat "$mount_point/gpu0/dedup/prefix.tokens" >/dev/null
qos_delay_ops="$(sqlite3 "$metadata_db" \
  "select coalesce((select value from metrics where name='qos_delay_ops'),0);")"
if [[ "$qos_delay_ops" -lt 1 ]]; then
  echo "expected qos_delay_ops"
  exit 1
fi

"$project_root/scripts/tokenfsctl.py" --config "$temp_config" metrics | grep -q "物理去重次数"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" dedup | grep -q "refs=2"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" check

echo "TokenFS advanced policy test passed."
