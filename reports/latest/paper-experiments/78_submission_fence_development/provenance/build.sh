set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
project=/home/wjxt/projects/tokenfs-submission-fence78-20261007
mkdir "$project"
tar -mxzf /home/wjxt/tokenfs-submission-fence78-source.tar.gz -C "$project"
cd "$project"
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release
cmake --build build-release -j2
ctest --test-dir build-release --output-on-failure
python3 -m unittest discover -s tests -p '*_test.py'
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts')
from submission_fence_hpj_study import SOURCES,sha
v=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={'development':sha(Path('study-configs/submission-fence-development.json'))})
Path('study-configs/submission-fence-freeze.json').write_text(json.dumps(v,indent=2)+'\n');print('FROZEN_BINARY',v['binary_sha256'])
PY
