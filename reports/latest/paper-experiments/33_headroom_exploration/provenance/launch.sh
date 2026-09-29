set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-headroom-exploration-evidence
mkdir /srv/tokenfs/remote-cn7/headroom-exploration-20260929
cat > /home/wjxt/tokenfs-headroom-exploration-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-headroom-exploration-20260929
python3 scripts/headroom_exploration_study.py run --spec study-configs/headroom-exploration-development.json --output /home/wjxt/tokenfs-headroom-exploration-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/headroom-exploration-20260929 --freeze study-configs/headroom-exploration-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-headroom-exploration-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-headroom-exploration-evidence/run.sh > /home/wjxt/tokenfs-headroom-exploration-evidence/run.log 2>&1 < /dev/null &
