set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-stationary-stability-evidence
mkdir /srv/tokenfs/remote-cn7/stationary-stability-20260929
cat > /home/wjxt/tokenfs-stationary-stability-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-stationary-stability-20260929
python3 scripts/stationary_stability_study.py run --spec study-configs/stationary-stability-development.json --output /home/wjxt/tokenfs-stationary-stability-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/stationary-stability-20260929 --freeze study-configs/stationary-stability-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-stationary-stability-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-stationary-stability-evidence/run.sh > /home/wjxt/tokenfs-stationary-stability-evidence/run.log 2>&1 < /dev/null &
