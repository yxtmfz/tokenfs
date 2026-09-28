set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-request-cost-evidence
mkdir /srv/tokenfs/remote-cn7/request-cost-20260928
cat > /home/wjxt/tokenfs-request-cost-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-request-cost-20260928
python3 scripts/request_cost_study.py run --spec study-configs/request-cost-development.json --output /home/wjxt/tokenfs-request-cost-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/request-cost-20260928 --freeze study-configs/request-cost-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-request-cost-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-request-cost-evidence/run.sh > /home/wjxt/tokenfs-request-cost-evidence/run.log 2>&1 < /dev/null &
