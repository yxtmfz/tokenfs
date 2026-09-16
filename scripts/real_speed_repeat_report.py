#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from statistics import mean, stdev
from xml.sax.saxutils import escape


CASE_ORDER = [
    "RemoteOnly",
    "LocalFirst",
    "LRU-Local",
    "LFU-Local",
    "LRU-ReadThrough",
    "LFU-ReadThrough",
    "AURA-no-prefetch",
    "AURA-no-xgpu",
    "AURA-Joint",
]
NUMERIC_FIELDS = [
    "total_mib",
    "wall_time_s",
    "effective_mib_s",
    "speedup_vs_baseline",
    "read_mib_s",
    "read_speedup_vs_baseline",
    "steady_reuse_mib_s",
    "steady_reuse_vs_baseline",
    "avg_read_us",
    "local_read_hit_rate_pct",
    "remote_read_open",
    "remote_open_reduction_pct",
    "promote_count",
    "prefetch_request_count",
    "prefetch_count",
    "evict_count",
    "spill_count",
    "cross_gpu_replica_create_count",
    "cross_gpu_local_replica_hit",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate repeated real NVMe-oF TokenFS benchmark runs."
    )
    parser.add_argument("repeat_root", help="Directory containing runs/run-XX outputs.")
    parser.add_argument("--label", default="", help="Human-readable workload label.")
    return parser.parse_args()


