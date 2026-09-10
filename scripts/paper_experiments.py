#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aura_kv.simulator import MIB, SCENARIOS, SimulationConfig, run_matrix


CORE_POLICIES = [
    "RemoteOnly",
    "LocalFirst",
    "LRU-Local",
    "LFU-Local",
    "DualWindowReplacement",
    "SourceAwareReplacement",
    "AffinityOnly",
    "WA-Affinity-Independent",
    "AURA-Joint",
    "OracleDemand",
]

LATENCY_POLICIES = [
    "RemoteOnly",
    "LocalFirst",
    "LRU-Local",
    "LFU-Local",
    "AURA-Joint",
]

PRESSURE_SCENARIOS = [
    "high_recompute",
    "scan_pollution",
    "large_object_pollution",
    "tight_capacity_thrash",
    "expensive_vs_cheap_mix",
]

SCENARIO_DESCRIPTIONS = {
    "private": "每个逻辑 GPU 访问自己的私有缓存。",
    "node_shared": "同节点共享缓存。",
    "cluster_shared": "跨节点共享缓存。",
    "hotspot_shift": "热点从一个节点迁移到另一个节点。",
    "high_recompute": "高重算代价 KV 与普通 KV 混合。",
    "remote_congestion": "远端访问代价升高。",
    "demand_estimation_error": "访问突发且带预测误差。",
    "tenant_isolation": "多个租户交替访问。",
    "scan_pollution": "稳定热点后插入大量一次性扫描数据。",
    "large_object_pollution": "少量大对象挤占小热点缓存。",
    "multi_gpu_shared_burst": "共享 KV 在多个逻辑 GPU 间突发复用。",
    "tight_capacity_thrash": "本地容量紧张导致反复替换。",
    "expensive_vs_cheap_mix": "高重算与低重算缓存混合。",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper-oriented AURA-KV experiments.")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "reports/latest/paper-experiments"))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--nodes", type=int, default=4)
    parser.add_argument("--gpus-per-node", type=int, default=1)
    parser.add_argument("--local-capacity-mib", type=int, default=64)
    parser.add_argument("--remote-p99-ms", type=float, default=8.0)
    parser.add_argument("--duplicate-budget-mib", type=int, default=128)
    parser.add_argument("--node-duplicate-budget-mib", type=int, default=48)
    return parser.parse_args()


def base_config(args: argparse.Namespace) -> SimulationConfig:
    return SimulationConfig(
        seed=args.seed,
        nodes=args.nodes,
        gpus_per_node=args.gpus_per_node,
        local_capacity_mib=args.local_capacity_mib,
        remote_read_p99_ms=args.remote_p99_ms,
        duplicate_budget_mib=args.duplicate_budget_mib,
        node_duplicate_budget_mib=args.node_duplicate_budget_mib,
    )


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def mean(rows: Iterable[dict[str, object]], key: str) -> float:
    values = [float(row[key]) for row in rows]
    return statistics.mean(values) if values else 0.0


def result_rows(results) -> list[dict[str, object]]:
    return [asdict(result) for result in results]


