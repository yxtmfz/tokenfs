#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python3 -m unittest tests.aura_kv_unit_test
python3 scripts/aura_kv_sim.py --output reports/latest/aura-kv-sim-smoke \
  --scenario cluster_shared --scenario hotspot_shift \
  --policy RemoteOnly --policy NodeLRU --policy AlternativeAwareNoLearning --policy AURA-KV

test -f reports/latest/aura-kv-sim-smoke/aura_sim_report.md
grep -q "SIMULATED RESULT" reports/latest/aura-kv-sim-smoke/aura_sim_report.md

echo "AURA-KV unit and simulator smoke tests passed."

