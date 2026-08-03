#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
result_root="${1:-$project_root/reports/latest/strategy-matrix}"
base_config="$project_root/config/tokenfs.dev.yaml"

tmp_dir="$(mktemp -d /tmp/tokenfs-strategy-matrix.XXXXXX)"

cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

rm -rf "$result_root"
mkdir -p "$result_root"

make_config() {
  local name="$1"
  local promote="$2"
  local prefetch="$3"
  local output="$tmp_dir/$name.yaml"
  python3 - "$base_config" "$output" "$promote" "$prefetch" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
promote = sys.argv[3]
prefetch = sys.argv[4]

text = src.read_text(encoding="utf-8")
text = text.replace("local_quota_mib: 64", "local_quota_mib: 32")
text = text.replace("promote_on_read: false", f"promote_on_read: {promote}")
text = text.replace("prefetch_on_read: false", f"prefetch_on_read: {prefetch}")
dst.write_text(text, encoding="utf-8")
PY
  echo "$output"
}

run_case() {
  local name="$1"
  local promote="$2"
  local prefetch="$3"
  local config
  config="$(make_config "$name" "$promote" "$prefetch")"
  local out="$result_root/$name"
  echo "strategy: $name"
  TOKENFS_CONFIG="$config" \
  TOKENFS_SHARD_MIB=8 \
  TOKENFS_LARGE_SHARD_MIB=40 \
  TOKENFS_NORMAL_SHARDS=4 \
  TOKENFS_OVERFLOW_SHARDS=2 \
  TOKENFS_CHUNK_MIB=1 \
    "$project_root/scripts/token_workload_test.sh" "$out" >/dev/null
}

run_case baseline false false
run_case promote true false
run_case prefetch false true
run_case full true true

python3 - "$result_root" <<'PY'
import csv
import html
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
cases = ["baseline", "promote", "prefetch", "full"]

def metric(metrics: dict, name: str) -> int:
    return int(metrics.get(name, 0))

def workload_seconds(path: Path) -> float:
    total = 0.0
    with path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += float(row["seconds"])
    return total

rows = []
for case in cases:
    case_dir = root / case
    metrics = json.loads((case_dir / "metrics.json").read_text(encoding="utf-8"))
    read_ops = metric(metrics, "read_ops")
    write_ops = metric(metrics, "write_ops")
    row = {
        "case": case,
        "read_local_rate_pct": round(metric(metrics, "read_local_rate_x100") / 100, 2),
        "write_local_rate_pct": round(metric(metrics, "write_local_rate_x100") / 100, 2),
        "remote_read_open": metric(metrics, "remote_read_open_count"),
        "local_read_open": metric(metrics, "local_read_open_count"),
        "promote_count": metric(metrics, "promote_count"),
        "prefetch_count": metric(metrics, "prefetch_count"),
        "evict_count": metric(metrics, "evict_count"),
        "evict_skip_hot": metric(metrics, "evict_skip_hot"),
        "spill_count": metric(metrics, "spill_count"),
        "avg_read_us": round(metric(metrics, "read_latency_us_total") / read_ops, 2) if read_ops else 0,
        "avg_write_us": round(metric(metrics, "write_latency_us_total") / write_ops, 2) if write_ops else 0,
        "workload_seconds": round(workload_seconds(case_dir / "summary.csv"), 4),
    }
    rows.append(row)

