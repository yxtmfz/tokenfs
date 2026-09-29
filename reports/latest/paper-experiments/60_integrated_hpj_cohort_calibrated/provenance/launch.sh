set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-integrated-hpj-cohort-calibrated-evidence
mkdir /srv/tokenfs/remote-cn7/integrated-hpj-cohort-calibrated-20260929
cat > /home/wjxt/tokenfs-integrated-hpj-cohort-calibrated-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-integrated-hpj-cohort-calibrated-20260929
python3 scripts/integrated_hpj_cohort_calibrated_study.py run --spec study-configs/integrated-hpj-cohort-calibrated-development.json --output /home/wjxt/tokenfs-integrated-hpj-cohort-calibrated-evidence/development --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/integrated-hpj-cohort-calibrated-20260929 --freeze study-configs/integrated-hpj-cohort-calibrated-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-integrated-hpj-cohort-calibrated-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-integrated-hpj-cohort-calibrated-evidence/run.sh > /home/wjxt/tokenfs-integrated-hpj-cohort-calibrated-evidence/run.log 2>&1 < /dev/null &
