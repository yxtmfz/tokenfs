set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-component-ablation-evidence
mkdir /srv/tokenfs/remote-cn7/component-ablation-20260928
cat > /home/wjxt/tokenfs-component-ablation-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-component-ablation-20260928
python3 scripts/component_ablation_study.py run --spec study-configs/component-ablation-development.json --output /home/wjxt/tokenfs-component-ablation-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/component-ablation-20260928 --freeze study-configs/component-ablation-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-component-ablation-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-component-ablation-evidence/run.sh > /home/wjxt/tokenfs-component-ablation-evidence/run.log 2>&1 < /dev/null &
