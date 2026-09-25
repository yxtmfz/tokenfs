set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
project=/home/wjxt/projects/tokenfs-burst-reuse-20260925
mkdir "$project"
tar -mxzf /home/wjxt/burst-reuse-source.tar.gz -C "$project"
cd "$project"
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release
cmake --build build-release -j2
ctest --test-dir build-release --output-on-failure
python3 -m unittest tests.aura_kv_unit_test tests.evidence_test tests.measured_study_test tests.affinity_joint_test tests.affinity_v2_test tests.affinity_v3_test tests.paper_minimal_test tests.shared_cache_pilot_test tests.shared_joint_pilot_test tests.causal_reuse_pilot_test tests.compact_planning_test tests.burst_reuse_test
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts')
from burst_reuse_study import SOURCES,sha
v=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={stage:sha(Path(f'study-configs/burst-reuse-{stage}.json')) for stage in ['correctness','development']})
Path('study-configs/burst-reuse-freeze.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
PY
