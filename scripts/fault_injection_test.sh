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

echo "fault: create a committed file"
mkdir -p "$mount_point/gpu0/fault"
printf "stable token data\n" > "$mount_point/gpu0/fault/stable.tokens"
sync
"$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" check >/tmp/tokenfs-fault-ok.log

echo "fault: detect physical file loss"
rm -f /var/lib/tokenfs/local/gpu0/fault/stable.tokens
if "$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" check >/tmp/tokenfs-fault-missing.log; then
  echo "expected missing physical file to fail consistency check"
  exit 1
fi
grep -q "物理文件不存在" /tmp/tokenfs-fault-missing.log

echo "fault: recover unfinished CREATING state on restart"
"$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null
mkdir -p /var/lib/tokenfs/remote-sim/gpu0/fault
printf "half-written remote shard\n" > /var/lib/tokenfs/remote-sim/gpu0/fault/partial.tokens
sqlite3 "$metadata_db" \
  "insert or replace into files(logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,checksum,state,created_at,updated_at,last_access_at,read_count) values('/gpu0/fault/partial.tokens',0,'remote','remote0','/var/lib/tokenfs/remote-sim/gpu0/fault/partial.tokens',26,'','CREATING',0,0,0,0);"
"$project_root/scripts/start_tokenfs.sh" "$project_root/config/tokenfs.dev.yaml" "$mount_point" >/dev/null
test ! -e /var/lib/tokenfs/remote-sim/gpu0/fault/partial.tokens
sqlite3 "$metadata_db" "select count(*) from files where logical_path='/gpu0/fault/partial.tokens';" | grep -q '^0$'

echo "fault: detect orphan remote file"
printf "orphan remote\n" > /var/lib/tokenfs/remote-sim/gpu0/fault/orphan.tokens
if "$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" check >/tmp/tokenfs-fault-orphan.log; then
  echo "expected orphan physical file to fail consistency check"
  exit 1
fi
grep -q "数据库没有记录" /tmp/tokenfs-fault-orphan.log

echo "TokenFS fault injection test passed."
