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

echo "check: healthy metadata and physical files"
mkdir -p "$mount_point/gpu0/check"
printf "consistent token shard\n" > "$mount_point/gpu0/check/ok.tokens"
sync
"$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" check

echo "check: detect orphan physical file"
printf "orphan\n" > /var/lib/tokenfs/local/gpu0/check/orphan.tokens
if "$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" check >/tmp/tokenfs-check-orphan.log; then
  echo "expected orphan file to be reported"
  exit 1
fi
grep -q "数据库没有记录" /tmp/tokenfs-check-orphan.log
rm -f /var/lib/tokenfs/local/gpu0/check/orphan.tokens

echo "check: detect missing physical file"
rm -f /var/lib/tokenfs/local/gpu0/check/ok.tokens
if "$project_root/scripts/tokenfsctl.py" --config "$project_root/config/tokenfs.dev.yaml" check >/tmp/tokenfs-check-missing.log; then
  echo "expected missing physical file to be reported"
  exit 1
fi
grep -q "物理文件不存在" /tmp/tokenfs-check-missing.log

echo "check: startup recovery removes incomplete records"
"$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null
mkdir -p /var/lib/tokenfs/local/gpu0/check
printf "partial\n" > /var/lib/tokenfs/local/gpu0/check/partial.tokens
sqlite3 "$metadata_db" \
  "insert or replace into files(logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,checksum,state,created_at,updated_at,last_access_at,read_count) values('/gpu0/check/partial.tokens',0,'local','local','/var/lib/tokenfs/local/gpu0/check/partial.tokens',8,'','CREATING',0,0,0,0);"
"$project_root/scripts/start_tokenfs.sh" "$project_root/config/tokenfs.dev.yaml" "$mount_point" >/dev/null
test ! -e /var/lib/tokenfs/local/gpu0/check/partial.tokens
sqlite3 "$metadata_db" "select count(*) from files where logical_path='/gpu0/check/partial.tokens';" | grep -q '^0$'

echo "TokenFS consistency test passed."
