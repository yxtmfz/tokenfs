set -eu
. /home/wjxt/aura-kv-tools/env.sh
test "$(cat /home/wjxt/tokenfs-index80-moving-trace-tools/run.exit)" = 0
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Own TokenFS still active'; exit 2; fi
python3 - <<'PACK'
from pathlib import Path
import tarfile,hashlib,json
r=Path('/home/wjxt/tokenfs-indexed-precheck80-moving-trace')
p=Path('/home/wjxt/tokenfs-indexed-precheck80-moving-trace.tar.gz')
assert not p.exists()
assert json.loads((r/'diagnostic-audit.json').read_text())['passed']
assert not any(str(r) in line for line in Path('/proc/mounts').read_text().splitlines())
files=[f for f in sorted(r.rglob('*')) if f.is_file() and not any(x.startswith('cache') for x in f.relative_to(r).parts) and (f.suffix in ['.json','.db','.log','.csv','.md'] or f.name.startswith('state.db-'))]
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
before={str(f.relative_to(r)):sha(f) for f in files}
with tarfile.open(p,'w:gz') as t:
 for f in files:t.add(f,arcname=str(f.relative_to(r)))
assert before=={str(f.relative_to(r)):sha(f) for f in files}
with tarfile.open(p) as t:
 assert {m.name:hashlib.sha256(t.extractfile(m).read()).hexdigest() for m in t.getmembers()}==before
print(json.dumps(dict(files=len(files),sha256=sha(p),sidecars=[x for x in before if 'state.db-' in x],originals_unchanged=True)))
PACK
