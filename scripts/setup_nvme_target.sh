#!/usr/bin/env bash
set -euo pipefail

target_ip="${TOKENFS_TARGET_IP:-0.0.0.0}"
target_port="${TOKENFS_TARGET_PORT:-4420}"
subnqn="${TOKENFS_TARGET_SUBNQN:-nqn.2026-07.local.tokenfs:remote0}"
hostnqn="${TOKENFS_TARGET_ALLOWED_HOST_NQN:-}"
image="${TOKENFS_TARGET_IMAGE:-/var/lib/tokenfs/nvmeof-target/remote0.img}"
size="${TOKENFS_TARGET_SIZE:-2G}"
serial="${TOKENFS_TARGET_SERIAL:-TOKENFS0001}"

usage() {
  cat <<EOF
Usage: $0 [--target-ip ip] [--port port] [--subnqn nqn] [--image path] [--size size]

Environment variables:
  TOKENFS_TARGET_IP=0.0.0.0
  TOKENFS_TARGET_PORT=4420
  TOKENFS_TARGET_SUBNQN=nqn.2026-07.local.tokenfs:remote0
  TOKENFS_TARGET_ALLOWED_HOST_NQN=<optional host nqn>
  TOKENFS_TARGET_IMAGE=/var/lib/tokenfs/nvmeof-target/remote0.img
  TOKENFS_TARGET_SIZE=2G

This script creates a Linux kernel NVMe/TCP target backed by a loop file.
It does not format the client-side NVMe namespace.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-ip)
      target_ip="$2"
      shift 2
      ;;
    --port)
      target_port="$2"
      shift 2
      ;;
    --subnqn)
      subnqn="$2"
      shift 2
      ;;
    --image)
      image="$2"
      shift 2
      ;;
    --size)
      size="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

run_root() {
  sudo "$@"
}

echo "Setting up Linux NVMe/TCP target"
echo "subnqn=$subnqn"
echo "listen=$target_ip:$target_port"
echo "image=$image"

run_root modprobe nvmet
run_root modprobe nvmet-tcp
run_root modprobe loop

if ! mountpoint -q /sys/kernel/config; then
  run_root mount -t configfs none /sys/kernel/config
fi

run_root mkdir -p "$(dirname "$image")"
if [[ ! -f "$image" ]]; then
  run_root truncate -s "$size" "$image"
fi

loopdev="$(sudo losetup -j "$image" | awk -F: 'NR==1 {print $1}')"
if [[ -z "$loopdev" ]]; then
  loopdev="$(sudo losetup --find --show "$image")"
fi

subsys="/sys/kernel/config/nvmet/subsystems/$subnqn"
port="/sys/kernel/config/nvmet/ports/1"

run_root mkdir -p "$subsys/namespaces/1"
echo 1 | sudo tee "$subsys/attr_allow_any_host" >/dev/null
echo "$serial" | sudo tee "$subsys/attr_serial" >/dev/null
echo "$loopdev" | sudo tee "$subsys/namespaces/1/device_path" >/dev/null
echo 1 | sudo tee "$subsys/namespaces/1/enable" >/dev/null

if [[ -n "$hostnqn" ]]; then
  echo 0 | sudo tee "$subsys/attr_allow_any_host" >/dev/null
  run_root mkdir -p "/sys/kernel/config/nvmet/hosts/$hostnqn"
  run_root ln -s "/sys/kernel/config/nvmet/hosts/$hostnqn" "$subsys/allowed_hosts/$hostnqn" 2>/dev/null || true
fi

run_root mkdir -p "$port"
echo "$target_ip" | sudo tee "$port/addr_traddr" >/dev/null
echo "$target_port" | sudo tee "$port/addr_trsvcid" >/dev/null
echo tcp | sudo tee "$port/addr_trtype" >/dev/null
echo ipv4 | sudo tee "$port/addr_adrfam" >/dev/null
run_root ln -s "$subsys" "$port/subsystems/$subnqn" 2>/dev/null || true

echo "NVMe/TCP target is ready."
echo "loopdev=$loopdev"
echo "subnqn=$subnqn"
echo "target=$target_ip:$target_port"
