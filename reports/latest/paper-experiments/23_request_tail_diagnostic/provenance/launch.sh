set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-tail-diagnostic-evidence
mkdir /srv/tokenfs/remote-cn7/tail-diagnostic-20260928
cat > /home/wjxt/tokenfs-tail-diagnostic-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-tail-diagnostic-20260928
python3 scripts/tail_diagnostic_study.py run --spec study-configs/tail-diagnostic.json --output /home/wjxt/tokenfs-tail-diagnostic-evidence/diagnostic --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/tail-diagnostic-20260928 --freeze study-configs/tail-diagnostic-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-tail-diagnostic-evidence/diagnostic.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-tail-diagnostic-evidence/run.sh > /home/wjxt/tokenfs-tail-diagnostic-evidence/run.log 2>&1 < /dev/null &
