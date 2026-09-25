set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-compact-closeout-evidence
mkdir /srv/tokenfs/remote-cn7/compact-closeout-20260925
cat > /home/wjxt/tokenfs-compact-closeout-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-compact-closeout-20260925
for stage in correctness development; do
python3 scripts/compact_planning_study.py run --spec study-configs/compact-planning-closeout-$stage.json --output /home/wjxt/tokenfs-compact-closeout-evidence/$stage --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/compact-closeout-20260925 --freeze study-configs/compact-planning-closeout-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-compact-closeout-evidence/$stage.exit
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
done
RUN
nohup bash /home/wjxt/tokenfs-compact-closeout-evidence/run.sh > /home/wjxt/tokenfs-compact-closeout-evidence/run.log 2>&1 < /dev/null &
