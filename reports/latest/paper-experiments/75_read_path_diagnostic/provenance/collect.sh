set -eu
root=/home/wjxt/tokenfs-read-tail75-evidence
project=/home/wjxt/projects/tokenfs-read-tail75-20261007
test "$(cat "$root/development.exit")" = 0
test "$(cat "$root/correctness.exit")" = 0
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Own TokenFS process still active'; exit 2; fi
mkdir -p "$root/provenance"
cp "$project/study-configs/read-tail-freeze.json" "$root/provenance/freeze.json"
tar -czf /home/wjxt/tokenfs-read-tail75-evidence.tar.gz -C "$root" .
sha256sum /home/wjxt/tokenfs-read-tail75-evidence.tar.gz
