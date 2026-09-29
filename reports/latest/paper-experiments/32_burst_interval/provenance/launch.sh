set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-burst-interval-evidence
mkdir /srv/tokenfs/remote-cn7/burst-interval-20260929
cat > /home/wjxt/tokenfs-burst-interval-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-burst-interval-20260929
python3 scripts/burst_interval_study.py run --spec study-configs/burst-interval-development.json --output /home/wjxt/tokenfs-burst-interval-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/burst-interval-20260929 --freeze study-configs/burst-interval-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-burst-interval-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-burst-interval-evidence/run.sh > /home/wjxt/tokenfs-burst-interval-evidence/run.log 2>&1 < /dev/null &
