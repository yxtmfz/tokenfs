set -eu
python3 - <<'PY'
from pathlib import Path
import tarfile,json,hashlib
root=Path('/home/wjxt/tokenfs-shared-pilot-evidence')
assert (root/'speed.exit').read_text().strip()=='0'
assert len(list((root/'development').glob('*/*/result.json')))==18
assert len(list((root/'correctness').glob('*/*/result.json')))==3
assert not any(str(root) in x for x in Path('/proc/mounts').read_text().splitlines())
project=Path('/home/wjxt/projects/tokenfs-shared-pilot-20260924')
archive=Path('/home/wjxt/shared-cache-pilot-evidence.tar.gz')
with tarfile.open(archive,'w:gz') as tar:
 for p in root.rglob('*'):
  if p.is_file() and (p.suffix in ['.json','.db','.log','.exit','.sh']) and not any(x.startswith('cache') for x in p.relative_to(root).parts):
   tar.add(p,arcname=str(p.relative_to(root)))
 tar.add(project/'study-configs/shared-cache-pilot-freeze.json',arcname='provenance/freeze.json')
 tar.add(project/'build-release/Testing/Temporary/LastTest.log',arcname='provenance/ctest.log')
print(json.dumps(dict(bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),speed_runs=18,content_runs=3)))
PY
