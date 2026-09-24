set -eu
. /home/wjxt/aura-kv-tools/env.sh
hostname
cat /proc/loadavg
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process; do not overlap'; exit 2; fi
project=/home/wjxt/projects/tokenfs-shared-joint-20260924
mkdir "$project"
tar -xzf /home/wjxt/shared-joint-pilot-source.tar.gz -C "$project"
cd "$project"
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release
cmake --build build-release -j2
ctest --test-dir build-release --output-on-failure
python3 -m unittest tests.aura_kv_unit_test tests.evidence_test tests.measured_study_test tests.affinity_joint_test tests.affinity_v2_test tests.affinity_v3_test tests.paper_minimal_test tests.shared_cache_pilot_test tests.shared_joint_pilot_test
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts')
from shared_joint_pilot import SOURCES,sha
v=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={stage:sha(Path(f'study-configs/shared-joint-pilot-{stage}.json')) for stage in ['correctness','development']})
Path('study-configs/shared-joint-pilot-freeze.json').write_text(json.dumps(v,indent=2)+'\n')
print(json.dumps(v))
PY
