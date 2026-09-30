set -eu
root=/home/wjxt/tokenfs-integrated-hpj-cohort-caller-final-evidence
if [ -f "$root/confirmation.exit" ]; then cat "$root/confirmation.exit"; fi
tail -12 "$root/run.log"
