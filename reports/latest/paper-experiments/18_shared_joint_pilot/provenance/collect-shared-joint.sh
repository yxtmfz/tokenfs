set -eu
python3 - <<'PY'
from pathlib import Path
import tarfile,json,hashlib
r=Path('/home/wjxt/tokenfs-shared-joint-evidence')
assert (r/'speed.exit').read_text().strip()=='0'
assert len(list((r/'development').glob('*/*/result.json')))==18
assert len(list((r/'correctness').glob('*/*/result.json')))==6
assert not any(str(r) in l for l in Path('/proc/mounts').read_text().splitlines())
p=Path('/home/wjxt/projects/tokenfs-shared-joint-20260924')
a=Path('/home/wjxt/shared-joint-pilot-evidence.tar.gz')
with tarfile.open(a,'w:gz') as t:
 for f in r.rglob('*'):
  if f.is_file() and f.suffix in ['.json','.db','.log','.exit','.sh'] and not any(x.startswith('cache') for x in f.relative_to(r).parts):t.add(f,arcname=str(f.relative_to(r)))
 t.add(p/'study-configs/shared-joint-pilot-freeze.json',arcname='provenance/freeze.json')
 t.add(p/'build-release/Testing/Temporary/LastTest.log',arcname='provenance/ctest.log')
print(json.dumps(dict(bytes=a.stat().st_size,sha256=hashlib.sha256(a.read_bytes()).hexdigest(),speed_runs=18,content_runs=6)))
PY
