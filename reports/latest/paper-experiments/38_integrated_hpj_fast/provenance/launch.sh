set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-integrated-hpj-fast-evidence
mkdir /srv/tokenfs/remote-cn7/integrated-hpj-fast-20260929
cat > /home/wjxt/tokenfs-integrated-hpj-fast-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-integrated-hpj-fast-20260929
python3 scripts/integrated_hpj_fast_study.py run --spec study-configs/integrated-hpj-fast-development.json --output /home/wjxt/tokenfs-integrated-hpj-fast-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/integrated-hpj-fast-20260929 --freeze study-configs/integrated-hpj-fast-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-integrated-hpj-fast-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-integrated-hpj-fast-evidence/run.sh > /home/wjxt/tokenfs-integrated-hpj-fast-evidence/run.log 2>&1 < /dev/null &
