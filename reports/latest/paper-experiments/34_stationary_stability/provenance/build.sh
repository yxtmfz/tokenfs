set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
project=/home/wjxt/projects/tokenfs-stationary-stability-20260929
mkdir "$project"
tar -mxzf /home/wjxt/stationary-stability-source.tar.gz -C "$project"
cd "$project"
python3 - <<'PY'
import sys,json,shutil
from pathlib import Path
sys.path.insert(0,'scripts')
from stationary_stability_study import SOURCES,sha
old=Path('/home/wjxt/projects/tokenfs-headroom-exploration-20260929')
frozen=json.loads((old/'study-configs/headroom-exploration-freeze.json').read_text())
assert all(sha(Path(p))==h for p,h in frozen['source_hashes'].items()),'old source changed'
assert sha(old/'build-release/tokenfs')==frozen['binary_sha256']=='2757459e304a99751ed9f9c69b3a549c56243dbeb3b779f29cb68ce9164a591c'
Path('build-release/Testing/Temporary').mkdir(parents=True)
for name in ['tokenfs','CMakeCache.txt']:
 shutil.copy2(old/'build-release'/name,Path('build-release')/name)
shutil.copy2(old/'build-release/Testing/Temporary/LastTest.log','build-release/Testing/Temporary/LastTest.log')
v=dict(source_hashes={p:sha(Path(p)) for p in SOURCES},binary_sha256=sha(Path('build-release/tokenfs')),specs={'development':sha(Path('study-configs/stationary-stability-development.json'))})
Path('study-configs/stationary-stability-freeze.json').write_text(json.dumps(v,indent=2)+'\n')
Path('study-configs/binary-reuse.json').write_text(json.dumps(dict(recompiled=False,origin=str(old),original_source_commit='f828c04e5e2e3d73e1c35132de6dc1625e28413b',original_freeze=frozen,original_native_test_log_reused=True),indent=2)+'\n')
print(json.dumps(v))
PY
python3 -m unittest discover -s tests -p '*_test.py'
