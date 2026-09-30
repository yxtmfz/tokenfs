#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-disk-opportunity74-20260930
root=/home/wjxt/tokenfs-disk-opportunity74-evidence
python3 scripts/integrated_hpj_disk_opportunity_study.py run --spec study-configs/disk-opportunity-development.json --output "$root/development" --binary build-release/tokenfs --reference-binary /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-lazy-20260930/build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/disk-opportunity74-20260930 --freeze study-configs/disk-opportunity-freeze.json
rc=$?
printf '%s\n' "$rc" > "$root/development.exit"
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
python3 scripts/disk_opportunity_correctness.py --binary build-release/tokenfs --reference-binary /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-lazy-20260930/build-release/tokenfs --freeze study-configs/disk-opportunity-freeze.json --output "$root/correctness" --remote-root /srv/tokenfs/remote-cn7/disk-opportunity74-20260930
rc=$?
printf '%s\n' "$rc" > "$root/correctness.exit"
exit "$rc"
