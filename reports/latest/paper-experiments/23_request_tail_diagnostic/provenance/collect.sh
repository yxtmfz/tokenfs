set -eu
. /home/wjxt/aura-kv-tools/env.sh
root=/home/wjxt/tokenfs-tail-diagnostic-evidence
project=/home/wjxt/projects/tokenfs-tail-diagnostic-20260928
test "$(cat "$root/diagnostic.exit")" = 0
cd "$project"
python3 scripts/tail_diagnostic_study.py audit --output "$root/diagnostic"
python3 scripts/tail_diagnostic_study.py report --output "$root/diagnostic"
mkdir -p "$root/provenance"
cp study-configs/tail-diagnostic-freeze.json "$root/provenance/freeze.json"
cp build-release/Testing/Temporary/LastTest.log "$root/provenance/ctest.log"
sha256sum build-release/tokenfs
cat /proc/loadavg
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Unexpected remaining TokenFS process'; exit 2; fi
findmnt -T /srv/tokenfs/remote-cn7
python3 - <<'ARCHIVE'
from pathlib import Path
import tarfile
root=Path('/home/wjxt/tokenfs-tail-diagnostic-evidence')
assert not any(str(root) in line for line in Path('/proc/mounts').read_text().splitlines())
with tarfile.open('/home/wjxt/tail-diagnostic-evidence.tar.gz','w:gz') as t:
 for f in root.rglob('*'):
  if f.is_file() and f.suffix in ['.json','.db','.log','.exit','.sh'] and not any(x.startswith('cache') for x in f.relative_to(root).parts):t.add(f,arcname=str(f.relative_to(root)))
ARCHIVE
sha256sum /home/wjxt/tail-diagnostic-evidence.tar.gz
