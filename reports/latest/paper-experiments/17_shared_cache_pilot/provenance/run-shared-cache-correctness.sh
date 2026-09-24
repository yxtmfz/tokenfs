set -eu
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-shared-pilot-20260924
mkdir /home/wjxt/tokenfs-shared-pilot-evidence
mkdir /srv/tokenfs/remote-cn7/shared-pilot-20260924
python3 scripts/shared_cache_pilot.py run --spec study-configs/shared-cache-pilot-correctness.json --output /home/wjxt/tokenfs-shared-pilot-evidence/correctness --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/shared-pilot-20260924 --freeze study-configs/shared-cache-pilot-freeze.json
python3 - <<'PY'
import json
from pathlib import Path
r=Path('/home/wjxt/tokenfs-shared-pilot-evidence/correctness')
print((r/'batch-audit.json').read_text())
for p in r.glob('*/*/result.json'):
 d=json.loads(p.read_text());print(d['strategy'],d['metrics'].get('peer_cache_hit',0),d['verified_replicas'])
 if d['strategy']=='AnyReadyShare':assert d['metrics'].get('peer_cache_hit',0)>0
PY