with (root / "strategy_summary.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

def bar(value: float, max_value: float, width: int = 28) -> str:
    if max_value <= 0:
        return ""
    filled = max(0, min(width, round(value / max_value * width)))
    return "█" * filled + "░" * (width - filled)

max_read_rate = max(row["read_local_rate_pct"] for row in rows)
max_time = max(row["workload_seconds"] for row in rows)
max_remote_open = max(row["remote_read_open"] for row in rows)

lines = [
    "# TokenFS 策略矩阵报告",
    "",
    "本报告使用同一组 token shard workload 比较四种策略，适合作为论文预实验和消融实验框架。",
    "",
    "| 策略 | 本地读命中率 % | 远端打开读取 | 热点提升 | 顺序预取 | 本地淘汰 | 跳过热点 | 溢写 | 平均读 us | 平均写 us | workload 总耗时 s |",
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
]
for row in rows:
    lines.append(
        f"| {row['case']} | {row['read_local_rate_pct']} | {row['remote_read_open']} | "
        f"{row['promote_count']} | {row['prefetch_count']} | {row['evict_count']} | "
        f"{row['evict_skip_hot']} | {row['spill_count']} | {row['avg_read_us']} | "
        f"{row['avg_write_us']} | {row['workload_seconds']} |"
    )

lines.extend(["", "## 本地读命中率", "", "```text"])
for row in rows:
    lines.append(f"{row['case']:<10} {bar(row['read_local_rate_pct'], max_read_rate)} {row['read_local_rate_pct']}%")
lines.extend(["```", "", "## 远端打开读取次数", "", "```text"])
for row in rows:
    lines.append(f"{row['case']:<10} {bar(row['remote_read_open'], max_remote_open)} {row['remote_read_open']} 次")
lines.extend(["```", "", "## workload 总耗时", "", "```text"])
for row in rows:
    lines.append(f"{row['case']:<10} {bar(row['workload_seconds'], max_time)} {row['workload_seconds']} s")
lines.extend([
    "```",
    "",
    "## 解读",
    "",
    "- `baseline` 表示只做本地优先和远端溢写。",
    "- `promote` 表示远端文件重复读取后提升回本地。",
    "- `prefetch` 表示读取连续 shard 时提前把下一片拉回本地。",
    "- `full` 表示热点提升、顺序预取和代价驱动淘汰联合工作。",
    "- 当前开发环境没有真实 NVMe-oF SSD，因此绝对耗时不能代表最终论文结果；但命中率、溢写次数、提升次数、预取次数和淘汰次数可以验证策略逻辑是否生效。",
])
(root / "strategy_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

table_rows = "\n".join(
    "<tr>"
    f"<td><code>{html.escape(row['case'])}</code></td>"
    f"<td>{row['read_local_rate_pct']}</td>"
    f"<td>{row['remote_read_open']}</td>"
    f"<td>{row['promote_count']}</td>"
    f"<td>{row['prefetch_count']}</td>"
    f"<td>{row['evict_count']}</td>"
    f"<td>{row['avg_read_us']}</td>"
    f"<td>{row['workload_seconds']}</td>"
    "</tr>"
    for row in rows
)
html_doc = f"""<!doctype html>
<meta charset="utf-8">
<title>TokenFS Strategy Matrix</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #20242a; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #cfd8e3; padding: 8px; text-align: left; }}
th {{ background: #f4f6f8; }}
code {{ background: #f0f2f4; padding: 2px 6px; border-radius: 6px; }}
.note {{ background: #f7f9fc; border-left: 4px solid #2f6feb; padding: 12px 16px; margin: 18px 0; }}
</style>
<h1>TokenFS 策略矩阵报告</h1>
<div class="note">该报告用于比较策略是否生效，不用于给出最终真实 NVMe-oF 性能结论。</div>
<table>
<thead><tr><th>策略</th><th>本地读命中率 %</th><th>远端打开读取</th><th>热点提升</th><th>顺序预取</th><th>本地淘汰</th><th>平均读 us</th><th>总耗时 s</th></tr></thead>
<tbody>
{table_rows}
</tbody>
</table>
"""
(root / "strategy_report.html").write_text(html_doc, encoding="utf-8")
PY

echo "TokenFS strategy matrix report generated:"
echo "  $result_root/strategy_report.md"
echo "  $result_root/strategy_report.html"
echo "  $result_root/strategy_summary.csv"
