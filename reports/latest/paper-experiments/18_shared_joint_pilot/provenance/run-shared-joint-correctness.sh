set -eu
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-shared-joint-20260924
mkdir /home/wjxt/tokenfs-shared-joint-evidence
mkdir /srv/tokenfs/remote-cn7/shared-joint-20260924
python3 scripts/shared_joint_pilot.py run --spec study-configs/shared-joint-pilot-correctness.json --output /home/wjxt/tokenfs-shared-joint-evidence/correctness --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/shared-joint-20260924 --freeze study-configs/shared-joint-pilot-freeze.json
python3 - <<'PY'
import json
from pathlib import Path
r=Path('/home/wjxt/tokenfs-shared-joint-evidence/correctness')
print((r/'batch-audit.json').read_text())
for p in r.glob('*/*/result.json'):
 d=json.loads(p.read_text());print(d['strategy'],d['metrics'].get('shared_placement_selected',0),d['metrics'].get('shared_placement_relocated',0),d['retained_cache_bytes'])
 if d['strategy']=='HP':assert d['metrics'].get('shared_placement_selected',0)>0
 if d['strategy']=='PoolSIEVE2':assert d['retained_cache_bytes'][1:]==[0,0]
PY
