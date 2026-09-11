#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  sudo ./scripts/nvmeof_net_profile.sh apply <dev> <profile>
  sudo ./scripts/nvmeof_net_profile.sh clear <dev>

Profiles:
  mild        delay 0.2ms,  2gbit
  campus     delay 0.6ms,  1gbit
  congested  delay 1.5ms, 500mbit

This script shapes the NVMe/TCP path with Linux tc/netem/tbf. Use it only on
the test NIC of the NVMe-oF target/client VM, never on a production interface.
EOF
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

action="$1"
dev="$2"
profile="${3:-mild}"

if [[ "$EUID" -ne 0 ]]; then
  echo "Please run with sudo." >&2
  exit 1
fi

case "$action" in
  clear)
    tc qdisc del dev "$dev" root 2>/dev/null || true
    echo "cleared network profile on $dev"
    ;;
  apply)
    case "$profile" in
      mild)
        delay="0.2ms"
        rate="2gbit"
        ;;
      campus)
        delay="0.6ms"
        rate="1gbit"
        ;;
      congested)
        delay="1.5ms"
        rate="500mbit"
        ;;
      *)
        usage
        exit 1
        ;;
    esac
    tc qdisc del dev "$dev" root 2>/dev/null || true
    tc qdisc add dev "$dev" root handle 1: netem delay "$delay"
    tc qdisc add dev "$dev" parent 1: handle 10: tbf rate "$rate" burst 8mb latency 50ms
    echo "applied $profile profile on $dev: delay=$delay rate=$rate"
    ;;
  *)
    usage
    exit 1
    ;;
esac
