set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-read-fill-evidence
mkdir /srv/tokenfs/remote-cn7/read-fill-20260928
cat > /home/wjxt/tokenfs-read-fill-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-read-fill-20260928
python3 scripts/read_fill_study.py run --spec study-configs/read-fill-development.json --output /home/wjxt/tokenfs-read-fill-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/read-fill-20260928 --freeze study-configs/read-fill-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-read-fill-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-read-fill-evidence/run.sh > /home/wjxt/tokenfs-read-fill-evidence/run.log 2>&1 < /dev/null &
