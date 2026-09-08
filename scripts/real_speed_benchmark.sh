#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
result_root="${1:-$project_root/reports/latest/paper-experiments/06_real_speed_benchmark}"
matrix_dir="$result_root/strategy-matrix"
config="${TOKENFS_CONFIG:-$project_root/config/tokenfs.dev.yaml}"
backend_id="${TOKENFS_BACKEND_ID:-remote0}"
require_nvmeof="${TOKENFS_REQUIRE_NVMEOF:-1}"
environment="${TOKENFS_REAL_SPEED_ENV:-}"

read_backend_value() {
  local key="$1"
  python3 - "$config" "$backend_id" "$key" <<'PY'
import sys
from pathlib import Path

config = Path(sys.argv[1])
backend_id = sys.argv[2]
key = sys.argv[3]
section = ""
current = None
found = {}

def clean(value):
    return value.strip().strip('"').strip("'")

for raw in config.read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].rstrip()
    if not line.strip():
        continue
    if not line.startswith(" ") and line.endswith(":"):
        section = line[:-1]
        current = None
        continue
    stripped = line.strip()
    if section == "backends" and stripped.startswith("- "):
        if found.get("id") == backend_id:
            break
        current = {}
        found = current
        stripped = stripped[2:].strip()
    if current is None or ":" not in stripped:
        continue
    k, v = stripped.split(":", 1)
    current[k.strip()] = clean(v)

if found.get("id") != backend_id:
    found = {}
print(found.get(key, ""))
PY
}

fail_nvmeof_check() {
  cat >&2 <<EOF
真实速度实验已停止：远端后端没有通过 NVMe-oF 挂载检查。

论文级真实速度实验必须满足：
  1. 配置文件中的 backends[].type = nvmeof
  2. backends[].root 指向 NVMe-oF 挂载目录，例如 /srv/tokenfs/remote0
  3. 该目录必须已经挂载，且挂载源应为 /dev/nvme...

推荐流程：
  cp config/tokenfs.nvmeof.example.yaml config/tokenfs.nvmeof.yaml
  编辑 config/tokenfs.nvmeof.yaml，填入真实 target_ip、subnqn、device
  sudo ./scripts/connect_nvme.sh --config config/tokenfs.nvmeof.yaml --backend $backend_id --chown-current
  TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/real_speed_benchmark.sh

如果只是开发自测，可显式绕过：
  TOKENFS_REQUIRE_NVMEOF=0 ./scripts/real_speed_benchmark.sh

但绕过结果不能写成真实 NVMe-oF 端到端性能。
EOF
  exit 2
}

write_mount_evidence() {
  local evidence="$result_root/nvmeof_mount_evidence.txt"
  mkdir -p "$result_root"
  {
    echo "time=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "config=$config"
    echo "backend=$backend_id"
    echo
    echo "[findmnt]"
    findmnt -rn --target "$verified_root" || true
    echo
    echo "[findmnt verbose]"
    findmnt --target "$verified_root" || true
    echo
    echo "[lsblk]"
    lsblk || true
    echo
    echo "[nvme list]"
    if command -v nvme >/dev/null 2>&1; then
      nvme list || true
    else
      echo "nvme command not found"
    fi
  } > "$evidence"
}

verify_nvmeof_mount() {
  local backend_type root nvme_mount device source fstype
  backend_type="$(read_backend_value type)"
  root="$(read_backend_value root)"
  nvme_mount="$(read_backend_value nvme_mount)"
  device="${TOKENFS_NVME_DEVICE:-$(read_backend_value nvme_device)}"
  verified_root="${TOKENFS_REMOTE_ROOT:-${root:-$nvme_mount}}"
  verified_mount="${TOKENFS_NVME_MOUNT:-${nvme_mount:-$verified_root}}"

  if [[ "$require_nvmeof" != "1" ]]; then
    environment="${environment:-TokenFS FUSE workload, NVMe-oF check bypassed}"
    return
  fi

  [[ "$backend_type" == "nvmeof" ]] || fail_nvmeof_check
  [[ -n "$verified_root" && -n "$verified_mount" ]] || fail_nvmeof_check
  [[ "$verified_root" == "$verified_mount" ]] || fail_nvmeof_check
  command -v findmnt >/dev/null 2>&1 || fail_nvmeof_check
  findmnt -rn --target "$verified_root" >/dev/null || fail_nvmeof_check

  source="$(findmnt -rn -o SOURCE --target "$verified_root" | head -n 1)"
  fstype="$(findmnt -rn -o FSTYPE --target "$verified_root" | head -n 1)"
  [[ "$source" == /dev/nvme* ]] || fail_nvmeof_check
  if [[ -n "$device" && "$device" != "/dev/nvmeXnY" && "$source" != "$device" ]]; then
    echo "配置中的 nvme_device=$device，但实际挂载源是 $source。" >&2
    fail_nvmeof_check
  fi

  environment="${environment:-TokenFS FUSE workload with verified NVMe-oF mount: $source -> $verified_root ($fstype)}"
  write_mount_evidence
  echo "NVMe-oF mount verified: $source -> $verified_root ($fstype)"
}

verify_nvmeof_mount

TOKENFS_CONFIG="$config" \
TOKENFS_BACKEND_ID="$backend_id" \
  "$project_root/scripts/strategy_matrix_test.sh" "$matrix_dir"

python3 "$project_root/scripts/real_speed_report.py" \
  "$matrix_dir" \
  "$result_root" \
  --environment "$environment"

echo "TokenFS real speed benchmark generated:"
echo "  $result_root/real_speed_report.md"
echo "  $result_root/real_speed_summary.csv"
echo "  $result_root/figures/real_wall_time.svg"
echo "  $result_root/figures/real_speedup_vs_baseline.svg"
echo "  $result_root/figures/real_effective_throughput.svg"
echo "  $result_root/nvmeof_mount_evidence.txt"
