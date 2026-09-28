set -eu
root=/home/wjxt/tokenfs-planning-efficiency-evidence
if [ -f "$root/development.exit" ]; then cat "$root/development.exit"; fi
tail -12 "$root/run.log"
