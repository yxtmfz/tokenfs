set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
project=/home/wjxt/projects/tokenfs-integrated-hpj-reverse-20260929
mkdir "$project"
tar -mxzf /home/wjxt/integrated-hpj-reverse-source.tar.gz -C "$project"
cd "$project"
mkdir -p build-release/Testing/Temporary
cp /home/wjxt/projects/tokenfs-integrated-hpj-guarded-20260929/build-release/tokenfs build-release/tokenfs
cp /home/wjxt/projects/tokenfs-integrated-hpj-guarded-20260929/build-release/CMakeCache.txt build-release/CMakeCache.txt
cp /home/wjxt/projects/tokenfs-integrated-hpj-guarded-20260929/build-release/Testing/Temporary/LastTest.log build-release/Testing/Temporary/LastTest.log
cmp build-release/tokenfs /home/wjxt/projects/tokenfs-integrated-hpj-guarded-20260929/build-release/tokenfs
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts')
from integrated_hpj_reverse_study import SOURCES,sha
v=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={'development':sha(Path('study-configs/integrated-hpj-reverse-development.json'))})
Path('study-configs/integrated-hpj-reverse-freeze.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
PY
