set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-adaptive-control-evidence
mkdir /srv/tokenfs/remote-cn7/adaptive-control-20260928
cat > /home/wjxt/tokenfs-adaptive-control-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-adaptive-control-20260928
for stage in correctness development; do
python3 scripts/adaptive_control_study.py run --spec study-configs/adaptive-control-$stage.json --output /home/wjxt/tokenfs-adaptive-control-evidence/$stage --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/adaptive-control-20260928 --freeze study-configs/adaptive-control-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-adaptive-control-evidence/$stage.exit
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
done
RUN
nohup bash /home/wjxt/tokenfs-adaptive-control-evidence/run.sh > /home/wjxt/tokenfs-adaptive-control-evidence/run.log 2>&1 < /dev/null &
