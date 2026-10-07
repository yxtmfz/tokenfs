set -eu
. /home/wjxt/aura-kv-tools/env.sh
test "$(cat /home/wjxt/tokenfs-indexed-precheck80-evidence/development.exit)" = 0
test "$(cat /home/wjxt/tokenfs-indexed-precheck80-evidence/correctness.exit)" = 0
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Own TokenFS still active'; exit 2; fi
tools=/home/wjxt/tokenfs-index80-moving-trace-tools
mkdir "$tools"
tar -mxzf /home/wjxt/tokenfs-index80-moving-trace-tools.tar.gz -C "$tools"
if PYTHONDONTWRITEBYTECODE=1 python3 "$tools/tail-trace.py" run --source-root /home/wjxt/projects/tokenfs-indexed-precheck80-20261007 --binary /home/wjxt/projects/tokenfs-indexed-precheck80-20261007/build-release/tokenfs --freeze /home/wjxt/projects/tokenfs-indexed-precheck80-20261007/study-configs/indexed-precheck-freeze.json --diagnostic-freeze "$tools/tail-trace-freeze.json" --output /home/wjxt/tokenfs-indexed-precheck80-moving-trace --remote-root /srv/tokenfs/remote-cn7/indexed-precheck80-20261007 > "$tools/run.log" 2>&1; then
 printf '0\n' > "$tools/run.exit"
 cat "$tools/run.log"
else
 rc=$?
 printf '%s\n' "$rc" > "$tools/run.exit"
 cat "$tools/run.log"
 exit "$rc"
fi
