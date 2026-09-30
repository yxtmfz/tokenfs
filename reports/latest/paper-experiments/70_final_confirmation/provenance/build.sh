set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
project=/home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-final-20260930
mkdir "$project"
tar -mxzf /home/wjxt/integrated-hpj-cohort-caller-final-source.tar.gz -C "$project"
cd "$project"
old=/home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-lazy-20260930
 diff -r src "$old/src"
 cmp CMakeLists.txt "$old/CMakeLists.txt"
 mkdir -p build-release/Testing/Temporary
 cp "$old/build-release/tokenfs" build-release/tokenfs
 cp "$old/build-release/CMakeCache.txt" build-release/CMakeCache.txt
 cp "$old/build-release/Testing/Temporary/LastTest.log" build-release/Testing/Temporary/LastTest.log
 ctest --test-dir "$old/build-release" --output-on-failure
python3 -m unittest discover -s tests -p '*_test.py'
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts')
from integrated_hpj_cohort_caller_final_study import SOURCES,sha
v=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={'confirmation':sha(Path('study-configs/integrated-hpj-cohort-caller-final-confirmation.json'))})
Path('study-configs/integrated-hpj-cohort-caller-final-freeze.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
PY