def as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize(values: list[float]) -> tuple[float, float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0, 0.0
    return mean(values), stdev(values) if len(values) > 1 else 0.0, min(values), max(values)


def load_runs(root: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    run_rows: list[dict[str, object]] = []
    for run_dir in sorted((root / "runs").glob("run-*")):
        summary = run_dir / "real_speed_summary.csv"
        if not summary.exists():
            continue
        for row in read_csv(summary):
            out: dict[str, object] = {"run": run_dir.name, "case": row.get("case", "")}
            for field in NUMERIC_FIELDS:
                out[field] = as_float(row.get(field))
            run_rows.append(out)

    summary_rows: list[dict[str, object]] = []
    for case in CASE_ORDER:
        rows = [row for row in run_rows if row["case"] == case]
        if not rows:
            continue
        out: dict[str, object] = {"case": case, "runs": len(rows)}
        for field in NUMERIC_FIELDS:
            avg, sd, lo, hi = summarize([as_float(row[field]) for row in rows])
            out[f"{field}_mean"] = round(avg, 4)
            out[f"{field}_std"] = round(sd, 4)
            out[f"{field}_min"] = round(lo, 4)
            out[f"{field}_max"] = round(hi, 4)
        summary_rows.append(out)
    return run_rows, summary_rows


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: object, digits: int = 2) -> str:
    val = as_float(value)
    if math.isclose(val, round(val)):
        return str(int(round(val)))
    return f"{val:.{digits}f}"


def svg_bar_with_range(
    path: Path,
    title: str,
    rows: list[dict[str, object]],
    key: str,
    unit: str,
    higher_is_better: bool,
) -> None:
    width = 1220
    left = 190
    right = 190
    top = 82
    row_h = 48
    height = top + len(rows) * row_h + 50
    max_value = max((as_float(row[f"{key}_max"]) for row in rows), default=1.0)
    max_bar_w = width - left - right
    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        "<rect width='100%' height='100%' fill='#fff'/>",
        f"<text x='24' y='42' font-family='Arial, Helvetica, sans-serif' font-size='26' font-weight='700' fill='#20242b'>{escape(title)}</text>",
        f"<text x='{width - 24}' y='42' text-anchor='end' font-family='Arial, Helvetica, sans-serif' font-size='16' fill='#64748b'>{'越高越好' if higher_is_better else '越低越好'}，红线为 min-max</text>",
        f"<line x1='24' y1='62' x2='{width - 24}' y2='62' stroke='#d8dee8'/>",
    ]
    for idx, row in enumerate(rows):
        y = top + idx * row_h
        case = str(row["case"])
        avg = as_float(row[f"{key}_mean"])
        lo = as_float(row[f"{key}_min"])
        hi = as_float(row[f"{key}_max"])
        bar_w = int(max_bar_w * avg / max_value) if max_value else 0
        lo_x = left + int(max_bar_w * lo / max_value) if max_value else left
        hi_x = left + int(max_bar_w * hi / max_value) if max_value else left
        color = "#2563eb" if case == "AURA-Joint" else "#64748b"
        if case == "RemoteOnly":
            color = "#111827"
        parts.extend(
            [
                f"<text x='24' y='{y + 22}' font-family='Menlo, Consolas, monospace' font-size='17' fill='#20242b'>{escape(case)}</text>",
                f"<rect x='{left}' y='{y}' width='{max_bar_w}' height='26' rx='5' fill='#eef2f7'/>",
                f"<rect x='{left}' y='{y}' width='{bar_w}' height='26' rx='5' fill='{color}'/>",
                f"<line x1='{lo_x}' y1='{y + 35}' x2='{hi_x}' y2='{y + 35}' stroke='#ef4444' stroke-width='3'/>",
                f"<line x1='{lo_x}' y1='{y + 30}' x2='{lo_x}' y2='{y + 40}' stroke='#ef4444' stroke-width='3'/>",
                f"<line x1='{hi_x}' y1='{y + 30}' x2='{hi_x}' y2='{y + 40}' stroke='#ef4444' stroke-width='3'/>",
                f"<text x='{left + max_bar_w + 18}' y='{y + 22}' font-family='Arial, Helvetica, sans-serif' font-size='17' fill='#20242b'>{avg:.2f}{escape(unit)}</text>",
            ]
        )
    parts.append("</svg>\n")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_report(root: Path, rows: list[dict[str, object]], label: str) -> None:
    aura = next((row for row in rows if row["case"] == "AURA-Joint"), None)
    remote = next((row for row in rows if row["case"] == "RemoteOnly"), None)
    fastest = min(rows, key=lambda row: as_float(row["wall_time_s_mean"])) if rows else None
    lines = [
        "# 真实 NVMe-oF 多轮速度实验汇总",
        "",
        f"实验规模：{label or '未标注'}。",
        "",
        "本报告把同一套真实 TokenFS workload 在 NVMe-oF 挂载目录上重复运行多次，并汇总均值、标准差和最小/最大范围。它用于回答 AURA-Joint 的速度收益是否稳定，而不是只依赖一次运行结果。",
        "",
        "所有策略使用同一访问形状：远端 canonical KV Cache、本地冷缓存占满、容量压力、热点复用、连续 shard 访问和跨 GPU 共享读取。与单轮验证相比，本实验只放大 shard 规模并重复采样，不额外构造只适合 AURA 的极端 trace。",
        "",
        "实验默认控制 Linux page cache：清缓存动作记录为证据，但不计入策略读写耗时。这样可以避免 RemoteOnly 的重复读取被内存缓存伪装成本地速度。",
        "",
        "## 均值结果",
        "",
        "| 策略 | 轮数 | 总数据 MiB | 总耗时均值 s | 耗时范围 s | 总吞吐均值 MiB/s | 加速比均值 | 读吞吐均值 MiB/s | 本地读命中率均值 | 远端打开读取均值 | 后台动作均值 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        actions = (
            f"promote={fmt(row['promote_count_mean'])}, "
            f"prefetch={fmt(row['prefetch_count_mean'])}, "
            f"evict={fmt(row['evict_count_mean'])}, "
            f"xgpu_hit={fmt(row['cross_gpu_local_replica_hit_mean'])}"
        )
        lines.append(
            f"| `{row['case']}` | {row['runs']} | {fmt(row['total_mib_mean'])} | "
            f"{fmt(row['wall_time_s_mean'])} | {fmt(row['wall_time_s_min'])}-{fmt(row['wall_time_s_max'])} | "
            f"{fmt(row['effective_mib_s_mean'])} | {fmt(row['speedup_vs_baseline_mean'], 3)}x | "
            f"{fmt(row['read_mib_s_mean'])} | {fmt(row['local_read_hit_rate_pct_mean'])}% | "
            f"{fmt(row['remote_read_open_mean'])} | {actions} |"
        )

    lines.extend(
        [
            "",
            "## 图表",
            "",
            "![多轮总耗时](figures/repeat_wall_time_mean.svg)",
            "",
            "![多轮总吞吐](figures/repeat_effective_throughput_mean.svg)",
            "",
            "![多轮加速比](figures/repeat_speedup_mean.svg)",
            "",
            "## 结论提示",
            "",
        ]
    )
    if aura and remote:
        lines.append(
            f"- AURA-Joint 平均端到端加速比为 `{fmt(aura['speedup_vs_baseline_mean'], 3)}x`，范围 `{fmt(aura['speedup_vs_baseline_min'], 3)}x-{fmt(aura['speedup_vs_baseline_max'], 3)}x`。"
        )
        lines.append(
            f"- AURA-Joint 平均远端打开读取为 `{fmt(aura['remote_read_open_mean'])}` 次，RemoteOnly 为 `{fmt(remote['remote_read_open_mean'])}` 次，说明本地副本和后台动作确实减少了远端访问。"
        )
    if aura and fastest:
        if fastest["case"] == "AURA-Joint":
            lines.append("- AURA-Joint 是本轮多次重复实验中平均总耗时最低的策略。")
        else:
            lines.append(
                f"- 当前环境中平均总耗时最低的是 `{fastest['case']}`，不是 AURA-Joint；这说明当前双 VM NVMe-oF 环境更适合证明机制和远端访问减少，暂时不能直接声称 AURA 端到端速度显著领先所有 baseline。"
            )
    lines.extend(
        [
            "- 如果均值提升但波动较大，论文中应同时报告标准差或 min-max，而不是只放最好的一轮。",
            "- 如果未来换成真实物理 GPU 服务器，只需要保持同一脚本和同一策略参数重新运行，即可得到可横向比较的数据。",
        ]
    )
    (root / "repeat_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.repeat_root)
    run_rows, summary_rows = load_runs(root)
    write_rows(root / "repeat_runs.csv", run_rows)
    write_rows(root / "repeat_summary.csv", summary_rows)
    figures = root / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    svg_bar_with_range(figures / "repeat_wall_time_mean.svg", "Repeated real wall-clock time", summary_rows, "wall_time_s", "s", False)
    svg_bar_with_range(figures / "repeat_effective_throughput_mean.svg", "Repeated real effective throughput", summary_rows, "effective_mib_s", "MiB/s", True)
    svg_bar_with_range(figures / "repeat_speedup_mean.svg", "Repeated real speedup over RemoteOnly", summary_rows, "speedup_vs_baseline", "x", True)
    write_report(root, summary_rows, args.label)
    print(f"repeat summary: {root / 'repeat_summary.csv'}")
    print(f"repeat report:  {root / 'repeat_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
