set -eu
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-affinity-v2d-20260920
tar -mxzf /home/wjxt/affinity-v2-freeze-launch.tar.gz
base=/home/wjxt/tokenfs-affinity-v2d-evidence
test ! -e "$base/affinity-v2-confirmation-01"
python3 - <<'PY'
from pathlib import Path
import json,hashlib,sys
sys.path.insert(0,'scripts');from affinity_v2_study import SOURCES
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=Path('study-configs/affinity-v2-freeze-01.json');f=json.loads(p.read_text())
assert f['source_hashes']=={p:sha(p) for p in SOURCES} and f['binary_sha256']==sha('build-release/tokenfs') and f['spec_sha256']==sha('study-configs/affinity-v2-confirmation-01.json')
base=Path('/home/wjxt/tokenfs-affinity-v2d-evidence')
for name in ['affinity-v2-correctness-01','affinity-v2-development-01']:
 assert (base/(name+'.exit')).read_text().strip()=='0'
 assert json.loads((base/name/'batch-audit.json').read_text())['passed']
(base/'confirmation-launch-context.json').write_text(json.dumps(dict(freeze=f,freeze_sha256=sha(p)),indent=2)+'\n')
PY
cat > "$base/confirmation-runner.sh" <<'RUNNER'
set -eu
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-affinity-v2d-20260920
base=/home/wjxt/tokenfs-affinity-v2d-evidence
set +e
python3 scripts/affinity_v2_study.py run --spec study-configs/affinity-v2-confirmation-01.json --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/affinity-v2d --output "$base/affinity-v2-confirmation-01" --freeze study-configs/affinity-v2-freeze-01.json --reference "$base/affinity-v2-correctness-01/batch-audit.json" > "$base/affinity-v2-confirmation-01.log" 2>&1
status=$?
echo "$status" > "$base/affinity-v2-confirmation-01.exit"
exit "$status"
RUNNER
nohup sh "$base/confirmation-runner.sh" > "$base/confirmation-runner.log" 2>&1 < /dev/null &
echo $! > "$base/confirmation.pid"
cat "$base/confirmation.pid"
