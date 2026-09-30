set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
cd /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-support-20260930
python3 scripts/hotspot_freshness_correctness.py --study integrated_hpj_cohort_caller_support_study --binary build-release/tokenfs --reference-binary /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-lazy-20260930/build-release/tokenfs --freeze study-configs/integrated-hpj-cohort-caller-support-freeze.json --output /home/wjxt/tokenfs-integrated-hpj-cohort-caller-support-evidence/correctness --remote-root /srv/tokenfs/remote-cn7/integrated-hpj-cohort-caller-support-20260930
