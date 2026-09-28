set -eu
. /home/wjxt/aura-kv-tools/env.sh
hostname
cat /proc/loadavg
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
findmnt -T /srv/tokenfs/remote-cn7
project=/home/wjxt/projects/tokenfs-readiness-diagnostic-20260928
old=/home/wjxt/projects/tokenfs-incremental-cost-20260928
mkdir "$project"
tar -mxzf /home/wjxt/readiness-diagnostic-source.tar.gz -C "$project"
cd "$project"
for f in src/main.cpp src/measured_policy.h src/copy_cost.h src/request_trace.h src/read_fill.h src/request_read_cost.h src/sieve_policy.h; do cmp "$f" "$old/$f"; done
mkdir build-release
cp "$old/build-release/tokenfs" "$old/build-release/CMakeCache.txt" build-release/
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts');from readiness_diagnostic_study import SOURCES,sha
v=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={'diagnostic':sha(Path('study-configs/readiness-diagnostic.json'))})
assert v['binary_sha256']=='7b724487dc5e4454f98d5d2598b12a9aa51b76491a269d18614f2639f3210ba9'
Path('study-configs/readiness-diagnostic-freeze.json').write_text(json.dumps(v,indent=2)+'\n')
PY
mkdir /home/wjxt/tokenfs-readiness-diagnostic-evidence /srv/tokenfs/remote-cn7/readiness-diagnostic-20260928
cat > /home/wjxt/tokenfs-readiness-diagnostic-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-readiness-diagnostic-20260928
python3 scripts/readiness_diagnostic_study.py run --spec study-configs/readiness-diagnostic.json --output /home/wjxt/tokenfs-readiness-diagnostic-evidence/diagnostic --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/readiness-diagnostic-20260928 --freeze study-configs/readiness-diagnostic-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-readiness-diagnostic-evidence/diagnostic.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-readiness-diagnostic-evidence/run.sh > /home/wjxt/tokenfs-readiness-diagnostic-evidence/run.log 2>&1 < /dev/null &
