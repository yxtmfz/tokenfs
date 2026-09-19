#!/usr/bin/env python3
"""Offline, audited tables/figures; never participates in policy decisions."""
from __future__ import annotations
import argparse
import csv
import json
import statistics
from pathlib import Path

from evidence_benchmark import dump, MIB, percentile
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
    analysis_label=manifest['spec']['stage']
    if analysis_label=='confirmation' and max((r['n'] for r in comparisons),default=0)<10:
        analysis_label='descriptive supplement (small n; no confirmatory claim)'
    mechanisms=[]; segments=[]; interactions={};by_case={}
    for block in manifest['spec']['blocks']:
        results={}
        for name in block['variants']:
            case=root/block['id']/name
            result=json.loads((case/'result.json').read_text());results[name]=result
            metrics=result['metrics']
            events=json.loads((case/'policy-events.json').read_text())
            rows=json.loads((case/'requests.json').read_text())
            by_case[(block['id'],name)]=(result,events)
            paced=[r for r in rows if 'release_s' in r]
            mechanisms.append(dict(block=block['id'],scenario=block['scenario'],strategy=name,
                admissions=sum(e['action']=='ADMIT' for e in events),
                calibrated_admissions=sum(e['action']=='ADMIT' and 'calibrated=1' in e['reason'] for e in events),
                prior_admissions=sum(e['action']=='ADMIT' and 'calibrated=0' in e['reason'] for e in events),
                calibration_annotation_unavailable=sum(e['action']=='ADMIT' and 'calibrated=' not in e['reason'] for e in events),
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
                arrival_to_completion_p99_ms=percentile([max(0,r['completed_s']-r['release_s'])*1000 for r in paced],.99) if paced else None,
                arrival_to_issue_p99_ms=percentile([max(0,r['issued_s']-r['release_s'])*1000 for r in paced],.99) if paced else None,
                daemon_cpu_s=result['daemon_cpu_s'],daemon_peak_rss_kib=result['daemon_peak_rss_kib']))
            if rows and all('issued_s' in r and 'completed_s' in r for r in rows):
                for part in range(4):
                    selected=rows[part*len(rows)//4:(part+1)*len(rows)//4]
                    start_index=part*len(rows)//4
                    # Include the boundary idle gap, especially in paced replay.
                    start_time=rows[start_index-1]['completed_s'] if start_index else 0
                    elapsed=selected[-1]['completed_s']-start_time
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
    component_rows=[]
    for row in comparisons:
        name=row['baseline']
        if not name.startswith('AURA-'):continue
        observed=0;different_actions=0;matched=0
        for b in manifest['spec']['blocks']:
            if not all(b.get(k,default)==row[k] for k,default in [('scenario',None),('quota_mib',None),('requests',None),('shard_mib',None),('window',128),('paced',False)]):continue
            if name not in b['variants'] or 'AURA-adaptive' not in b['variants']:continue
            a,ae=by_case[(b['id'],'AURA-adaptive')];other,oe=by_case[(b['id'],name)]
            m=a['metrics'];matched+=1
            actions=lambda es:[(e['action'],e['logical_path'],e['gpu_id']) for e in es if e['action'] in ['EVICT','PROMOTE_READY','REPLICATE_READY']]
            different_actions+=actions(ae)!=actions(oe)
            if name=='AURA-no-shift':active=m.get('measured_shift_resets',0)>0
            elif name=='AURA-no-aging':active=b['requests']>b.get('window',128) or m.get('measured_shift_resets',0)>0
            elif name=='AURA-synchronous':active=m.get('background_submitted',0)>0
            elif name in ['AURA-no-value','AURA-no-size']:
                active=m.get('evict_count',0)>0 or other['metrics'].get('evict_count',0)>0
                if name=='AURA-no-size':
                    sizes=json.loads((root/b['id']/'objects.json').read_text())['sizes_mib']
                    active=active and len(set(sizes.values()))>1
            elif name=='AURA-no-cost':active=m.get('measured_precheck_copy_cost',0)>0 or any(e['action']=='ADMIT' and 'calibrated=1' in e['reason'] for e in ae)
            elif name in ['AURA-no-admission','AURA-no-joint']:active=sum(m.get('measured_precheck_'+k,0) for k in ['no_reuse','copy_cost','victim_loss'])>0
            else:active=False
            observed+=bool(active)
        component_rows.append(dict(scenario=row['scenario'],quota_mib=row['quota_mib'],requests=row['requests'],window=row['window'],baseline=name,n=matched,
            blocks_with_relevant_activity=observed,blocks_with_different_copy_or_eviction_sequence=different_actions,
            interpretation='target mechanism unobserved; no component-necessity claim' if observed==0 else 'activity observed, not by itself proof of a speed contribution'))
    for name,rows in [('mechanisms',mechanisms),('segments',segments),('interactions',interaction_rows)]:
        dump(root/(name+'.json'),rows);csv_file(root/(name+'.csv'),rows)
    dump(root/'component-evidence.json',component_rows);csv_file(root/'component-evidence.csv',component_rows)
    csv_file(root/'summary.csv',summaries);csv_file(root/'paired-comparisons.csv',comparisons)
    lines=['# Measured-policy evidence', '',
        f"Analysis: {analysis_label}. Recorded stage: {manifest['spec']['stage']}. Batch: {root.name}. All expected runs passed audit.", '',
        'Time ratio = AURA-adaptive/reference; less than one is faster. Actual throughput is logical MiB / outer wall time.', '',
        '| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Reference | n | Time ratio [95% CI] | Holm p | Verdict |',
        '|---|---:|---:|---:|---:|---|---|---:|---|---:|---|']
    for row in comparisons:
        ci=row['ci95'];bounds='unavailable' if ci[0] is None else f'{ci[0]:.4f}, {ci[1]:.4f}'
        p='unavailable' if row['p_holm'] is None else f"{row['p_holm']:.5g}"
        lines.append(f"| {row['scenario']} | {row['quota_mib']} | {row['requests']} | {row['shard_mib']} | {row['window']} | {row['paced']} | {row['baseline']} | {row['n']} | {row['time_ratio']:.4f} [{bounds}] | {p} | {row['verdict']} |")
    lines += ['', '## Absolute performance and resource cost', '',
        '| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Strategy | n | Mean wall s | Mean MiB/s | Copied MiB | Daemon CPU s | Peak RSS KiB |',
        '|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|']
    for row in summaries:
        lines.append(f"| {row['scenario']} | {row['quota_mib']} | {row['requests']} | {row['shard_mib']} | {row['window']} | {row['paced']} | {row['strategy']} | {row['n']} | {row['mean_wall_s']:.4f} | {row['mean_mib_s']:.3f} | {row['mean_copy_mib']:.2f} | {row['mean_cpu_s']:.3f} | {row['mean_rss_kib']:.1f} |")
    lines += ['', '## Interpretation', '',
        'The primary family comprises LRU, LFU and RecentLFU comparisons across the scenes in this batch; other families are per-component. Intervals are unadjusted paired bootstrap intervals; p-values use Holm correction within each family. No component is necessary merely because its point estimate is favorable. Inspect mechanisms.json and component-evidence.json for actual activity and changed actions; untriggered components have no identified necessity even if timing differs.', '',
        'Report paired-comparisons.json with_drain_ratio alongside foreground time. mechanisms.json contains p50/p99 of individual object reads, CPU, RSS and copying for every run. In paced replay it also reports block arrival-to-issue and arrival-to-completion p99, including loader backlog; these are not inference TTFT. segments.json partitions time by request-index quarter, including boundary idle gaps; quarters are not independent replication units. interactions.json is an exploratory four-cell comparison, not a full RobustBenefit test.', '',
        'Foreground timing excludes initialization and post-run verification. Copy payload is not physical wire/disk traffic. Logical cache domains are not physical GPUs. Public traces preserve block identity/order with synthetic normalized bytes; saturated replay is not full inference or the original concurrency. Small-n development/supplementary runs do not support confirmatory claims. Negative and uncertain results are retained.']
    (root/'measured-report.md').write_text('\n'.join(lines)+'\n')
    if figures:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        out=root/'figures';out.mkdir(exist_ok=True)
        baselines=['RemoteOnly','LRU-equal','LFU-equal','RecentLFU-admit']
        selections=[('time-ratios',[r for r in comparisons if r['baseline'] in baselines]),
                    ('component-ratios',[r for r in comparisons if r['baseline'].startswith('AURA-')])]
        for title,selected in selections:
            if not selected:continue
            fig,ax=plt.subplots(figsize=(10,max(4,len(selected)*.3)))
            def inactive(r):
                return any(c['scenario']==r['scenario'] and c['quota_mib']==r['quota_mib'] and c['window']==r['window'] and c['baseline']==r['baseline'] and c['blocks_with_relevant_activity']==0 for c in component_rows)
            for i,r in enumerate(selected):
                ci=r['ci95'];color='#666666' if inactive(r) else '#2066a8' if r['verdict']=='faster' else '#bb4b38' if r['verdict']=='slower' else '#666666'
                ax.plot(r['time_ratio'],i,'o',color=color,markersize=4)
                if ci[0] is not None:ax.plot(ci,[i,i],color=color)
            ax.set_yticks(range(len(selected)),[f"{r['scenario']} q={r['quota_mib']} N={r['requests']} w={r['window']} {'paced' if r['paced'] else 'sat'} n={r['n']} / {r['baseline']}"+(' [inactive]' if inactive(r) else '') for r in selected],fontsize=7)
            ax.axvline(1,color='black',linestyle='--',linewidth=.8);ax.invert_yaxis()
            ax.set_xlabel('Paired time ratio (AURA-adaptive/reference); 95% intervals only when n >= 2')
            ax.set_title(f"{root.name}: {analysis_label}",fontsize=10)
            ax.grid(axis='x',alpha=.2);fig.tight_layout()
            for suffix in ['png','svg','pdf']:fig.savefig(out/f'{title}.{suffix}',dpi=180)
            plt.close(fig)
        # Absolute delivered throughput, with uncertainty across whole runs.
        fields=['scenario','quota_mib','requests','shard_mib','window','paced']
        groups=list(dict.fromkeys(tuple(r[k] for k in fields) for r in summaries))
        if len(groups)<=8:
            names=baselines+['AURA-adaptive'];colors=['#b6bec9','#e3ac59','#8aabc0','#81ad8b','#365d9b']
            fig,ax=plt.subplots(figsize=(max(8,len(groups)*1.7),5.5));width=.15
            for j,name in enumerate(names):
                xs=[];means=[];ex=[];em=[];lo=[];hi=[]
                for i,g in enumerate(groups):
                    values=[]
                    for b in manifest['spec']['blocks']:
                        key=tuple(b.get(k,128 if k=='window' else False if k=='paced' else None) for k in fields)
                        if key==g and (b['id'],name) in by_case:values.append(by_case[(b['id'],name)][0]['effective_mib_s'])
                    if not values:continue
                    mean=statistics.mean(values);ci=interval(values)
                    xs.append(i+(j-2)*width);means.append(mean)
                    if ci[0] is not None:
                        ex.append(xs[-1]);em.append(mean);lo.append(max(0,mean-ci[0]));hi.append(max(0,ci[1]-mean))
                ax.bar(xs,means,width,label=name,color=colors[j])
                if ex:ax.errorbar(ex,em,yerr=[lo,hi],fmt='none',color='black',capsize=2,linewidth=.7)
            ax.set_xticks(range(len(groups)),[f'{g[0]}\nq={g[1]}, N={g[2]}' for g in groups],rotation=25,ha='right',fontsize=8)
            ax.set_ylabel('Delivered MiB/s (logical bytes / outer wall time)')
            ax.set_title(f'{root.name}: mean throughput; intervals only when n >= 2')
            ax.legend(ncol=3,fontsize=8);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);fig.tight_layout()
            for suffix in ['png','svg','pdf']:fig.savefig(out/f'throughput.{suffix}',dpi=180)
            plt.close(fig)
    return len(summaries),len(comparisons)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path)
    parser.add_argument('--figures',action='store_true');args=parser.parse_args()
    print(generate(args.root,args.figures))
