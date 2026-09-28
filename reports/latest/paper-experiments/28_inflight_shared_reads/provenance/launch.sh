set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-inflight-shared-evidence
mkdir /srv/tokenfs/remote-cn7/inflight-shared-20260928
cat > /home/wjxt/tokenfs-inflight-shared-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-inflight-shared-20260928
python3 scripts/inflight_shared_study.py run --spec study-configs/inflight-shared-development.json --output /home/wjxt/tokenfs-inflight-shared-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/inflight-shared-20260928 --freeze study-configs/inflight-shared-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-inflight-shared-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-inflight-shared-evidence/run.sh > /home/wjxt/tokenfs-inflight-shared-evidence/run.log 2>&1 < /dev/null &
