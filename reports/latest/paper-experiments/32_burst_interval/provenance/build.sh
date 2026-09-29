set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
project=/home/wjxt/projects/tokenfs-burst-interval-20260929
mkdir "$project"
tar -mxzf /home/wjxt/burst-interval-source.tar.gz -C "$project"
cd "$project"
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release
cmake --build build-release -j2
ctest --test-dir build-release --output-on-failure
python3 -m unittest discover -s tests -p '*_test.py'
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts')
from burst_interval_study import SOURCES,sha
v=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={'development':sha(Path('study-configs/burst-interval-development.json'))})
Path('study-configs/burst-interval-freeze.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
PY
