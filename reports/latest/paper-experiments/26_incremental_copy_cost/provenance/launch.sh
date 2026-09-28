set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-incremental-cost-evidence
mkdir /srv/tokenfs/remote-cn7/incremental-cost-20260928
cat > /home/wjxt/tokenfs-incremental-cost-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-incremental-cost-20260928
python3 scripts/incremental_cost_study.py run --spec study-configs/incremental-cost-development.json --output /home/wjxt/tokenfs-incremental-cost-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/incremental-cost-20260928 --freeze study-configs/incremental-cost-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-incremental-cost-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-incremental-cost-evidence/run.sh > /home/wjxt/tokenfs-incremental-cost-evidence/run.log 2>&1 < /dev/null &
