#!/usr/bin/env python3
"""Generate speed-first paired comparisons; never combine validation with performance."""
from __future__ import annotations
import argparse
import itertools
import json
import math
from pathlib import Path
import random
import statistics

from evidence_benchmark import dump, percentile

COMPARISONS = {
    "LRU-equal": "整体性能 / 对等 LRU",
    "LFU-equal": "整体性能 / 对等 LFU",
    "RemoteOnly": "整体性能 / 无缓存",
    "no-value": "组件 / 价值淘汰",
    "no-gain": "组件 / 收益准入",
    "no-affinity": "组件 / 亲和放置",
    "no-trend": "组件 / 趋势",
    "no-xgpu": "架构 / 跨逻辑 GPU 缓存",
    "synchronous": "系统开销 / 异步执行",
}


def interval(values, transform=lambda x:x, alpha=.05):
    if len(values) < 2: return [None, None]
    rng=random.Random(714)
    means=[transform(statistics.mean(rng.choices(values,k=len(values)))) for _ in range(5000)]
    return [percentile(means,alpha/2),percentile(means,1-alpha/2)]


def paired_p(values):
    """Two-sided paired sign-flip test under the symmetric-null assumption."""
    if len(values) < 2: return None
    observed=abs(sum(values))
    if len(values) <= 16:
        flips=itertools.product((-1,1),repeat=len(values))
        scores=[abs(sum(v*s for v,s in zip(values,signs))) for signs in flips]
        return sum(s >= observed-1e-12 for s in scores)/len(scores)
    rng=random.Random(712)
    count=sum(abs(sum(v*rng.choice((-1,1)) for v in values)) >= observed-1e-12 for _ in range(10000))
    return (count+1)/10001


def holm(rows):
    candidates=sorted((r for r in rows if r["p_raw"] is not None),key=lambda r:r["p_raw"])
    prior=0
    for i,r in enumerate(candidates):
        prior=max(prior,min(1,r["p_raw"]*(len(candidates)-i)))
        r["p_holm"]=prior


