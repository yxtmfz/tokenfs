#!/usr/bin/env python3
"""Describe observed actions; action differences alone do not prove causal speed gains."""
import argparse
import json
from pathlib import Path
import statistics
from evidence_audit import audit


def analyze(root):
    if not audit(root)['passed']:
        raise ValueError('batch audit failed')
    manifest=json.loads((root/'manifest.json').read_text())
    pairs=json.loads((root/'paired-comparisons.json').read_text())
    rows=[]
    for pair in pairs:
        if pair['baseline'] in {'RemoteOnly','LRU-equal','LFU-equal'}:
            continue
        unchanged=0;counts=[];gain_rejections=0;cross_calls=0
        for seed in manifest['args']['seeds']:
            block=root/f"{pair['scenario']}-seed-{seed}"
            groups=[]
            for strategy in [pair['treatment'],pair['baseline']]:
                result=json.loads((block/strategy/'result.json').read_text())
                events=json.loads((block/strategy/'policy-events.json').read_text())
                # Signed scores in frozen formal-02 telemetry are not reliable; do not use them.
                actions=[(e['action'],e['logical_path'],e['gpu_id'],e['bytes']) for e in events]
                m=result['metrics']
                groups.append((actions,m))
            unchanged += groups[0][0] == groups[1][0]
            m=groups[0][1]
            gain_rejections += sum(m.get(k,0) for k in ['promote_skip_low_reuse','promote_skip_low_value','promote_skip_low_benefit'])
            cross_calls += m.get('affinity_cross_gpu_caller_count',0)
            counts.append([sum(g[1].get(k,0) for k in ['promote_bytes','prefetch_bytes','cross_gpu_replica_create_bytes'])/1048576 for g in groups])
        note='动作差异可能包含异步时序变化，不能单独视为目标算法的因果贡献。'
        if pair['baseline']=='no-gain' and gain_rejections==0 and cross_calls==0:
            note='未观察到收益准入拒绝，且无跨域调用；本场景不能识别准入筛选收益。'
        rows.append(dict(scenario=pair['scenario'],treatment=pair['treatment'],baseline=pair['baseline'],n=len(counts),
                         identical_action_sequence_pairs=unchanged,
                         treatment_copy_mib=statistics.mean(x[0] for x in counts),baseline_copy_mib=statistics.mean(x[1] for x in counts),
                         treatment_owner_gain_rejections=gain_rejections,treatment_cross_gpu_calls=cross_calls,note=note))
    (root/'mechanism-summary.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
    lines=['# 机制触发与动作审查','',
           '此表只描述记录中实际发生的动作，不能把异步时序造成的序列差异解释为纯算法因果效应。比较忽略 score、reason 和 seq，只保留 action/path/GPU/bytes。formal-02 的负 value score 在日志中发生无符号转换；排序使用独立 int64 分数，动作选择与 wall 不受这一记录格式错误影响。原始 score 不改写、不用于模型项分析。','',
           '| 场景 | 比较 | 动作序列相同的配对数 | 复制 MiB（处理/对照） | 解释 |',
           '|---|---|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['scenario']} | {r['treatment']} / {r['baseline']} | {r['identical_action_sequence_pairs']}/{r['n']} | {r['treatment_copy_mib']:.1f} / {r['baseline_copy_mib']:.1f} | {r['note']} |")
    (root/'mechanism-report.md').write_text('\n'.join(lines)+'\n')
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path)
    analyze(p.parse_args().root)
