set -eu
hostname
cat /proc/loadavg
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'own TokenFS active'; exit 2; fi
findmnt -T /srv/tokenfs/remote-cn7
ls /home/wjxt/aura-kv-tools/env.sh