def analyze(root):
    manifest=json.loads((root/"manifest.json").read_text())
    rows=[]; data={}; failures=list(root.rglob("failure.json"))
    for path in root.glob("*-seed-*/*/result.json"):
        result=json.loads(path.read_text())
        if result["verify_every_request"]: raise ValueError("correctness runs are not performance evidence")
        if result["job_wall_s"] <= 0: raise ValueError("invalid wall time")
        data[(path.parent.parent.name,result["strategy"])]=result
    scenarios=manifest["args"]["scenarios"]
    expected_seeds=manifest["args"]["seeds"]
    for scenario in scenarios:
        comparisons=[("AURA-core",base,category) for base,category in COMPARISONS.items()]
        comparisons.append(("AURA-prefetch","AURA-core","组件 / 预取"))
        for treatment,baseline,category in comparisons:
            pairs=[]
            for seed in expected_seeds:
                key=f"{scenario}-seed-{seed}"
                a=data.get((key,treatment)); b=data.get((key,baseline))
                if a and b:
                    if a["logical_bytes"] != b["logical_bytes"]: raise ValueError("unpaired byte count")
                    pairs.append((a,b))
            if not pairs: continue
            logs=[math.log(a["job_wall_s"]/b["job_wall_s"]) for a,b in pairs]
            rows.append(dict(scenario=scenario,comparison=category,treatment=treatment,baseline=baseline,n=len(pairs),
                             complete=len(pairs)==len(expected_seeds) and not failures,
                             aura_wall_s=statistics.mean(a["job_wall_s"] for a,b in pairs),
                             baseline_wall_s=statistics.mean(b["job_wall_s"] for a,b in pairs),
                             aura_mib_s=statistics.mean(a["effective_mib_s"] for a,b in pairs),
                             baseline_mib_s=statistics.mean(b["effective_mib_s"] for a,b in pairs),
                             time_ratio=math.exp(statistics.mean(logs)),ci95=interval(logs,math.exp),
                             p_raw=paired_p(logs),p_holm=None,
                             mechanism_triggered=(baseline!="no-value" or any(a["metrics"].get("evict_count",0) for a,b in pairs))))
    for r in rows:
        r["family"] = "primary-LRU-LFU" if r["baseline"] in {"LRU-equal","LFU-equal"} else r["comparison"]
    for family in {r["family"] for r in rows}:
        holm([r for r in rows if r["family"] == family])
    for r in rows:
        if not r["complete"]: verdict="批次不完整，不作结论"
        elif not r["mechanism_triggered"]: verdict="未触发目标机制"
        elif r["n"]<10: verdict="pilot，样本不足"
        elif r["p_holm"] is not None and r["p_holm"]<.05 and r["ci95"][1]<1: verdict="支持此场景下真实提速"
        elif r["p_holm"] is not None and r["p_holm"]<.05 and r["ci95"][0]>1: verdict="此场景下更慢"
        else: verdict="速度贡献证据不确定"
        r["verdict"]=verdict
    interactions=[]
    for scenario in scenarios:
        differences=[]
        for seed in expected_seeds:
            block=f"{scenario}-seed-{seed}"
            cells=[data.get((block,s)) for s in ["E0A0","no-affinity","no-value","AURA-core"]]
            if all(cells):
                t00,t10,t01,t11=[c["job_wall_s"] for c in cells]
                differences.append(t11-t10-t01+t00)
        if differences:
            interactions.append(dict(scenario=scenario,n=len(differences),mean_interaction_s=statistics.mean(differences),
                                     ci95=interval(differences),definition="T11-T10-T01+T00; negative is beneficial interaction"))
    dump(root/"paired-comparisons.json",rows);dump(root/"interactions.json",interactions)
    lines=["# 真实速率与消融证据报告","",f"批次：{root.name}。缓存条件：{manifest['cache_mode']}。", "",
           "主指标为完整任务耗时；实际吞吐为相同任务字节除以外层耗时。时间比=AURA-core/对照，低于 1 较快。", "",
           "95% 区间按运行块 bootstrap；双侧符号翻转检验假设零假设下配对差对称，主比较 AURA 对 LRU/LFU 跨场景作为一个家族，其他每个组件跨场景各为预先定义的家族，家族内 p 值作 Holm 校正；不声称控制整篇论文的总体错误率。区间本身未经多重比较校正。", "",
           "| 场景 | 对照/消融 | n | AURA 秒 / MiB/s | 对照 秒 / MiB/s | 时间比 [95% CI] | 判定 |",
           "|---|---|---:|---:|---:|---|---|"]
    for r in rows:
        ci="未估计" if r["ci95"][0] is None else f"{r['ci95'][0]:.3f}, {r['ci95'][1]:.3f}"
        lines.append(f"| {r['scenario']} | {r['treatment']} / {r['baseline']} | {r['n']} | {r['aura_wall_s']:.3f} / {r['aura_mib_s']:.2f} | {r['baseline_wall_s']:.3f} / {r['baseline_mib_s']:.2f} | {r['time_ratio']:.3f} [{ci}] | {r['verdict']} |")
    lines += ["", "## 组件协同", "", "四格交互只检验价值淘汰与亲和放置，不能替代完整 RobustBenefit 与 independent 控制器比较。", "", json.dumps(interactions,ensure_ascii=False,indent=2), "",
              f"失败记录数：{len(failures)}。没有出现的场景/对照不是通过，而是尚无结果。", "",
              "## 解释边界", "", "输入为合成存储 trace，GPU 为逻辑缓存域；本表不证明真实推理 TTFT、真实 GPU 扩展性或完整 Python 联合模型在 C++ 中的性能。"]
    (root/"evidence-report.md").write_text("\n".join(lines)+"\n")
    return rows


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("root",type=Path)
    analyze(p.parse_args().root)
