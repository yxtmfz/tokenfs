#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
result_root="${1:-$project_root/reports/latest/paper-experiments/06_real_speed_benchmark}"
matrix_dir="$result_root/strategy-matrix"
environment="${TOKENFS_REAL_SPEED_ENV:-TokenFS FUSE workload}"

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
