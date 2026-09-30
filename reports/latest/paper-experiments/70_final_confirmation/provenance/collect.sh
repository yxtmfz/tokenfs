set -eu
. /home/wjxt/aura-kv-tools/env.sh
root=/home/wjxt/tokenfs-integrated-hpj-cohort-caller-final-evidence
project=/home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-final-20260930
test "$(cat "$root/confirmation.exit")" = 0
cd "$project"
python3 scripts/integrated_hpj_cohort_caller_final_study.py audit --output "$root/confirmation"
python3 scripts/integrated_hpj_cohort_caller_final_study.py report --output "$root/confirmation"
mkdir -p "$root/provenance"
cp study-configs/integrated-hpj-cohort-caller-final-freeze.json "$root/provenance/freeze.json"
cp /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-lazy-20260930/build-release/Testing/Temporary/LastTest.log "$root/provenance/ctest.log"
sha256sum build-release/tokenfs
cat /proc/loadavg
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Unexpected remaining TokenFS process'; exit 2; fi
findmnt -T /srv/tokenfs/remote-cn7
python3 - <<'ARCHIVE'
from pathlib import Path
import tarfile
root=Path('/home/wjxt/tokenfs-integrated-hpj-cohort-caller-final-evidence')
assert not any(str(root) in line for line in Path('/proc/mounts').read_text().splitlines())
with tarfile.open('/home/wjxt/integrated-hpj-cohort-caller-final-evidence.tar.gz','w:gz') as t:
 for f in root.rglob('*'):
  if f.is_file() and f.suffix in ['.json','.db','.log','.exit','.sh'] and not any(x.startswith('cache') for x in f.relative_to(root).parts):t.add(f,arcname=str(f.relative_to(root)))
ARCHIVE
sha256sum /home/wjxt/integrated-hpj-cohort-caller-final-evidence.tar.gz
