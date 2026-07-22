#!/usr/bin/env python3
import csv
import html
import json
import os
import sys
from pathlib import Path


CASE_DESCRIPTIONS = {
    "direct-local-write": "直接写 GPU 本地后端目录，作为本地存储写入基线。",
    "direct-local-read": "直接读 GPU 本地后端目录，作为本地存储读取基线。",
    "direct-remote-write": "直接写远端后端目录，开发模式下是目录模拟，NVMe-oF 模式下是远端挂载目录。",
    "direct-remote-read": "直接读远端后端目录，开发模式下是目录模拟，NVMe-oF 模式下是远端挂载目录。",
    "tokenfs-local-write": "通过 TokenFS/FUSE 写入小文件，预期保留在 GPU 本地层。",
    "tokenfs-local-read": "通过 TokenFS/FUSE 读取本地层文件。",
    "tokenfs-remote-spill-write": "通过 TokenFS/FUSE 写入超过本地配额的文件，触发远端溢写。",
    "tokenfs-remote-read": "通过 TokenFS/FUSE 读取远端层文件。",
}


def load_result(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    job = data["jobs"][0]
    read = job.get("read", {})
    write = job.get("write", {})
    op = "read" if read.get("io_bytes", 0) else "write"
    section = read if op == "read" else write
    options = job.get("job options", {})
    bw_bytes = section.get("bw_bytes", 0)
    iops = section.get("iops", 0)
    io_bytes = section.get("io_bytes", 0)
    runtime_ms = section.get("runtime", 0)
    return {
        "case": path.stem,
        "op": op,
        "bs": options.get("bs", "-"),
        "ioengine": options.get("ioengine", "-"),
        "iodepth": options.get("iodepth", "-"),
        "direct": options.get("direct", "-"),
        "io_mib": round(io_bytes / 1024 / 1024, 2),
        "runtime_s": round(runtime_ms / 1000, 3),
        "bw_mib_s": round(bw_bytes / 1024 / 1024, 2),
        "iops": round(iops, 2),
        "lat_mean_us": round(section.get("lat_ns", {}).get("mean", 0) / 1000, 2),
        "lat_p95_us": round(
            section.get("clat_ns", {}).get("percentile", {}).get("95.000000", 0) / 1000,
            2,
        ),
        "lat_p99_us": round(
            section.get("clat_ns", {}).get("percentile", {}).get("99.000000", 0) / 1000,
            2,
        ),
    }


def bar(value: float, max_value: float, width: int = 28) -> str:
    if max_value <= 0:
        return ""
    filled = int(round((value / max_value) * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def ratio(a: float, b: float) -> float:
    return 0 if b == 0 else a / b


def row_by_case(rows: list[dict], case: str):
    return next((row for row in rows if row["case"] == case), None)


def derive_insights(rows: list[dict]) -> list[str]:
    insights = []
    direct_local_read = row_by_case(rows, "direct-local-read")
    direct_remote_read = row_by_case(rows, "direct-remote-read")
    tokenfs_local_read = row_by_case(rows, "tokenfs-local-read")
    tokenfs_remote_read = row_by_case(rows, "tokenfs-remote-read")
    direct_local_write = row_by_case(rows, "direct-local-write")
    direct_remote_write = row_by_case(rows, "direct-remote-write")
    tokenfs_local_write = row_by_case(rows, "tokenfs-local-write")
    tokenfs_remote_write = row_by_case(rows, "tokenfs-remote-spill-write")

    if direct_local_read and direct_remote_read:
        slowdown = ratio(direct_remote_read["lat_mean_us"], direct_local_read["lat_mean_us"])
        bw_ratio = ratio(direct_remote_read["bw_mib_s"], direct_local_read["bw_mib_s"]) * 100
        insights.append(
            f"直接远端读取的平均延迟约为直接本地读取的 {slowdown:.1f} 倍，"
            f"带宽约为本地的 {bw_ratio:.1f}%。这说明远端路径即使能跑出带宽，也会多出网络和 Target 处理延迟。"
        )

    if tokenfs_local_read and direct_local_read:
        overhead = ratio(direct_local_read["bw_mib_s"], tokenfs_local_read["bw_mib_s"])
        insights.append(
            f"TokenFS 本地读带宽低于直接本地读，当前约有 {overhead:.1f} 倍差距，"
            "主要反映 FUSE、元数据维护和用户态转发开销。"
        )

    if tokenfs_remote_read and direct_remote_read:
        overhead = ratio(direct_remote_read["bw_mib_s"], tokenfs_remote_read["bw_mib_s"])
        insights.append(
            f"TokenFS 远端读相比直接远端读约慢 {overhead:.1f} 倍，"
            "后续热点提升和顺序预取就是为了减少重复远端读取。"
        )

    if tokenfs_local_write and tokenfs_remote_write:
        insights.append(
            "远端溢写写入不是单纯写文件，还包含配额判断、必要时迁移和元数据提交，"
            "因此要和直接目录写分开解读。"
        )

    if direct_local_write and direct_remote_write and direct_remote_write["bw_mib_s"] >= direct_local_write["bw_mib_s"]:
        insights.append(
            "直接远端写入看起来不慢甚至更快时，不要直接理解成远端 SSD 比本地快。"
            "当前基线使用较大的顺序块且可能经过页缓存，写入完成可能先落入内核缓存；"
            "论文实验需要增加 direct=1、更大数据量和 fsync/掉电语义测试。"
        )

    if rows and all(str(row.get("bs")) == "1m" for row in rows):
        insights.append(
            "本组测试块大小是 1 MiB，因此 IOPS 与 MiB/s 数值接近。"
            "后续若改成 4 KiB 随机读写，IOPS 更适合衡量小块访问能力。"
        )
    return insights


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            lineterminator="\n",
            fieldnames=[
                "case",
                "op",
                "bs",
                "ioengine",
                "iodepth",
                "direct",
                "io_mib",
                "runtime_s",
                "bw_mib_s",
                "iops",
                "lat_mean_us",
                "lat_p95_us",
                "lat_p99_us",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict], path: Path) -> None:
    max_bw = max((row["bw_mib_s"] for row in rows), default=0)
    max_runtime = max((row["runtime_s"] for row in rows), default=0)
    max_p99 = max((row["lat_p99_us"] for row in rows), default=0)
    title = os.environ.get("TOKENFS_PERF_TITLE", "TokenFS 性能测试报告")
    context = os.environ.get(
        "TOKENFS_PERF_CONTEXT",
        "本报告由性能测试脚本自动生成，默认用于开发虚拟机和目录模拟远端后端。",
    )
    with path.open("w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(context + "\n\n")
        f.write("## 测试说明\n\n")
        for row in rows:
            description = CASE_DESCRIPTIONS.get(row["case"], "自定义测试用例。")
            f.write(f"- `{row['case']}`：{description}\n")
        f.write("\n")
        f.write("## 结果表\n\n")
        f.write("| 用例 | 操作 | 块大小 | 数据量 MiB | 耗时 s | 带宽 MiB/s | IOPS | 平均延迟 us | P95 us | P99 us |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for row in rows:
            f.write(
                f"| `{row['case']}` | {row['op']} | {row['bs']} | {row['io_mib']} | "
                f"{row['runtime_s']} | {row['bw_mib_s']} | {row['iops']} | "
                f"{row['lat_mean_us']} | {row['lat_p95_us']} | {row['lat_p99_us']} |\n"
            )

        f.write("\n## 带宽可视化\n\n")
        f.write("```text\n")
        for row in rows:
            f.write(
                f"{row['case']:<30} {bar(row['bw_mib_s'], max_bw)} "
                f"{row['bw_mib_s']} MiB/s\n"
            )
        f.write("```\n\n")

        f.write("## 耗时可视化\n\n")
        f.write("```text\n")
        for row in rows:
            f.write(
                f"{row['case']:<30} {bar(row['runtime_s'], max_runtime)} "
                f"{row['runtime_s']} s\n"
            )
        f.write("```\n\n")

        f.write("## P99 延迟可视化\n\n")
        f.write("```text\n")
        for row in rows:
            f.write(
                f"{row['case']:<30} {bar(row['lat_p99_us'], max_p99)} "
                f"{row['lat_p99_us']} us\n"
            )
        f.write("```\n\n")

        f.write("## 自动解读\n\n")
        for item in derive_insights(rows):
            f.write(f"- {item}\n")
        f.write("\n")
        f.write("## 如何解读\n\n")
        f.write("- 带宽说明一次大块连续读写能跑多快。\n")
        f.write("- 耗时说明完成这次测试总共花了多久。\n")
        f.write("- 延迟说明单个 I/O 请求要等多久，远端路径通常更吃亏。\n")
        f.write("- IOPS 表示每秒完成多少次 I/O；当块大小是 1 MiB 时，IOPS 和 MiB/s 数值会接近。\n\n")
        f.write("如果本报告来自双 VM NVMe-oF 环境，它可以证明真实 NVMe/TCP 协议路径已经接入，但由于底层仍是虚拟磁盘和虚拟网络，最终论文性能数据仍应在真实 SSD 与实验室网络上重新采集。\n")


def html_bar(row: dict, metric: str, max_value: float, unit: str) -> str:
    pct = 0 if max_value <= 0 else round(row[metric] / max_value * 100, 2)
    label = html.escape(row["case"])
    value = row[metric]
    return (
        "<div class='chart-row'>"
        f"<span class='chart-label'>{label}</span>"
        "<span class='chart-track'>"
        f"<span class='chart-bar' style='width:{pct}%'></span>"
        "</span>"
        f"<span class='chart-value'>{value} {unit}</span>"
        "</div>"
    )


def write_html(rows: list[dict], path: Path) -> None:
    title = os.environ.get("TOKENFS_PERF_TITLE", "TokenFS 性能测试报告")
    context = os.environ.get(
        "TOKENFS_PERF_CONTEXT",
        "本报告由性能测试脚本自动生成，默认用于开发虚拟机和目录模拟远端后端。",
    )
    max_bw = max((row["bw_mib_s"] for row in rows), default=0)
    max_runtime = max((row["runtime_s"] for row in rows), default=0)
    max_iops = max((row["iops"] for row in rows), default=0)
    max_mean = max((row["lat_mean_us"] for row in rows), default=0)
    max_p99 = max((row["lat_p99_us"] for row in rows), default=0)

    html_rows = []
    for row in rows:
        html_rows.append(
            f"<tr><td><code>{html.escape(row['case'])}</code></td><td>{row['op']}</td>"
            f"<td>{row['bs']}</td><td>{row['io_mib']}</td><td>{row['runtime_s']}</td>"
            f"<td>{row['bw_mib_s']}</td><td>{row['iops']}</td>"
            f"<td>{row['lat_mean_us']}</td><td>{row['lat_p95_us']}</td><td>{row['lat_p99_us']}</td></tr>"
        )
    insight_items = "\n".join(f"<li>{html.escape(item)}</li>" for item in derive_insights(rows))

    charts = [
        ("带宽 MiB/s，越高越好", "bw_mib_s", max_bw, "MiB/s"),
        ("总耗时 s，越低越好", "runtime_s", max_runtime, "s"),
        ("IOPS，越高越好", "iops", max_iops, "IOPS"),
        ("平均延迟 us，越低越好", "lat_mean_us", max_mean, "us"),
        ("P99 延迟 us，越低越好", "lat_p99_us", max_p99, "us"),
    ]
    chart_html = []
    for heading, metric, max_value, unit in charts:
        chart_html.append(f"<section class='chart'><h2>{heading}</h2>")
        for row in rows:
            chart_html.append(html_bar(row, metric, max_value, unit))
        chart_html.append("</section>")

    path.write_text(
        """<!doctype html>
<meta charset="utf-8">
<title>TokenFS Performance Report</title>
<style>
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  margin: 32px;
  line-height: 1.5;
  color: #20242a;
}
h1 { margin-bottom: 8px; }
h2 { margin-top: 28px; border-bottom: 1px solid #d8dee8; padding-bottom: 8px; }
p, li { max-width: 980px; }
table { border-collapse: collapse; width: 100%; margin-top: 12px; }
th, td { border: 1px solid #cfd8e3; padding: 8px; text-align: left; }
th { background: #f4f6f8; }
code { background: #f0f2f4; padding: 2px 6px; border-radius: 6px; }
.charts { display: grid; grid-template-columns: 1fr; gap: 8px; }
.chart { margin-top: 12px; }
.chart-row {
  display: grid;
  grid-template-columns: minmax(230px, 34%) 1fr minmax(120px, auto);
  gap: 10px;
  align-items: center;
  margin: 7px 0;
}
.chart-label { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.chart-track { height: 16px; background: #eef1f5; border-radius: 999px; overflow: hidden; }
.chart-bar { display: block; height: 100%; background: #2f6feb; }
.chart-value { text-align: right; font-variant-numeric: tabular-nums; }
.note { background: #f7f9fc; border-left: 4px solid #2f6feb; padding: 12px 16px; margin-top: 18px; }
@media (max-width: 720px) {
  body { margin: 18px; }
  .chart-row { grid-template-columns: 1fr; gap: 4px; }
  .chart-value { text-align: left; }
  table { font-size: 13px; }
}
</style>
<h1>""" + html.escape(title) + """</h1>
<p>""" + html.escape(context) + """</p>
<section class="note">
<strong>解读提醒：</strong>带宽高不代表远端一定更好。远端路径还要看平均延迟、P95/P99 延迟和 TokenFS/FUSE 额外开销。
</section>
<h2>结果表</h2>
<table>
<thead><tr><th>用例</th><th>操作</th><th>块大小</th><th>数据量 MiB</th><th>耗时 s</th><th>带宽 MiB/s</th><th>IOPS</th><th>平均延迟 us</th><th>P95 us</th><th>P99 us</th></tr></thead>
<tbody>
"""
        + "\n".join(html_rows)
        + """
</tbody>
</table>
<div class="charts">
"""
        + "\n".join(chart_html)
        + """
</div>
<h2>自动解读</h2>
<ul>
"""
        + insight_items
        + """
</ul>
<h2>指标含义</h2>
<ul>
<li><strong>带宽</strong>：单位时间搬了多少数据，适合看大块顺序读写。</li>
<li><strong>耗时</strong>：完成整次测试花了多久，适合看端到端体验。</li>
<li><strong>IOPS</strong>：每秒完成多少次 I/O。块大小为 1 MiB 时，IOPS 和 MiB/s 数值会接近；块大小为 4 KiB 时，IOPS 更能反映小块随机访问能力。</li>
<li><strong>P99 延迟</strong>：99% 请求都能在这个时间内完成，适合看尾延迟和稳定性。</li>
</ul>
<p>双 VM NVMe-oF 可以证明协议路径，但最终论文性能数据仍应在真实 SSD 与实验室网络上重新采集。</p>
""",
        encoding="utf-8",
    )


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: perf_report.py <fio-json-dir> <output-dir>", file=sys.stderr)
        return 2
    json_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [load_result(path) for path in sorted(json_dir.glob("*.json"))]
    write_csv(rows, out_dir / "summary.csv")
    write_markdown(rows, out_dir / "report.md")
    write_html(rows, out_dir / "report.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
