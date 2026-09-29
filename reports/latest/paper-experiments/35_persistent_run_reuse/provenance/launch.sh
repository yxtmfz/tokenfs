set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-run-reuse-evidence
mkdir /srv/tokenfs/remote-cn7/run-reuse-20260929
cat > /home/wjxt/tokenfs-run-reuse-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-run-reuse-20260929
python3 scripts/run_reuse_study.py run --spec study-configs/run-reuse-development.json --output /home/wjxt/tokenfs-run-reuse-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/run-reuse-20260929 --freeze study-configs/run-reuse-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-run-reuse-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-run-reuse-evidence/run.sh > /home/wjxt/tokenfs-run-reuse-evidence/run.log 2>&1 < /dev/null &
