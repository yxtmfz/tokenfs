#!/usr/bin/env python3
import csv
import os
import json
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
    bw_bytes = section.get("bw_bytes", 0)
    iops = section.get("iops", 0)
    io_bytes = section.get("io_bytes", 0)
    runtime_ms = section.get("runtime", 0)
    return {
        "case": path.stem,
        "op": op,
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


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case",
                "op",
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
        f.write("| 用例 | 操作 | 数据量 MiB | 耗时 s | 带宽 MiB/s | IOPS | 平均延迟 us | P95 us | P99 us |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for row in rows:
            f.write(
                f"| `{row['case']}` | {row['op']} | {row['io_mib']} | "
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
        f.write("## 如何解读\n\n")
        f.write("这组测试主要用于观察：\n\n")
        f.write("- FUSE 路径相比直接目录访问的额外开销。\n")
        f.write("- 本地优先写入是否能正常保留在本地层。\n")
        f.write("- 超过配额后是否能触发远端溢写。\n")
        f.write("- 远端后端从目录模拟切换到 NVMe-oF 后的相对开销。\n\n")
        f.write("如果本报告来自双 VM NVMe-oF 环境，它可以证明真实 NVMe/TCP 协议路径已经接入，但由于底层仍是虚拟磁盘和虚拟网络，最终论文性能数据仍应在真实 SSD 与实验室网络上重新采集。\n")


def write_html(rows: list[dict], path: Path) -> None:
    max_bw = max((row["bw_mib_s"] for row in rows), default=0)
    title = os.environ.get("TOKENFS_PERF_TITLE", "TokenFS 性能测试报告")
    context = os.environ.get(
        "TOKENFS_PERF_CONTEXT",
        "本报告由性能测试脚本自动生成，默认用于开发虚拟机和目录模拟远端后端。",
    )
    html_rows = []
    for row in rows:
        pct = 0 if max_bw <= 0 else round(row["bw_mib_s"] / max_bw * 100, 2)
        html_rows.append(
            f"<tr><td>{row['case']}</td><td>{row['op']}</td>"
            f"<td>{row['io_mib']}</td><td>{row['runtime_s']}</td>"
            f"<td><div class='bar'><span style='width:{pct}%'></span></div>"
            f"{row['bw_mib_s']} MiB/s</td><td>{row['iops']}</td>"
            f"<td>{row['lat_mean_us']}</td><td>{row['lat_p95_us']}</td><td>{row['lat_p99_us']}</td></tr>"
        )
    path.write_text(
        """<!doctype html>
<meta charset="utf-8">
<title>TokenFS Performance Report</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; line-height: 1.5; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background: #f5f5f5; }
.bar { display: inline-block; width: 220px; height: 12px; background: #eee; margin-right: 8px; vertical-align: middle; }
.bar span { display: block; height: 12px; background: #2f6feb; }
code { background: #f5f5f5; padding: 2px 4px; }
</style>
<h1>""" + title + """</h1>
<p>""" + context + """</p>
<table>
<thead><tr><th>用例</th><th>操作</th><th>数据量 MiB</th><th>耗时 s</th><th>带宽</th><th>IOPS</th><th>平均延迟 us</th><th>P95 us</th><th>P99 us</th></tr></thead>
<tbody>
"""
        + "\n".join(html_rows)
        + """
</tbody>
</table>
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
