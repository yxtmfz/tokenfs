set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
cd /home/wjxt/projects/tokenfs-integrated-hpj-readpath-reverse-20260929
python3 scripts/integrated_hpj_correctness.py --study integrated_hpj_readpath_reverse_study --binary build-release/tokenfs --freeze study-configs/integrated-hpj-readpath-reverse-freeze.json --output /home/wjxt/tokenfs-integrated-hpj-readpath-reverse-evidence/correctness --remote-root /srv/tokenfs/remote-cn7/integrated-hpj-readpath-reverse-20260929
