set -eu
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-shared-pilot-20260924
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts')
import shared_cache_pilot as s
r=Path('/home/wjxt/tokenfs-shared-pilot-evidence/correctness')
assert s.audit(r)['passed']
assert any(json.loads(p.read_text())['metrics'].get('peer_cache_hit',0)>0 for p in r.glob('*/AnyReadyShare/result.json'))
assert not Path('/home/wjxt/tokenfs-shared-pilot-evidence/development').exists()
PY
cat > /home/wjxt/tokenfs-shared-pilot-evidence/run-speed.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-shared-pilot-20260924
python3 scripts/shared_cache_pilot.py run --spec study-configs/shared-cache-pilot-development.json --output /home/wjxt/tokenfs-shared-pilot-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/shared-pilot-20260924 --freeze study-configs/shared-cache-pilot-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-shared-pilot-evidence/speed.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-shared-pilot-evidence/run-speed.sh > /home/wjxt/tokenfs-shared-pilot-evidence/speed.log 2>&1 < /dev/null &
