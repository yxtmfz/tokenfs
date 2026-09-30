set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
mkdir /home/wjxt/tokenfs-integrated-hpj-cohort-caller-support-evidence
mkdir /srv/tokenfs/remote-cn7/integrated-hpj-cohort-caller-support-20260930
cat > /home/wjxt/tokenfs-integrated-hpj-cohort-caller-support-evidence/run.sh <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-support-20260930
python3 scripts/integrated_hpj_cohort_caller_support_study.py run --spec study-configs/integrated-hpj-cohort-caller-support-development.json --output /home/wjxt/tokenfs-integrated-hpj-cohort-caller-support-evidence/development --binary build-release/tokenfs --reference-binary /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-lazy-20260930/build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/integrated-hpj-cohort-caller-support-20260930 --freeze study-configs/integrated-hpj-cohort-caller-support-freeze.json
rc=$?
printf '%s\n' "$rc" > /home/wjxt/tokenfs-integrated-hpj-cohort-caller-support-evidence/development.exit
exit "$rc"
RUN
nohup bash /home/wjxt/tokenfs-integrated-hpj-cohort-caller-support-evidence/run.sh > /home/wjxt/tokenfs-integrated-hpj-cohort-caller-support-evidence/run.log 2>&1 < /dev/null &
