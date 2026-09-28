set -eu
. /home/wjxt/aura-kv-tools/env.sh
root=/home/wjxt/tokenfs-readiness-diagnostic-evidence
project=/home/wjxt/projects/tokenfs-readiness-diagnostic-20260928
cat "$root/diagnostic.exit"
# Preserve the failed report-generation status; archive the two completed raw cases.
cd "$project"
python3 scripts/readiness_diagnostic_study.py audit --output "$root/diagnostic"
mkdir -p "$root/provenance"
cp study-configs/readiness-diagnostic-freeze.json "$root/provenance/freeze.json"
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Unexpected own TokenFS process'; exit 2; fi
python3 - <<'PY'
from pathlib import Path
import tarfile,json
root=Path('/home/wjxt/tokenfs-readiness-diagnostic-evidence')
assert not any(str(root) in line for line in Path('/proc/mounts').read_text().splitlines())
for name in ['AdaptiveHP','PoolSIEVE1']:
 r=json.loads((root/'diagnostic/moving_shared-3241'/name/'result.json').read_text())
 print(name,r['effective_mib_s'],r['metrics'].get('measured_commit_copy_cost',0),r['metrics']['read_remote_bytes'])
with tarfile.open('/home/wjxt/readiness-diagnostic-evidence.tar.gz','w:gz') as t:
 for f in root.rglob('*'):
  if f.is_file() and f.suffix in ['.json','.db','.log','.exit','.sh'] and not any(x.startswith('cache') for x in f.relative_to(root).parts):t.add(f,arcname=str(f.relative_to(root)))
PY
sha256sum /home/wjxt/readiness-diagnostic-evidence.tar.gz