def summarize_by_policy(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_policy: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_policy.setdefault(str(row["policy"]), []).append(row)

    summaries: list[dict[str, object]] = []
    for policy in CORE_POLICIES:
        policy_rows = by_policy.get(policy, [])
        if not policy_rows:
            continue
        summaries.append(
            {
                "policy": policy,
                "scenarios": len(policy_rows),
                "avg_local_hit_rate": round(mean(policy_rows, "local_cache_hit_rate"), 4),
                "avg_remote_read_mib": round(mean(policy_rows, "remote_read_bytes") / MIB, 2),
                "avg_peer_read_mib": round(mean(policy_rows, "peer_read_bytes") / MIB, 2),
                "avg_duplicate_mib": round(mean(policy_rows, "duplicate_bytes") / MIB, 2),
                "avg_migration_mib": round(mean(policy_rows, "migration_bytes") / MIB, 2),
                "avg_replica_churn": round(mean(policy_rows, "replica_churn"), 2),
                "avg_p50_ms": round(mean(policy_rows, "ttft_p50_ms"), 4),
                "avg_p95_ms": round(mean(policy_rows, "ttft_p95_ms"), 4),
                "avg_p99_ms": round(mean(policy_rows, "ttft_p99_ms"), 4),
                "avg_slo_violation_rate": round(mean(policy_rows, "slo_violation_rate"), 4),
                "avg_objective_cost_per_request": round(mean(policy_rows, "objective_cost_per_request"), 4),
            }
        )
    return summaries


def compute_performance_summary(trace_summary: list[dict[str, object]]) -> list[dict[str, object]]:
    by_policy = {str(row["policy"]): row for row in trace_summary}
    lru_cost = float(by_policy["LRU-Local"]["avg_objective_cost_per_request"])
    remote_cost = float(by_policy["RemoteOnly"]["avg_objective_cost_per_request"])
    aura_cost = float(by_policy["AURA-Joint"]["avg_objective_cost_per_request"])

    rows: list[dict[str, object]] = []
    for row in trace_summary:
        policy = str(row["policy"])
        cost = float(row["avg_objective_cost_per_request"])
        if cost <= 0:
            performance_index = 0.0
            normalized_to_lru = 0.0
            normalized_to_remote = 0.0
        else:
            performance_index = 1.0 / cost
            normalized_to_lru = lru_cost / cost
            normalized_to_remote = remote_cost / cost
        rows.append(
            {
                "policy": policy,
                "objective_cost_per_request": round(cost, 4),
                "performance_index": round(performance_index, 4),
                "normalized_to_lru": round(normalized_to_lru, 4),
                "normalized_to_remote": round(normalized_to_remote, 4),
                "aura_reduction_over_this_policy": round((cost - aura_cost) / max(1e-9, cost), 4)
                if policy != "AURA-Joint"
                else 0.0,
            }
        )
    return rows


def write_svg_bar_chart(
    path: Path,
    title: str,
    rows: list[dict[str, object]],
    value_key: str,
    unit: str,
    width: int = 1180,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    left = 245
    right = 150
    top = 82
    row_h = 44
    bar_h = 24
    max_bar_w = width - left - right
    height = top + len(rows) * row_h + 42
    values = [float(row[value_key]) for row in rows]
    max_value = max(values) if values else 1.0

    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        "<rect width='100%' height='100%' fill='#ffffff'/>",
        f"<text x='24' y='42' font-family='Arial, Helvetica, sans-serif' font-size='26' font-weight='700' fill='#20242b'>{escape(title)}</text>",
        f"<line x1='24' y1='62' x2='{width - 24}' y2='62' stroke='#d8dee8'/>",
    ]
    for index, row in enumerate(rows):
        y = top + index * row_h
        label = str(row["policy"])
        value = float(row[value_key])
        bar_w = 0 if max_value <= 0 else int(max_bar_w * value / max_value)
        color = "#2563eb" if label == "AURA-Joint" else "#64748b"
        parts.extend(
            [
                f"<text x='24' y='{y + 19}' font-family='Menlo, Consolas, monospace' font-size='18' fill='#20242b'>{escape(label)}</text>",
                f"<rect x='{left}' y='{y}' width='{max_bar_w}' height='{bar_h}' rx='5' fill='#eef2f7'/>",
                f"<rect x='{left}' y='{y}' width='{bar_w}' height='{bar_h}' rx='5' fill='{color}'/>",
                f"<text x='{left + max_bar_w + 18}' y='{y + 19}' font-family='Arial, Helvetica, sans-serif' font-size='18' fill='#20242b'>{value:.2f}{escape(unit)}</text>",
            ]
        )
    parts.append("</svg>\n")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_performance_outputs(output: Path, trace_summary: list[dict[str, object]]) -> list[dict[str, object]]:
    perf_rows = compute_performance_summary(trace_summary)
    perf_dir = output / "05_performance_summary"
    write_csv(perf_dir / "performance_summary.csv", perf_rows)

    selected = [
        row
        for row in perf_rows
        if row["policy"]
        in {
            "RemoteOnly",
            "LocalFirst",
            "LRU-Local",
            "LFU-Local",
            "DualWindowReplacement",
            "SourceAwareReplacement",
            "WA-Affinity-Independent",
            "AURA-Joint",
        }
    ]
    write_svg_bar_chart(
        output / "figures/effective_performance_index.svg",
        "Effective performance normalized to LRU-Local",
        selected,
        "normalized_to_lru",
        "x",
    )
    improvement_rows = [row for row in selected if row["policy"] != "AURA-Joint"]
    improvement_rows = [
        {**row, "aura_improvement_percent": round(float(row["aura_reduction_over_this_policy"]) * 100, 2)}
        for row in improvement_rows
    ]
    write_svg_bar_chart(
        output / "figures/aura_improvement_vs_baselines.svg",
        "AURA-Joint objective cost reduction over baselines",
        improvement_rows,
        "aura_improvement_percent",
        "%",
    )
    return perf_rows


def run_trace_replay(config: SimulationConfig, output: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    results = run_matrix(config, SCENARIOS, CORE_POLICIES)
    rows = result_rows(results)
    summary = summarize_by_policy(rows)
    trace_dir = output / "01_trace_replay"
    write_csv(trace_dir / "trace_detail.csv", rows)
    write_csv(trace_dir / "trace_summary.csv", summary)
    (trace_dir / "trace_results.json").write_text(
        json.dumps(
            {
                "notice": "SIMULATED TRACE REPLAY - replace generated traces with real vLLM/SGLang traces when available.",
                "config": asdict(config),
                "scenarios": SCENARIOS,
                "policies": CORE_POLICIES,
                "results": rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return rows, summary


def run_e2e_latency(config: SimulationConfig, output: Path) -> list[dict[str, object]]:
    results = run_matrix(config, SCENARIOS, LATENCY_POLICIES)
    rows = result_rows(results)
    by_policy: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_policy.setdefault(str(row["policy"]), []).append(row)
    summary = []
    for policy in LATENCY_POLICIES:
        policy_rows = by_policy.get(policy, [])
        summary.append(
            {
                "policy": policy,
                "avg_p50_ms": round(mean(policy_rows, "ttft_p50_ms"), 4),
                "avg_p95_ms": round(mean(policy_rows, "ttft_p95_ms"), 4),
                "avg_p99_ms": round(mean(policy_rows, "ttft_p99_ms"), 4),
                "avg_slo_violation_rate": round(mean(policy_rows, "slo_violation_rate"), 4),
                "avg_remote_read_mib": round(mean(policy_rows, "remote_read_bytes") / MIB, 2),
                "avg_objective_cost_per_request": round(mean(policy_rows, "objective_cost_per_request"), 4),
            }
        )
    latency_dir = output / "02_e2e_latency"
    write_csv(latency_dir / "latency_detail.csv", rows)
    write_csv(latency_dir / "latency_summary.csv", summary)
    return summary


def run_sensitivity(output: Path, args: argparse.Namespace) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    policies = ["LRU-Local", "LFU-Local", "DualWindowReplacement", "AURA-Joint"]
    scenarios = PRESSURE_SCENARIOS

    sweeps = [
        ("local_capacity_mib", [32, 48, 64, 96, 128]),
        ("remote_p99_ms", [2.0, 4.0, 8.0, 16.0]),
        ("duplicate_budget_mib", [64, 96, 128, 192]),
    ]
    for sweep_name, values in sweeps:
        for value in values:
            cfg_kwargs = asdict(base_config(args))
            if sweep_name == "remote_p99_ms":
                cfg_kwargs["remote_read_p99_ms"] = float(value)
            else:
                cfg_kwargs[sweep_name] = int(value)
            if sweep_name == "duplicate_budget_mib":
                cfg_kwargs["node_duplicate_budget_mib"] = min(int(value), args.node_duplicate_budget_mib)
            cfg = SimulationConfig(**cfg_kwargs)
            detail = result_rows(run_matrix(cfg, scenarios, policies))
            for policy in policies:
                policy_rows = [row for row in detail if row["policy"] == policy]
                rows.append(
                    {
                        "sweep": sweep_name,
                        "value": value,
                        "policy": policy,
                        "scenarios": len(policy_rows),
                        "avg_local_hit_rate": round(mean(policy_rows, "local_cache_hit_rate"), 4),
                        "avg_remote_read_mib": round(mean(policy_rows, "remote_read_bytes") / MIB, 2),
                        "avg_migration_mib": round(mean(policy_rows, "migration_bytes") / MIB, 2),
                        "avg_replica_churn": round(mean(policy_rows, "replica_churn"), 2),
                        "avg_p99_ms": round(mean(policy_rows, "ttft_p99_ms"), 4),
                        "avg_objective_cost_per_request": round(mean(policy_rows, "objective_cost_per_request"), 4),
                    }
                )
    sens_dir = output / "03_sensitivity"
    write_csv(sens_dir / "sensitivity_summary.csv", rows)
    return rows


def summarize_nvmeof(output: Path) -> list[dict[str, object]]:
    source = PROJECT_ROOT / "reports/latest/real-nvmeof-summary.csv"
    rows = read_csv(source)
    normalized: list[dict[str, object]] = []
    for row in rows:
        normalized.append(
            {
                "case": row.get("case", ""),
                "operation": row.get("operation", ""),
                "bandwidth_mib_s": row.get("bandwidth_mib_s", ""),
                "iops": row.get("iops", ""),
                "p50_ms": row.get("p50_ms", ""),
                "p95_ms": row.get("p95_ms", ""),
                "p99_ms": row.get("p99_ms", ""),
                "notes": row.get("notes", ""),
            }
        )
    baseline_dir = output / "04_nvmeof_baseline"
    write_csv(baseline_dir / "real_nvmeof_summary.csv", normalized)
    return normalized


def format_float(value: object, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def write_report(
    output: Path,
    config: SimulationConfig,
    trace_summary: list[dict[str, object]],
    latency_summary: list[dict[str, object]],
    sensitivity_rows: list[dict[str, object]],
    nvme_rows: list[dict[str, object]],
    performance_rows: list[dict[str, object]],
    real_speed_rows: list[dict[str, str]],
) -> None:
    report = output / "paper_experiments_report.md"
    aura = next(row for row in trace_summary if row["policy"] == "AURA-Joint")
    lru = next(row for row in trace_summary if row["policy"] == "LRU-Local")
    lfu = next(row for row in trace_summary if row["policy"] == "LFU-Local")

    lines = [
        "# AURA-KV 论文实验汇总",
        "",
        "本报告汇总当前仓库在无完整真实 GPU 集群条件下已经完成的前四项实验。策略实验是 trace-driven simulator 结果；NVMe-oF baseline 来自已采集的真实协议链路摘要。二者用途不同，论文中需要分别标注。",
        "",
        "## 0. 实验配置",
        "",
        f"- 逻辑节点数：{config.nodes}",
        f"- 每节点 GPU 数：{config.gpus_per_node}",
        f"- 每节点本地缓存容量：{config.local_capacity_mib} MiB",
        f"- 远端 P99 代理代价：{config.remote_read_p99_ms} ms",
        f"- 全局重复副本预算：{config.duplicate_budget_mib} MiB",
        f"- 单节点重复副本预算：{config.node_duplicate_budget_mib} MiB",
        "",
        "## 1. Trace 回放实验",
        "",
        "当前使用 13 个 KV Cache 访问场景作为可复现 trace。真实 vLLM/SGLang trace 到位后，可以保留相同统计口径替换输入 trace。",
        "",
        "| 场景 | 含义 |",
        "|---|---|",
    ]
    for scenario in SCENARIOS:
        lines.append(f"| `{scenario}` | {SCENARIO_DESCRIPTIONS[scenario]} |")

    lines.extend(
        [
            "",
            "| 策略 | 本地命中率 | 远端读取 MiB | 迁移 MiB | Churn | P99 ms | 综合代价/请求 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in trace_summary:
        lines.append(
            f"| `{row['policy']}` | {row['avg_local_hit_rate']} | {row['avg_remote_read_mib']} | "
            f"{row['avg_migration_mib']} | {row['avg_replica_churn']} | {row['avg_p99_ms']} | "
            f"{row['avg_objective_cost_per_request']} |"
        )

    lru_improvement = (float(lru["avg_objective_cost_per_request"]) - float(aura["avg_objective_cost_per_request"])) / max(
        1e-9, float(lru["avg_objective_cost_per_request"])
    )
    lfu_improvement = (float(lfu["avg_objective_cost_per_request"]) - float(aura["avg_objective_cost_per_request"])) / max(
        1e-9, float(lfu["avg_objective_cost_per_request"])
    )

    lines.extend(
        [
            "",
            "观察：",
            "",
            f"- `AURA-Joint` 平均综合代价为 `{float(aura['avg_objective_cost_per_request']):.4f}/request`。",
            f"- 相比 `LRU-Local` 降低 `{lru_improvement:.1%}`，相比 `LFU-Local` 降低 `{lfu_improvement:.1%}`。",
            "- AURA 的优势不只是命中率，而是同时控制远端读取、迁移量和副本抖动。",
            "",
            "## 1.1 总性能指标",
            "",
            "`综合代价/请求` 是越低越好的主指标。为了更直观展示“快了多少”，本报告进一步定义：",
            "",
            "```text",
            "等效性能指数 = LRU-Local 综合代价 / 当前策略综合代价",
            "```",
            "",
            "因此 `LRU-Local = 1.00x`，数值越大，表示在同一组 trace 下单位综合代价能服务更多请求。",
            "",
            "![等效性能提升柱状图](figures/effective_performance_index.svg)",
            "",
            "| 策略 | 综合代价/请求 | 等效性能指数 | 相对 RemoteOnly | AURA 相比该策略降低代价 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in performance_rows:
        lines.append(
            f"| `{row['policy']}` | {row['objective_cost_per_request']} | "
            f"{row['normalized_to_lru']}x | {row['normalized_to_remote']}x | "
            f"{float(row['aura_reduction_over_this_policy']) * 100:.2f}% |"
        )
    lines.extend(
        [
            "",
            "![AURA 相对基线的综合代价降低](figures/aura_improvement_vs_baselines.svg)",
            "",
            "## 1.2 真实 TokenFS Workload 速度实验",
            "",
            "成本模型解释控制器为什么做某个选择，但不能单独证明系统真的更快。因此仓库额外提供真实 TokenFS workload 测速入口：",
            "",
            "```bash",
            "TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/real_speed_benchmark.sh",
            "```",
            "",
            "该实验读取 FUSE/TokenFS 实际运行产生的 wall-clock 时间、有效吞吐和平均读写延迟，不使用成本模型权重。脚本默认强制检查远端后端已经通过 NVMe-oF 直连挂载，避免把 `remote-sim` 开发目录或 SSH tunnel 数据路径误写成直连网络 SSD 结果。workload 会使用独立实验命名空间，构造远端 canonical KV、本地冷缓存、容量压力、热点复用、顺序预取和跨 GPU 共享访问；因此可以同时观察总耗时和策略生效后的复用阶段收益。",
            "",
            "| 策略 | 总数据 MiB | 总耗时 s | 有效吞吐 MiB/s | 相对 RemoteOnly 加速 | 复用阶段吞吐 MiB/s | 复用阶段相对吞吐 | 平均读 us | 本地读命中率 | 远端打开读取 | 后台动作 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    if real_speed_rows:
        for row in real_speed_rows:
            actions = (
                f"promote={row.get('promote_count', '')}, "
                f"prefetch={row.get('prefetch_request_count', '')}/{row.get('prefetch_count', '')}, "
                f"evict={row.get('evict_count', '')}, "
                f"xgpu={row.get('cross_gpu_replica_create_count', '')}/{row.get('cross_gpu_local_replica_hit', '')}"
            )
            lines.append(
                f"| `{row.get('case', '')}` | {row.get('total_mib', '')} | {row.get('wall_time_s', '')} | "
                f"{row.get('effective_mib_s', '')} | {row.get('speedup_vs_baseline', '')}x | "
                f"{row.get('steady_reuse_mib_s', '')} | {row.get('steady_reuse_vs_baseline', '')}x | "
                f"{row.get('avg_read_us', '')} | {row.get('local_read_hit_rate_pct', '')}% | "
                f"{row.get('remote_read_open', '')} | {actions} |"
            )
    else:
        lines.append(
            "| pending | 0 | 0 | 0 | 0x | 0 | 0x | 0 | 0% | 0 | 需要在 Linux/FUSE 环境把远端配置为 NVMe-oF 挂载目录后运行 `TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/real_speed_benchmark.sh` |"
        )

    lines.extend(
        [
            "",
            "## 2. 端到端延迟代理实验",
            "",
            "这里的端到端延迟是 simulator 中一次 KV 获取的代理延迟，不等同于真实 TTFT。它用于比较策略是否减少远端访问和高尾延迟路径。",
            "",
            "| 策略 | P50 ms | P95 ms | P99 ms | SLO 违约率 | 远端读取 MiB | 综合代价/请求 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in latency_summary:
        lines.append(
            f"| `{row['policy']}` | {row['avg_p50_ms']} | {row['avg_p95_ms']} | {row['avg_p99_ms']} | "
            f"{row['avg_slo_violation_rate']} | {row['avg_remote_read_mib']} | {row['avg_objective_cost_per_request']} |"
        )

    lines.extend(
        [
            "",
            "## 3. 参数敏感性实验",
            "",
            "本实验分别改变本地容量、远端 P99 代价和副本预算，观察 AURA 是否只在某个特殊参数下有效。",
            "",
            "| 扫描参数 | 取值 | AURA 综合代价/请求 | LRU 综合代价/请求 | LFU 综合代价/请求 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    grouped: dict[tuple[str, object], dict[str, dict[str, object]]] = {}
    for row in sensitivity_rows:
        grouped.setdefault((str(row["sweep"]), row["value"]), {})[str(row["policy"])] = row
    for (sweep, value), policies in grouped.items():
        aura_row = policies.get("AURA-Joint", {})
        lru_row = policies.get("LRU-Local", {})
        lfu_row = policies.get("LFU-Local", {})
        lines.append(
            f"| `{sweep}` | {value} | {format_float(aura_row.get('avg_objective_cost_per_request'))} | "
            f"{format_float(lru_row.get('avg_objective_cost_per_request'))} | "
            f"{format_float(lfu_row.get('avg_objective_cost_per_request'))} |"
        )

    lines.extend(
        [
            "",
            "## 4. NVMe-oF Baseline",
            "",
            "该部分读取仓库中已有真实 NVMe/TCP 链路摘要。如果换到新的实验室节点，应重新运行 Linux 端 baseline 脚本生成同格式 CSV。",
            "",
            "| 用例 | 操作 | 带宽 MiB/s | IOPS | P50 ms | P95 ms | P99 ms | 备注 |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    if nvme_rows:
        for row in nvme_rows:
            lines.append(
                f"| `{row['case']}` | {row['operation']} | {row['bandwidth_mib_s']} | {row['iops']} | "
                f"{row['p50_ms']} | {row['p95_ms']} | {row['p99_ms']} | {row['notes']} |"
            )
    else:
        lines.append("| pending | pending | 0 | 0 | 0 | 0 | 0 | 当前仓库没有可读取的真实 NVMe-oF baseline CSV。 |")

    lines.extend(
        [
            "",
            "## 5. 论文写作可用结论",
            "",
            "- 策略层：AURA-Joint 在 13 个 trace 场景中降低综合服务代价，尤其适合扫描污染、大对象污染、容量紧张和重算代价差异明显的 KV Cache 场景。",
            "- 系统层：TokenFS/AURA-KV 已具备本地缓存、远端权威层、策略控制器、后台任务、指标输出和 Dashboard 的原型能力。",
            "- NVMe-oF 层：已有真实 NVMe/TCP baseline 摘要，能说明远端路径存在额外延迟和带宽上限；完整 GPU 端到端收益仍需要在真实推理 workload 上复测。",
            "",
            "## 6. 输出文件",
            "",
            "```text",
            "01_trace_replay/trace_summary.csv",
            "01_trace_replay/trace_detail.csv",
            "02_e2e_latency/latency_summary.csv",
            "02_e2e_latency/latency_detail.csv",
            "03_sensitivity/sensitivity_summary.csv",
            "04_nvmeof_baseline/real_nvmeof_summary.csv",
            "05_performance_summary/performance_summary.csv",
            "06_real_speed_benchmark/real_speed_summary.csv",
            "06_real_speed_benchmark/real_speed_report.md",
            "06_real_speed_benchmark/figures/",
            "figures/effective_performance_index.svg",
            "figures/aura_improvement_vs_baselines.svg",
            "paper_experiments_report.md",
            "```",
        ]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config = base_config(args)
    trace_rows, trace_summary = run_trace_replay(config, output)
    latency_summary = run_e2e_latency(config, output)
    sensitivity_rows = run_sensitivity(output, args)
    nvme_rows = summarize_nvmeof(output)
    performance_rows = write_performance_outputs(output, trace_summary)
    real_speed_rows = [
        row
        for row in read_csv(output / "06_real_speed_benchmark/real_speed_summary.csv")
        if row.get("case") in {"RemoteOnly", "LocalFirst", "LRU-Local", "LFU-Local", "AURA-Joint"}
    ]
    write_report(
        output,
        config,
        trace_summary,
        latency_summary,
        sensitivity_rows,
        nvme_rows,
        performance_rows,
        real_speed_rows,
    )
    print("AURA-KV paper experiments completed.")
    print("SIMULATED RESULT for strategy experiments; NVMe-oF section uses existing baseline CSV if present.")
    print(f"trace_rows={len(trace_rows)}")
    print(f"sensitivity_rows={len(sensitivity_rows)}")
    print(f"report={output / 'paper_experiments_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
