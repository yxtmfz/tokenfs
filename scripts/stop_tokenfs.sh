#!/usr/bin/env bash
set -euo pipefail

mount_point="${1:-/mnt/tokenfs}"
pid_file="${TOKENFS_PID:-/tmp/tokenfs.pid}"

fusermount3 -u "$mount_point" 2>/dev/null || true

if [[ -f "$pid_file" ]]; then
  pid="$(cat "$pid_file")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
fi

echo "TokenFS stopped for $mount_point"
