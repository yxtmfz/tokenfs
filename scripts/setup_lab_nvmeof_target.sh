#!/usr/bin/env bash
set -euo pipefail

target_ip="${AURA_LAB_TARGET_IP:-}"
target_port="${AURA_LAB_TARGET_PORT:-4420}"
subnqn="${AURA_LAB_TARGET_SUBNQN:-nqn.2026-09.local.aura-kv:remote0}"
image="${AURA_LAB_BACKING_FILE:-}"
port_id="${AURA_LAB_PORT_ID:-1}"
nsid="${AURA_LAB_NSID:-1}"
serial="${AURA_LAB_SERIAL:-AURAKV0001}"
allowed_host_nqn="${AURA_LAB_ALLOWED_HOST_NQN:-}"
allowed_host_nqns="${AURA_LAB_ALLOWED_HOST_NQNS:-}"
allow_any_host="${AURA_LAB_ALLOW_ANY_HOST:-0}"
apply="${AURA_APPLY:-0}"

usage() {
  cat <<EOF
Usage:
  AURA_APPLY=1 AURA_LAB_ALLOWED_HOST_NQN=<client-host-nqn> $0
  AURA_APPLY=1 AURA_LAB_ALLOWED_HOST_NQNS="<nqn1>,<nqn2>" $0

Purpose:
  Configure a lab server as an NVMe/TCP Target backed by an existing file.
  The file is attached to a loop device first, so nvmet sees a block device.

Defaults:
  target_ip=$target_ip
  target_port=$target_port
  subnqn=$subnqn
  image=$image

Safety:
  - This script does not format any disk.
  - This script does not create the backing file.
  - This script refuses to apply unless AURA_APPLY=1 is set.
  - By default it requires AURA_LAB_ALLOWED_HOST_NQN or AURA_LAB_ALLOWED_HOST_NQNS.
  - To intentionally allow any host, set AURA_LAB_ALLOW_ANY_HOST=1.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "$target_ip" || -z "$image" ]]; then
  cat >&2 <<'EOF'
AURA_LAB_TARGET_IP and AURA_LAB_BACKING_FILE are required.

Example:
  AURA_LAB_TARGET_IP=<LAB_STORAGE_PRIVATE_IP> \
  AURA_LAB_BACKING_FILE=/path/to/aura-remote0.img \
  ./scripts/setup_lab_nvmeof_target.sh
EOF
  exit 2
fi

cat <<EOF
Lab NVMe/TCP Target plan
------------------------
listen:       $target_ip:$target_port
subnqn:       $subnqn
namespace:    $nsid
backing file: $image
serial:       $serial
allowed host: ${allowed_host_nqn:-<not set>}
allowed hosts: ${allowed_host_nqns:-<not set>}
allow any:    $allow_any_host
apply:        $apply
EOF

if [[ "$apply" != "1" ]]; then
  echo
  echo "Dry-run only. Set AURA_APPLY=1 to configure the Target."
  exit 0
fi

if [[ ! -f "$image" ]]; then
  echo "backing file does not exist: $image" >&2
  exit 1
fi

if [[ "$allow_any_host" != "1" && -z "$allowed_host_nqn" && -z "$allowed_host_nqns" ]]; then
  echo "AURA_LAB_ALLOWED_HOST_NQN or AURA_LAB_ALLOWED_HOST_NQNS is required unless AURA_LAB_ALLOW_ANY_HOST=1." >&2
  exit 1
fi

sudo modprobe nvmet
sudo modprobe nvmet-tcp

if ! mountpoint -q /sys/kernel/config; then
  sudo mount -t configfs none /sys/kernel/config
fi

base="/sys/kernel/config/nvmet"
subsys="$base/subsystems/$subnqn"
port="$base/ports/$port_id"
namespace="$subsys/namespaces/$nsid"

loopdev="$(sudo losetup -j "$image" | awk -F: 'NR==1 {print $1}')"
if [[ -z "$loopdev" ]]; then
  loopdev="$(sudo losetup --find --show "$image")"
fi

sudo mkdir -p "$namespace"
if [[ -f "$namespace/enable" ]]; then
  echo 0 | sudo tee "$namespace/enable" >/dev/null || true
fi

echo "$serial" | sudo tee "$subsys/attr_serial" >/dev/null
echo -n "$loopdev" | sudo tee "$namespace/device_path" >/dev/null
echo 1 | sudo tee "$namespace/enable" >/dev/null

if [[ "$allow_any_host" == "1" ]]; then
  echo 1 | sudo tee "$subsys/attr_allow_any_host" >/dev/null
else
  echo 0 | sudo tee "$subsys/attr_allow_any_host" >/dev/null
  host_list="$allowed_host_nqn"
  if [[ -n "$allowed_host_nqns" ]]; then
    host_list="$host_list ${allowed_host_nqns//,/ }"
  fi
  for host_nqn in $host_list; do
    [[ -n "$host_nqn" ]] || continue
    sudo mkdir -p "$base/hosts/$host_nqn"
    sudo ln -s "$base/hosts/$host_nqn" \
      "$subsys/allowed_hosts/$host_nqn" 2>/dev/null || true
  done
fi

sudo mkdir -p "$port/subsystems"
echo "$target_ip" | sudo tee "$port/addr_traddr" >/dev/null
echo "$target_port" | sudo tee "$port/addr_trsvcid" >/dev/null
echo tcp | sudo tee "$port/addr_trtype" >/dev/null
echo ipv4 | sudo tee "$port/addr_adrfam" >/dev/null
sudo ln -s "$subsys" "$port/subsystems/$subnqn" 2>/dev/null || true

echo "NVMe/TCP Target configured: $target_ip:$target_port $subnqn via $loopdev"
