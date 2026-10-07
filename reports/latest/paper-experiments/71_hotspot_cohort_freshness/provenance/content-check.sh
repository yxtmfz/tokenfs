set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
cd /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-freshness-20260930
mkdir /srv/tokenfs/remote-cn7/integrated-hpj-cohort-caller-freshness-20260930/content-v2
python3 scripts/hotspot_freshness_correctness_v2.py --binary build-release/tokenfs --reference-binary /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-lazy-20260930/build-release/tokenfs --freeze study-configs/integrated-hpj-cohort-caller-freshness-freeze.json --output /home/wjxt/tokenfs-integrated-hpj-cohort-caller-freshness-evidence/correctness-v2 --remote-root /srv/tokenfs/remote-cn7/integrated-hpj-cohort-caller-freshness-20260930/content-v2
