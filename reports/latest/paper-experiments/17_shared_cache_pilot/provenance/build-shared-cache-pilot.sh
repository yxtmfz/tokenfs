set -eu
. /home/wjxt/aura-kv-tools/env.sh
project=/home/wjxt/projects/tokenfs-shared-pilot-20260924
mkdir "$project"
tar -xzf /home/wjxt/shared-cache-pilot-source.tar.gz -C "$project"
cd "$project"
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release
cmake --build build-release -j2
ctest --test-dir build-release --output-on-failure
python3 tests/shared_cache_pilot_test.py
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts')
from shared_cache_pilot import SOURCES,sha
out=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={stage:sha(Path(f'study-configs/shared-cache-pilot-{stage}.json')) for stage in ['correctness','development']})
Path('study-configs/shared-cache-pilot-freeze.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
PY
