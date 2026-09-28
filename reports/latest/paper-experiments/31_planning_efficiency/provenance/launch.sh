set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-planning-efficiency-evidence
mkdir /srv/tokenfs/remote-cn7/planning-efficiency-20260929
cat > /home/wjxt/tokenfs-planning-efficiency-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-planning-efficiency-20260929
python3 scripts/planning_efficiency_study.py run --spec study-configs/planning-efficiency-development.json --output /home/wjxt/tokenfs-planning-efficiency-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/planning-efficiency-20260929 --freeze study-configs/planning-efficiency-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-planning-efficiency-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-planning-efficiency-evidence/run.sh > /home/wjxt/tokenfs-planning-efficiency-evidence/run.log 2>&1 < /dev/null &
