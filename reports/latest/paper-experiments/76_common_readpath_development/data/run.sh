#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-common-readpath76-20261007
root=/home/wjxt/tokenfs-common-readpath76-evidence
python3 scripts/common_readpath_hpj_study.py run --spec study-configs/common-readpath-development.json --output "$root/development" --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/common-readpath76-20261007 --freeze study-configs/common-readpath-freeze.json
rc=$?
printf '%s\n' "$rc" > "$root/development.exit"
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
python3 scripts/disk_opportunity_correctness.py --study common_readpath_hpj_study --binary build-release/tokenfs --reference-binary /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-lazy-20260930/build-release/tokenfs --freeze study-configs/common-readpath-freeze.json --output "$root/correctness" --remote-root /srv/tokenfs/remote-cn7/common-readpath76-20261007
rc=$?
printf '%s\n' "$rc" > "$root/correctness.exit"
exit "$rc"
