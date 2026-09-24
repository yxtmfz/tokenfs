set -eu
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-shared-joint-20260924
python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'scripts');import shared_joint_pilot as s
r=Path('/home/wjxt/tokenfs-shared-joint-evidence/correctness')
assert s.audit(r)['passed']
assert not Path('/home/wjxt/tokenfs-shared-joint-evidence/development').exists()
PY
cat > /home/wjxt/tokenfs-shared-joint-evidence/run-speed.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-shared-joint-20260924
python3 scripts/shared_joint_pilot.py run --spec study-configs/shared-joint-pilot-development.json --output /home/wjxt/tokenfs-shared-joint-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/shared-joint-20260924 --freeze study-configs/shared-joint-pilot-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-shared-joint-evidence/speed.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-shared-joint-evidence/run-speed.sh > /home/wjxt/tokenfs-shared-joint-evidence/speed.log 2>&1 < /dev/null &
