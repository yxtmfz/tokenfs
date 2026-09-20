set -eu
case "$(hostname)" in
 cn7) . /home/wjxt/aura-kv-tools/env.sh;;
 cn8) . /home/wjxt/tokenfs-eval-tools-20260919/env.sh;;
 *) exit 2;;
esac
cd /home/wjxt/projects/tokenfs-affinity-v3e-20260920
python3 - <<'PY'
from pathlib import Path
import json,hashlib,platform
import sys
sys.path.insert(0,'scripts')
import affinity_v3_study as study
study.activate();host=platform.node();base=Path('/home/wjxt/tokenfs-affinity-v3e-evidence')
names=['affinity-v3-correctness-01']+(['affinity-v3-development-01'] if host=='cn7' else [])
assert (base/'build.exit').read_text().strip()=='0'
records={}
for name in names:
 assert (base/(name+'.exit')).read_text().strip()=='0'
 records[name]=study.core.audit(base/name);assert records[name]['passed']
assert not (base/'affinity-v3-confirmation-01').exists()
mounts=[line for line in Path('/proc/mounts').read_text().splitlines() if str(base) in line];assert not mounts
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
result=dict(host=host,binary_sha256=sha('build-release/tokenfs'),source_hashes={p:sha(p) for p in study.SOURCES},spec_sha256=sha('study-configs/affinity-v3-confirmation-01.json'),records=records,remaining_mounts=mounts)
(base/'preflight.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
PY
