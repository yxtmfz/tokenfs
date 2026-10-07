set -eu
. /home/wjxt/aura-kv-tools/env.sh
root=/home/wjxt/tokenfs-submission-fence78-evidence
project=/home/wjxt/projects/tokenfs-submission-fence78-20261007
test "$(cat "$root/development.exit")" = 0
test "$(cat "$root/correctness.exit")" = 0
cd "$project"
python3 scripts/submission_fence_hpj_study.py audit --output "$root/development"
mkdir "$root/provenance"
cp study-configs/submission-fence-freeze.json "$root/provenance/freeze.json"
cp build-release/Testing/Temporary/LastTest.log "$root/provenance/native-tests.log"
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Unexpected remaining TokenFS process'; exit 2; fi
python3 - <<'PY'
from pathlib import Path
import tarfile,hashlib
r=Path('/home/wjxt/tokenfs-submission-fence78-evidence')
assert not any(str(r) in line for line in Path('/proc/mounts').read_text().splitlines())
# An immutable offline SQLite read must never silently omit live WAL/SHM.
sidecars=list(r.rglob('state.db-*'))
assert not sidecars, 'SQLite sidecars remain before collection: '+str([str(p.relative_to(r)) for p in sidecars])
p=Path('/home/wjxt/tokenfs-submission-fence78-evidence.tar.gz')
with tarfile.open(p,'w:gz') as t:
 for f in sorted(r.rglob('*')):
  if f.is_file() and f.suffix in ['.json','.db','.log','.exit','.sh'] and not any(x.startswith('cache') for x in f.relative_to(r).parts):t.add(f,arcname=str(f.relative_to(r)))
print(hashlib.sha256(p.read_bytes()).hexdigest())
PY
