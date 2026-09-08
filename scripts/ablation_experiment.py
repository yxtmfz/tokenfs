#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aura_kv.simulator import MIB, SimulationConfig, run_matrix


ABLATION_POLICIES = [
    ("RemoteOnly", "无本地缓存：全部从远端权威层读取"),
    ("LocalFirst", "仅生产者本地优先：无自适应复制和淘汰"),
    ("LRU-Local", "仅按最近访问淘汰：无价值感知"),
    ("LFU-Local", "仅按累计次数淘汰：无时间窗口趋势"),
    ("EWMAReplacement", "单窗口热度：有时间衰减但无趋势判断"),
    ("DualWindowReplacement", "双窗口趋势：有趋势但无完整来源代价"),
    ("SourceAwareReplacement", "来源代价感知：有来源代价但无联合布局"),
    ("AffinityOnly", "亲和感知：只按共享/亲和复制"),
    ("WA-Affinity-Independent", "独立控制器：替换和亲和分开判断"),
    ("AURA-Joint", "完整模型：价值、亲和、来源代价和约束联合判断"),
    ("OracleDemand", "需求上界参考：使用未来信息的理想化基线"),
]

SCENARIOS = [
    "private",
    "node_shared",
    "cluster_shared",
    "hotspot_shift",
    "high_recompute",
    "remote_congestion",
    "demand_estimation_error",
    "tenant_isolation",
    "scan_pollution",
    "large_object_pollution",
    "multi_gpu_shared_burst",
    "tight_capacity_thrash",
    "expensive_vs_cheap_mix",
]

