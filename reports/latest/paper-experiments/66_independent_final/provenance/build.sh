set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
project=/home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-independent-20260929
mkdir "$project"
tar -mxzf /home/wjxt/integrated-hpj-cohort-caller-independent-source.tar.gz -C "$project"
cd "$project"
mkdir -p build-release/Testing/Temporary
cp /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-20260929/build-release/tokenfs build-release/tokenfs
cp /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-20260929/build-release/CMakeCache.txt build-release/CMakeCache.txt
cp /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-20260929/build-release/Testing/Temporary/LastTest.log build-release/Testing/Temporary/LastTest.log
python3 - <<'CHECK'
from pathlib import Path
import hashlib
old=Path('/home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-20260929')
for folder in ['src','tests']:
 for f in (old/folder).rglob('*'):
  if f.is_file() and f.suffix in ['.h','.cpp']:
   p=Path(f.relative_to(old));assert p.read_bytes()==f.read_bytes(),str(p)
assert Path('CMakeLists.txt').read_bytes()==(old/'CMakeLists.txt').read_bytes()
assert hashlib.sha256(Path('build-release/tokenfs').read_bytes()).hexdigest()=='b8c9d323a658a857c0ee4b467967dbf7e24f5523bc54944a8d9710100440b4d4'
print('Retained native source and exact report64 binary verified')
CHECK
ctest --test-dir /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-20260929/build-release --output-on-failure
python3 -m unittest discover -s tests -p '*_test.py'
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts')
from integrated_hpj_cohort_caller_independent_study import SOURCES,sha
v=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={'independent':sha(Path('study-configs/integrated-hpj-cohort-caller-independent-development.json'))})
Path('study-configs/integrated-hpj-cohort-caller-independent-freeze.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
PY
