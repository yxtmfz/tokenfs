set -eu
python3 - <<'PY'
from pathlib import Path
import hashlib,json
r=Path('/home/wjxt/tokenfs-submission-fence78-evidence')
for p in sorted(r.rglob('state.db*')):
 print(json.dumps({'path':str(p.relative_to(r)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))
PY
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Unexpected own TokenFS'; exit 2; fi
