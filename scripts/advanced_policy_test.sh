#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mount_point="${TOKENFS_MOUNT:-/mnt/tokenfs}"
metadata_db="${TOKENFS_DB:-/var/lib/tokenfs/metadata/tokenfs.db}"
temp_config="$(mktemp /tmp/tokenfs-advanced.XXXXXX.yaml)"
qos_config="$(mktemp /tmp/tokenfs-qos.XXXXXX.yaml)"

cleanup() {
  "$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null 2>&1 || true
  rm -f "$temp_config" "$qos_config"
}
trap cleanup EXIT

python3 - "$project_root/config/tokenfs.dev.yaml" "$temp_config" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
text = src.read_text(encoding="utf-8")
text = text.replace("local_quota_mib: 64", "local_quota_mib: 96", 1)
dst.write_text(text, encoding="utf-8")
PY

"$project_root/scripts/reset_dev_state.sh" "$mount_point" >/dev/null
cmake -S "$project_root" -B "$project_root/build" -G Ninja >/dev/null
cmake --build "$project_root/build" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$temp_config" "$mount_point" >/dev/null

echo "advanced: AI value-aware eviction protects hot high-value files"
mkdir -p "$mount_point/gpu0/value"

python3 - "$mount_point/gpu0/value/hot.tokens" <<'PY'
import sys
from pathlib import Path

Path(sys.argv[1]).write_bytes(b"H" * 24 * 1024 * 1024)
PY

for _ in {1..6}; do
  cat "$mount_point/gpu0/value/hot.tokens" >/dev/null
done

python3 - "$mount_point/gpu0/value/cold.tokens" <<'PY'
import sys
from pathlib import Path

Path(sys.argv[1]).write_bytes(b"C" * 40 * 1024 * 1024)
PY

python3 - "$mount_point/gpu0/value/new.tokens" <<'PY'
import sys
from pathlib import Path

Path(sys.argv[1]).write_bytes(b"N" * 40 * 1024 * 1024)
PY

hot_tier="$(sqlite3 "$metadata_db" \
  "select tier from files where logical_path='/gpu0/value/hot.tokens';")"
if [[ "$hot_tier" != "local" ]]; then
  echo "expected hot high-value file to remain local"
  exit 1
fi

evict_count="$(sqlite3 "$metadata_db" \
  "select coalesce((select value from metrics where name='evict_count'),0);")"
if [[ "$evict_count" -lt 1 ]]; then
  echo "expected value-aware local eviction"
  exit 1
fi

echo "advanced: GPU affinity stats identify the dominant GPU"
cat "$mount_point/gpu0/value/hot.tokens" >/dev/null
cat "$mount_point/gpu0/value/hot.tokens" >/dev/null
gpu0_reads="$(sqlite3 "$metadata_db" \
  "select coalesce((select read_count from gpu_access where logical_path='/gpu0/value/hot.tokens' and gpu_id=0),0);")"
if [[ "$gpu0_reads" -lt 2 ]]; then
  echo "expected gpu0 affinity reads to be recorded"
  exit 1
fi

"$project_root/scripts/tokenfsctl.py" --config "$temp_config" metrics | grep -q "本地淘汰次数"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" affinity | grep -q "GPU 0"
"$project_root/scripts/tokenfsctl.py" --config "$temp_config" check
"$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null

python3 - "$project_root/config/tokenfs.dev.yaml" "$qos_config" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
text = src.read_text(encoding="utf-8")
text = text.replace("qos_read_iops_per_gpu: 0", "qos_read_iops_per_gpu: 2")
dst.write_text(text, encoding="utf-8")
PY

"$project_root/scripts/reset_dev_state.sh" "$mount_point" >/dev/null
"$project_root/scripts/start_tokenfs.sh" "$qos_config" "$mount_point" >/dev/null

echo "advanced: QoS limiter records per-GPU delay"
mkdir -p "$mount_point/gpu0/qos"
printf "qos\n" >"$mount_point/gpu0/qos/tiny.tokens"
cat "$mount_point/gpu0/qos/tiny.tokens" >/dev/null
cat "$mount_point/gpu0/qos/tiny.tokens" >/dev/null
qos_delay_ops="$(sqlite3 "$metadata_db" \
  "select coalesce((select value from metrics where name='qos_delay_ops'),0);")"
if [[ "$qos_delay_ops" -lt 1 ]]; then
  echo "expected qos_delay_ops"
  exit 1
fi

"$project_root/scripts/tokenfsctl.py" --config "$qos_config" metrics | grep -q "QoS 延迟次数"
"$project_root/scripts/tokenfsctl.py" --config "$qos_config" check

echo "TokenFS advanced policy test passed."
