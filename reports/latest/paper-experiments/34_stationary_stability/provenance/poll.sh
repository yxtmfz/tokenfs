set -eu
root=/home/wjxt/tokenfs-stationary-stability-evidence
if [ -f "$root/development.exit" ]; then cat "$root/development.exit"; fi
tail -12 "$root/run.log"
