#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="${1:-$project_root/config/tokenfs.dev.yaml}"
mount_point="${2:-/mnt/tokenfs}"
log_file="${TOKENFS_LOG:-/tmp/tokenfs.log}"
pid_file="${TOKENFS_PID:-/tmp/tokenfs.pid}"

if [[ ! -x "$project_root/build/tokenfs" ]]; then
  echo "tokenfs binary not found. Build first:"
  echo "  cmake -S \"$project_root\" -B \"$project_root/build\" -G Ninja"
  echo "  cmake --build \"$project_root/build\""
  exit 1
fi

mkdir -p "$mount_point"
fusermount3 -u "$mount_point" 2>/dev/null || true

"$project_root/build/tokenfs" --config "$config" -f "$mount_point" >"$log_file" 2>&1 &
pid=$!
echo "$pid" >"$pid_file"
sleep 1

if ! kill -0 "$pid" 2>/dev/null; then
  echo "TokenFS failed to start. Log:"
  cat "$log_file"
  exit 1
fi

echo "TokenFS mounted at $mount_point"
echo "pid=$pid"
echo "log=$log_file"
