set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-causal-reuse-evidence
mkdir /srv/tokenfs/remote-cn7/causal-reuse-20260925
cat > /home/wjxt/tokenfs-causal-reuse-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-causal-reuse-20260925
for stage in correctness development; do
python3 scripts/causal_reuse_pilot.py run --spec study-configs/causal-reuse-pilot-$stage.json --output /home/wjxt/tokenfs-causal-reuse-evidence/$stage --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/causal-reuse-20260925 --freeze study-configs/causal-reuse-pilot-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-causal-reuse-evidence/$stage.exit
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
done
RUN
nohup bash /home/wjxt/tokenfs-causal-reuse-evidence/run.sh > /home/wjxt/tokenfs-causal-reuse-evidence/run.log 2>&1 < /dev/null &