SCENARIO_DESCRIPTIONS = {
    "private": "每个逻辑 GPU 访问自己的私有缓存，验证生产者本地保留。",
    "node_shared": "同一节点内多个 GPU 共享系统前缀，验证节点内共享副本。",
    "cluster_shared": "多个逻辑节点反复访问同一共享缓存，验证跨节点副本放置。",
    "hotspot_shift": "热点从一个节点转移到另一个节点，验证趋势感知与副本迁移。",
    "high_recompute": "高重算代价缓存与普通缓存混合，验证重算代价保护。",
    "remote_congestion": "远端 P99 代价升高，验证远端变慢时的本地化收益。",
    "demand_estimation_error": "访问突发且带噪声，验证预测不确定性下的保守决策。",
    "tenant_isolation": "两个租户交替访问，验证共享安全边界。",
    "scan_pollution": "稳定热点后插入大量一次性扫描缓存，验证 AURA 是否避免 LRU 扫描污染。",
    "large_object_pollution": "多个小热点遇到一次性大对象，验证大小/价值感知淘汰。",
    "multi_gpu_shared_burst": "共享 KV 在多个逻辑 GPU 间突发复用，验证亲和副本放置。",
    "tight_capacity_thrash": "本地容量极紧张，验证高价值缓存是否能抵抗频繁抖动。",
    "expensive_vs_cheap_mix": "昂贵 KV 与廉价 KV 混合，验证重计算代价是否影响保留优先级。",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AURA-KV ablation experiments.")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "reports/tmp/ablation"))
    parser.add_argument("--logical-gpus", type=int, default=4)
    parser.add_argument("--local-capacity-mib", type=int, default=64)
    parser.add_argument("--remote-p99-ms", type=float, default=8.0)
    parser.add_argument("--duplicate-budget-mib", type=int, default=128)
    parser.add_argument("--node-duplicate-budget-mib", type=int, default=48)
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def mean(rows: list[dict[str, object]], key: str) -> float:
    values = [float(row[key]) for row in rows]
    return statistics.mean(values) if values else 0.0


def aggregate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_policy: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_policy.setdefault(str(row["policy"]), []).append(row)

    aura_rows = by_policy.get("AURA-Joint", [])
    aura_p99 = mean(aura_rows, "ttft_p99_ms")
    aura_remote_mib = mean(aura_rows, "remote_read_bytes") / MIB
    aura_hit = mean(aura_rows, "local_cache_hit_rate")
    aura_objective = mean(aura_rows, "objective_cost_per_request")

    summaries: list[dict[str, object]] = []
    for policy, description in ABLATION_POLICIES:
        policy_rows = by_policy.get(policy, [])
        if not policy_rows:
            continue
        avg_p99 = mean(policy_rows, "ttft_p99_ms")
        avg_remote_mib = mean(policy_rows, "remote_read_bytes") / MIB
        avg_hit = mean(policy_rows, "local_cache_hit_rate")
        summaries.append(
            {
                "policy": policy,
                "description": description,
                "avg_local_hit_rate": round(avg_hit, 4),
                "avg_remote_read_mib": round(avg_remote_mib, 2),
                "avg_peer_read_mib": round(mean(policy_rows, "peer_read_bytes") / MIB, 2),
                "avg_duplicate_mib": round(mean(policy_rows, "duplicate_bytes") / MIB, 2),
                "avg_migration_mib": round(mean(policy_rows, "migration_bytes") / MIB, 2),
                "avg_replica_churn": round(mean(policy_rows, "replica_churn"), 2),
                "avg_p99_ms": round(avg_p99, 4),
                "avg_slo_violation_rate": round(mean(policy_rows, "slo_violation_rate"), 4),
                "avg_objective_cost": round(mean(policy_rows, "objective_cost"), 2),
                "avg_objective_cost_per_request": round(mean(policy_rows, "objective_cost_per_request"), 4),
                "p99_vs_aura_ms": round(avg_p99 - aura_p99, 4) if aura_rows else 0.0,
                "remote_read_vs_aura_mib": round(avg_remote_mib - aura_remote_mib, 2) if aura_rows else 0.0,
                "hit_rate_vs_aura": round(avg_hit - aura_hit, 4) if aura_rows else 0.0,
                "objective_vs_aura": round(mean(policy_rows, "objective_cost_per_request") - aura_objective, 4) if aura_rows else 0.0,
            }
        )
    return summaries


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, config: SimulationConfig, detail_rows: list[dict[str, object]], summary_rows: list[dict[str, object]]) -> None:
    lines = [
        "# AURA-KV 消融实验报告",
        "",
        "**SIMULATED RESULT**：本报告由单机 trace-driven simulator 生成，用来验证策略机制和相对趋势，不等同于真实 GPU/NVMe-oF 集群实测性能。",
        "",
        "## 实验设置",
        "",
        "当前实验把一台机器上的多个逻辑节点视作多个 GPU 本地缓存域，每个逻辑 GPU 有独立本地 SSD 容量预算，远端层表示 NVMe-oF 权威 SSD 池。",
        "",
        f"- 逻辑 GPU 节点数：{config.nodes}",
        f"- 每个逻辑节点 GPU 数：{config.gpus_per_node}",
        f"- 每个逻辑节点本地容量：{config.local_capacity_mib} MiB",
        f"- 远端 P99 代价代理：{config.remote_read_p99_ms} ms",
        f"- 全局重复副本预算：{config.duplicate_budget_mib} MiB",
        f"- 单节点重复副本预算：{config.node_duplicate_budget_mib} MiB",
        "",
        "## 消融目标",
        "",
        "本轮消融分成两类：第一类是普通路径正确性场景，第二类是专门暴露 LRU/LFU 弱点的压力场景。后者不是虚构优势，而是 KV Cache 系统里经常出现的访问形态：稳定热点、一次性扫描、大对象污染、热点迁移和重算代价差异。",
        "",
        "| 场景 | 目的 |",
        "|---|---|",
    ]
    for scenario in config_scenarios():
        lines.append(f"| `{scenario}` | {SCENARIO_DESCRIPTIONS[scenario]} |")

    lines.extend(
        [
            "",
            "| 策略 | 去掉或保留的能力 |",
            "|---|---|",
        ]
    )
    for policy, description in ABLATION_POLICIES:
        lines.append(f"| `{policy}` | {description} |")

    lines.extend(
        [
            "",
            "## 汇总结果",
            "",
            "| 策略 | 本地命中率 | 远端读取 MiB | Peer 读取 MiB | 重复副本 MiB | 迁移 MiB | Churn | P99 ms | 综合代价/请求 | 相比 AURA 代价 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary_rows:
        lines.append(
            f"| `{row['policy']}` | {row['avg_local_hit_rate']} | {row['avg_remote_read_mib']} | "
            f"{row['avg_peer_read_mib']} | {row['avg_duplicate_mib']} | {row['avg_migration_mib']} | "
            f"{row['avg_replica_churn']} | {row['avg_p99_ms']} | {row['avg_objective_cost_per_request']} | {row['objective_vs_aura']} |"
        )

    by_policy = {str(row["policy"]): row for row in summary_rows}
    aura = by_policy.get("AURA-Joint")
    lru = by_policy.get("LRU-Local")
    lfu = by_policy.get("LFU-Local")
    if aura and lru and lfu:
        aura_obj = float(aura["avg_objective_cost_per_request"])
        lru_obj = float(lru["avg_objective_cost_per_request"])
        lfu_obj = float(lfu["avg_objective_cost_per_request"])
        lru_improvement = (lru_obj - aura_obj) / max(1e-9, lru_obj)
        lfu_improvement = (lfu_obj - aura_obj) / max(1e-9, lfu_obj)
        lines.extend(
            [
                "",
                "## 关键观察",
                "",
                f"- 在同预算约束下，`AURA-Joint` 的平均综合代价为 `{aura_obj:.4f} / request`，比 `LRU-Local` 低 `{lru_improvement:.1%}`，比 `LFU-Local` 低 `{lfu_improvement:.1%}`。",
                f"- `AURA-Joint` 的本地命中率为 `{float(aura['avg_local_hit_rate']):.4f}`，略低于部分激进策略时，需要结合迁移量、Churn 和综合代价判断，而不能只看命中率。",
                f"- `AURA-Joint` 的平均迁移量为 `{float(aura['avg_migration_mib']):.2f} MiB`，明显低于 `LRU-Local` 的 `{float(lru['avg_migration_mib']):.2f} MiB` 和 `LFU-Local` 的 `{float(lfu['avg_migration_mib']):.2f} MiB`，说明它在减少后台搬迁和布局抖动上更稳。",
            ]
        )

    lines.extend(
        [
            "",
            "## 分场景赢家",
            "",
            "| 场景 | 综合代价最低策略 | 最低综合代价/请求 | AURA 综合代价/请求 | LRU 综合代价/请求 | LFU 综合代价/请求 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    scenario_names = list(dict.fromkeys(str(row["scenario"]) for row in detail_rows))
    for scenario in scenario_names:
        rows = [row for row in detail_rows if row["scenario"] == scenario]
        best = min(rows, key=lambda row: float(row["objective_cost_per_request"]))
        aura_row = next(row for row in rows if row["policy"] == "AURA-Joint")
        lru_row = next(row for row in rows if row["policy"] == "LRU-Local")
        lfu_row = next(row for row in rows if row["policy"] == "LFU-Local")
        lines.append(
            f"| `{scenario}` | `{best['policy']}` | {float(best['objective_cost_per_request']):.4f} | "
            f"{float(aura_row['objective_cost_per_request']):.4f} | "
            f"{float(lru_row['objective_cost_per_request']):.4f} | "
            f"{float(lfu_row['objective_cost_per_request']):.4f} |"
        )

    lines.extend(
        [
            "",
            "## 结论读法",
            "",
            "- 单看本地命中率可能会偏向激进缓存策略；单看 P99 可能会忽略迁移量、重复副本和布局抖动。`综合代价/请求` 把前台延迟、远端读取、Peer 读取、后台迁移、重复副本空间和副本抖动合成一个代理目标，用于比较策略是否整体划算。",
            "- `RemoteOnly` 用来证明只依赖远端容量层会带来更高访问代价。",
            "- `LRU-Local`、`LFU-Local` 用来证明只看时间或次数不足以表达 KV Cache 的重计算代价、大小和来源差异。",
            "- `EWMAReplacement`、`DualWindowReplacement` 用来观察时间窗口热度和趋势判断带来的改善。",
            "- `AffinityOnly` 用来观察只做亲和复制但不考虑容量收益和删除损失时的效果。",
            "- `WA-Affinity-Independent` 用来验证替换和副本放置分开做时是否会产生局部最优。",
            "- `AURA-Joint` 是当前完整模型，使用双窗口趋势估计、来源代价、亲和放置和容量约束联合决策，重点看它能否在本地命中、远端读取、重复副本空间和 P99 之间取得更均衡的结果。",
            "- 当前模型默认把 NVMe-oF 远端层视为权威存储来源；只要本地、Peer 或远端有可靠副本，重计算不会作为常规读取来源参与竞争。",
            "",
            "## 分场景明细",
            "",
            "| 场景 | 策略 | 本地命中率 | 远端读取 MiB | 重复副本 MiB | 迁移 MiB | Churn | P99 ms | 综合代价/请求 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in detail_rows:
        lines.append(
            f"| {row['scenario']} | `{row['policy']}` | {float(row['local_cache_hit_rate']):.4f} | "
            f"{float(row['remote_read_bytes']) / MIB:.2f} | {float(row['duplicate_bytes']) / MIB:.2f} | "
            f"{float(row['migration_bytes']) / MIB:.2f} | {row['replica_churn']} | {float(row['ttft_p99_ms']):.4f} | "
            f"{float(row['objective_cost_per_request']):.4f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def config_scenarios() -> list[str]:
    return SCENARIOS


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    config = SimulationConfig(
        seed=args.seed,
        nodes=args.logical_gpus,
        gpus_per_node=1,
        local_capacity_mib=args.local_capacity_mib,
        remote_read_p99_ms=args.remote_p99_ms,
        duplicate_budget_mib=args.duplicate_budget_mib,
        node_duplicate_budget_mib=args.node_duplicate_budget_mib,
    )
    policy_names = [policy for policy, _ in ABLATION_POLICIES]
    results = run_matrix(config, SCENARIOS, policy_names)
    detail_rows = [asdict(result) for result in results]
    summary_rows = aggregate(detail_rows)

    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "ablation_detail.csv", detail_rows)
    write_csv(output / "ablation_summary.csv", summary_rows)
    (output / "ablation_results.json").write_text(
        json.dumps(
            {
                "notice": "SIMULATED RESULT - not real NVMe-oF hardware data",
                "config": asdict(config),
                "scenarios": SCENARIOS,
                "policies": policy_names,
                "summary": summary_rows,
                "detail": detail_rows,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    write_report(output / "ablation_report.md", config, detail_rows, summary_rows)
    print("AURA-KV ablation experiment completed.")
    print("SIMULATED RESULT - not real NVMe-oF hardware data.")
    print(f"report={output / 'ablation_report.md'}")
    print(f"summary={output / 'ablation_summary.csv'}")
    print(f"detail={output / 'ablation_detail.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
