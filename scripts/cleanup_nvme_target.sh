#!/usr/bin/env bash
set -euo pipefail

subnqn="${TOKENFS_TARGET_SUBNQN:-nqn.2026-07.local.tokenfs:remote0}"
image="${TOKENFS_TARGET_IMAGE:-/var/lib/tokenfs/nvmeof-target/remote0.img}"
remove_image=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subnqn)
      subnqn="$2"
      shift 2
      ;;
    --image)
      image="$2"
      shift 2
      ;;
    --remove-image)
      remove_image=1
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--subnqn nqn] [--image path] [--remove-image]"
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

port="/sys/kernel/config/nvmet/ports/1"
subsys="/sys/kernel/config/nvmet/subsystems/$subnqn"

echo "Cleaning NVMe/TCP target $subnqn"

if [[ -L "$port/subsystems/$subnqn" ]]; then
  sudo rm -f "$port/subsystems/$subnqn"
fi

if [[ -d "$subsys/namespaces/1" ]]; then
  echo 0 | sudo tee "$subsys/namespaces/1/enable" >/dev/null 2>&1 || true
fi

if [[ -d "$subsys" ]]; then
  sudo find "$subsys/allowed_hosts" -mindepth 1 -maxdepth 1 -type l -delete 2>/dev/null || true
  sudo rmdir "$subsys/namespaces/1" 2>/dev/null || true
  sudo rmdir "$subsys" 2>/dev/null || true
fi

if [[ -d "$port" ]]; then
  sudo rmdir "$port" 2>/dev/null || true
fi

loopdev="$(sudo losetup -j "$image" | awk -F: 'NR==1 {print $1}')"
if [[ -n "$loopdev" ]]; then
  sudo losetup -d "$loopdev" || true
fi

if [[ "$remove_image" -eq 1 ]]; then
  sudo rm -f "$image"
fi

echo "NVMe/TCP target cleanup finished."
