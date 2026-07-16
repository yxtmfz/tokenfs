#!/usr/bin/env bash
set -euo pipefail

mount_point="${1:-/mnt/tokenfs}"
metadata_db="${TOKENFS_DB:-/var/lib/tokenfs/metadata/tokenfs.db}"

echo "Listing root:"
ls -la "$mount_point"

echo "Writing a small local token file:"
mkdir -p "$mount_point/gpu0/demo"
echo "hello tokenfs" > "$mount_point/gpu0/demo/a.tokens"
cat "$mount_point/gpu0/demo/a.tokens"

echo "Creating a large sparse file to trigger remote spill:"
truncate -s 80M "$mount_point/gpu0/big.tokens"
sync

echo "Local files:"
find /var/lib/tokenfs/local -maxdepth 5 -type f -printf "%p %s\n" | sort

echo "Remote-sim files:"
find /var/lib/tokenfs/remote-sim -maxdepth 5 -type f -printf "%p %s\n" | sort

echo "Metadata:"
sqlite3 "$metadata_db" \
  "select logical_path,tier,physical_path,size_bytes,checksum,state from files order by logical_path;"
