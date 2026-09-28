set -eu
root=/home/wjxt/tokenfs-readiness-diagnostic-evidence
cat "$root/diagnostic.exit"
tail -25 "$root/run.log"
