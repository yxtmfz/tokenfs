#!/usr/bin/env python3
"""Offline, audited tables/figures; never participates in policy decisions."""
from __future__ import annotations
import argparse
import csv
import json
import statistics
from pathlib import Path

from evidence_benchmark import dump, MIB
from evidence_report import interval
from measured_study import report


def csv_file(path, rows):
    if not rows:
        return
    with path.open('w', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def generate(root, figures=False):
    summaries, comparisons=report(root)
    manifest=json.loads((root/'manifest.json').read_text())
    mechanisms=[]; segments=[]; interactions={}
    for block in manifest['spec']['blocks']:
        results={}
        for name in block['variants']:
            case=root/block['id']/name
            result=json.loads((case/'result.json').read_text());results[name]=result
            metrics=result['metrics']
            events=json.loads((case/'policy-events.json').read_text())
            rows=json.loads((case/'requests.json').read_text())
            mechanisms.append(dict(block=block['id'],scenario=block['scenario'],strategy=name,
                admissions=sum(e['action']=='ADMIT' for e in events),
                evictions=metrics.get('evict_count',0),
                shift_resets=metrics.get('measured_shift_resets',0),
                reject_no_reuse=metrics.get('measured_precheck_no_reuse',0),
                reject_copy_cost=metrics.get('measured_precheck_copy_cost',0),
                reject_victim_loss=metrics.get('measured_precheck_victim_loss',0),
                local_fraction=metrics.get('read_local_bytes',0)/result['logical_bytes'],
                copy_mib=sum(metrics.get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/MIB,
                with_drain_s=result['completed_with_background_s'],
                request_p50_ms=result['request_p50_s']*1000,
                request_p99_ms=result['request_p99_s']*1000,
                daemon_cpu_s=result['daemon_cpu_s'],daemon_peak_rss_kib=result['daemon_peak_rss_kib']))
            if rows and all('issued_s' in r and 'completed_s' in r for r in rows):
                for part in range(4):
                    selected=rows[part*len(rows)//4:(part+1)*len(rows)//4]
                    elapsed=selected[-1]['completed_s']-selected[0]['issued_s']
                    segments.append(dict(block=block['id'],scenario=block['scenario'],strategy=name,
                        quarter=part+1,requests=len(selected),elapsed_s=elapsed,
                        mib_s=sum(r['bytes'] for r in selected)/MIB/elapsed))
        names=['AURA-adaptive','AURA-no-admission','AURA-no-value','AURA-no-joint']
        if all(n in results for n in names):
            a,b,c,d=[results[n]['job_wall_s'] for n in names]
            key=(block['scenario'],block['quota_mib'],block['requests'],block['shard_mib'])
            interactions.setdefault(key,[]).append(a-b-c+d)
    interaction_rows=[dict(scenario=k[0],quota_mib=k[1],requests=k[2],shard_mib=k[3],n=len(v),
        mean_interaction_s=statistics.mean(v),ci95=interval(v),
        definition='T(full)-T(no-admission)-T(no-value)+T(no-joint); negative favors interaction; exploratory')
        for k,v in interactions.items()]
    for name,rows in [('mechanisms',mechanisms),('segments',segments),('interactions',interaction_rows)]:
        dump(root/(name+'.json'),rows);csv_file(root/(name+'.csv'),rows)
    csv_file(root/'summary.csv',summaries);csv_file(root/'paired-comparisons.csv',comparisons)
    lines=['# Measured-policy evidence', '',
        f"Stage: {manifest['spec']['stage']}. Batch: {root.name}. All expected runs passed audit.", '',
        'Time ratio = AURA-adaptive/reference; less than one is faster. Actual throughput is logical MiB / outer wall time.', '',
        '| Scenario | Quota MiB | Requests | Reference | n | Time ratio [95% CI] | Holm p | Verdict |',
        '|---|---:|---:|---|---:|---|---:|---|']
    for row in comparisons:
        ci=row['ci95'];bounds='unavailable' if ci[0] is None else f'{ci[0]:.4f}, {ci[1]:.4f}'
        p='unavailable' if row['p_holm'] is None else f"{row['p_holm']:.5g}"
        lines.append(f"| {row['scenario']} | {row['quota_mib']} | {row['requests']} | {row['baseline']} | {row['n']} | {row['time_ratio']:.4f} [{bounds}] | {p} | {row['verdict']} |")
    lines += ['', '## Absolute performance and resource cost', '',
        '| Scenario | Quota MiB | Requests | Strategy | n | Mean wall s | Mean MiB/s | Copied MiB | Daemon CPU s | Peak RSS KiB |',
        '|---|---:|---:|---|---:|---:|---:|---:|---:|---:|']
    for row in summaries:
        lines.append(f"| {row['scenario']} | {row['quota_mib']} | {row['requests']} | {row['strategy']} | {row['n']} | {row['mean_wall_s']:.4f} | {row['mean_mib_s']:.3f} | {row['mean_copy_mib']:.2f} | {row['mean_cpu_s']:.3f} | {row['mean_rss_kib']:.1f} |")
    lines += ['', '## Interpretation', '',
        'The primary family comprises LRU, LFU and RecentLFU comparisons across the scenes in this batch; other families are per-component. Intervals are unadjusted paired bootstrap intervals; p-values use Holm correction within each family. No component is necessary merely because its point estimate is favorable. Inspect mechanisms.json for actual trigger counts.', '',
        'Report paired-comparisons.json with_drain_ratio alongside foreground time. mechanisms.json contains p50/p99, CPU, RSS and copying for every run. segments.json gives descriptive throughput by request-index quarter; quarters are not independent replication units. interactions.json is an exploratory four-cell comparison, not a full RobustBenefit test.', '',
        'Foreground timing excludes initialization and post-run verification. Copy payload is not physical wire/disk traffic. Logical cache domains are not physical GPUs. Public traces preserve block identity/order with synthetic normalized bytes; saturated replay is not full inference or the original concurrency. Small-n development/supplementary runs do not support confirmatory claims. Negative and uncertain results are retained.']
    (root/'measured-report.md').write_text('\n'.join(lines)+'\n')
    if figures:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        out=root/'figures';out.mkdir(exist_ok=True)
        main=[r for r in comparisons if r['baseline'] in ['LRU-equal','LFU-equal','RecentLFU-admit','RemoteOnly']]
        fig,ax=plt.subplots(figsize=(9,max(4,len(main)*.3)))
        for i,r in enumerate(main):
            ci=r['ci95'];color='#2066a8' if r['verdict']=='faster' else '#bb4b38' if r['verdict']=='slower' else '#666666'
            ax.plot(r['time_ratio'],i,'o',color=color,markersize=4)
            if ci[0] is not None:ax.plot(ci,[i,i],color=color)
        ax.set_yticks(range(len(main)),[f"{r['scenario']} q={r['quota_mib']} N={r['requests']} / {r['baseline']}" for r in main],fontsize=7)
        ax.axvline(1,color='black',linestyle='--',linewidth=.8);ax.invert_yaxis()
        ax.set_xlabel('Paired geometric mean time ratio (AURA-adaptive/reference), 95% CI')
        ax.set_title(f"{root.name}: {manifest['spec']['stage']}")
        ax.grid(axis='x',alpha=.2);fig.tight_layout()
        for suffix in ['png','svg','pdf']:fig.savefig(out/f'time-ratios.{suffix}',dpi=180)
        plt.close(fig)
    return len(summaries),len(comparisons)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path)
    parser.add_argument('--figures',action='store_true');args=parser.parse_args()
    print(generate(args.root,args.figures))
