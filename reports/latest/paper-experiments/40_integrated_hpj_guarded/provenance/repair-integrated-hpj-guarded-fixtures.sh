set -eu
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-integrated-hpj-guarded-20260929
tar -mxzf /home/wjxt/integrated-hpj-test-fixtures.tar.gz
ctest --test-dir build-release --output-on-failure
python3 -m unittest discover -s tests -p '*_test.py'
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts')
from integrated_hpj_guarded_study import SOURCES,sha
v=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={'development':sha(Path('study-configs/integrated-hpj-guarded-development.json'))})
Path('study-configs/integrated-hpj-guarded-freeze.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
PY
