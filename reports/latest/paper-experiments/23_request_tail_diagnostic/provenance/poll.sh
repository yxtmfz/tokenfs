set -eu
root=/home/wjxt/tokenfs-tail-diagnostic-evidence
if [ -f "$root/diagnostic.exit" ]; then cat "$root/diagnostic.exit"; fi
tail -12 "$root/run.log"
