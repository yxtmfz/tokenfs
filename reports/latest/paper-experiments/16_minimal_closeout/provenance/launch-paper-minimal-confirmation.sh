set -eu
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-paper-minimal-20260921
tar -mxzf /home/wjxt/paper-minimal-freeze-launch.tar.gz
base=/home/wjxt/tokenfs-paper-minimal-evidence
test ! -e "$base/paper-minimal-confirmation-01"
python3 - <<'PY'
from pathlib import Path
import json,hashlib,sys
sys.path.insert(0,'scripts');from paper_minimal_study import SOURCES
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=Path('study-configs/paper-minimal-freeze-01.json');f=json.loads(p.read_text())
assert f['source_hashes']=={p:sha(p) for p in SOURCES} and f['binary_sha256']==sha('build-release/tokenfs') and f['spec_sha256']==sha('study-configs/paper-minimal-confirmation-01.json')
assert f['sensitivity_spec_sha256']==sha('study-configs/paper-minimal-sensitivity-01.json') and f['plan_sha256']==sha('docs/paper-minimal-plan.md')
base=Path('/home/wjxt/tokenfs-paper-minimal-evidence')
for name in ['paper-minimal-correctness-01','paper-minimal-development-01']:
 assert (base/(name+'.exit')).read_text().strip()=='0'
 assert json.loads((base/name/'batch-audit.json').read_text())['passed']
(base/'confirmation-launch-context.json').write_text(json.dumps(dict(freeze=f,freeze_sha256=sha(p)),indent=2)+'\n')
PY
cat > "$base/confirmation-runner.sh" <<'RUNNER'
set -eu
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-paper-minimal-20260921
base=/home/wjxt/tokenfs-paper-minimal-evidence
set +e
python3 scripts/paper_minimal_study.py run --spec study-configs/paper-minimal-confirmation-01.json --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/paper-minimal --output "$base/paper-minimal-confirmation-01" --freeze study-configs/paper-minimal-freeze-01.json --reference "$base/paper-minimal-correctness-01/batch-audit.json" > "$base/paper-minimal-confirmation-01.log" 2>&1
status=$?
echo "$status" > "$base/paper-minimal-confirmation-01.exit"
if [ "$status" -ne 0 ]; then exit "$status"; fi
python3 scripts/paper_minimal_study.py run --spec study-configs/paper-minimal-sensitivity-01.json --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/paper-minimal --output "$base/paper-minimal-sensitivity-01" > "$base/paper-minimal-sensitivity-01.log" 2>&1
status=$?
echo "$status" > "$base/paper-minimal-sensitivity-01.exit"
exit "$status"
RUNNER
nohup sh "$base/confirmation-runner.sh" > "$base/confirmation-runner.log" 2>&1 < /dev/null &
echo $! > "$base/confirmation.pid"
cat "$base/confirmation.pid"
