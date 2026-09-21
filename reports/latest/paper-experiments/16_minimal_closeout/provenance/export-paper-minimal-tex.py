"""Export the four evidence tables; requires only Python's standard library."""
from pathlib import Path
import argparse,json

p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
read=lambda rel:json.loads((a.report/rel).read_text())
s=read('confirmation/summary.json');cs=read('confirmation/comparisons.json');sens=read('sensitivity/summary.json');sc=read('sensitivity/comparisons.json')
labels={'static_affinity':'Stable hotspots','hot_shift':'Hotspot shifts','public_toolagent':'Public tool-agent replay','uniform':'Uniform random','hot_shift_q16':'16 MiB/domain','hot_shift_long':'1536 requests'}
def tab(caption,label,headers,rows):
 return '\n'.join([r'\begin{table*}[t]',r'\centering',r'\small',r'\caption{'+caption+'}',r'\label{'+label+'}',r'\begin{tabular}{l'+'r'*(len(headers)-1)+'}',r'\toprule',' & '.join(headers)+r' \\',r'\midrule']+[' & '.join(map(str,row))+r' \\' for row in rows]+[r'\bottomrule',r'\end{tabular}',r'\end{table*}',''])
lookup=lambda scene,name:next(x for x in s if x['scenario']==scene and x['strategy']==name)
intro=r'''% TokenFS minimal storage study; generated from report 16 JSON.
% Requires \usepackage{booktabs}. Insert into an IEEE journal manuscript.
% All performance values are actual storage replay rates, not GPU/LLM results.
% H: shift adaptation. J: victim-loss-aware admission. Affinity decisions off;
% the common legacy metadata path remains present in all arms.
% No old-version data are mixed into these tables.
'''
tables=[tab('Overall storage throughput (MiB/s, arithmetic means of 12 runs per cell). All arms share the same binary, input bytes, per-domain quota, and storage path.','tab:tokenfs-overall',['Scene','RemoteOnly','LRU','SIEVE','SIEVE-2hit','RecentLFU','Full (H+J)'],[[labels[scene]]+[f"{lookup(scene,name)['mib_s']:.2f}" for name in ['RemoteOnly','LRU','SIEVE','SIEVE-2hit','RecentLFU','Full']] for scene in ['static_affinity','hot_shift','public_toolagent','uniform']])]
rows=[]
for c in cs:
 if c['family']!='mechanism':continue
 rows.append([labels[c['scenario']],c['baseline'],f"{lookup(c['scenario'],'Full')['mib_s']:.2f}",f"{lookup(c['scenario'],c['baseline'])['mib_s']:.2f}",f"{c['throughput_change_pct']:+.2f}\\%",f"[{c['ci95'][0]:.4f}, {c['ci95'][1]:.4f}]",f"{c['p_holm']:.6f}",c['verdict']])
tables.append(tab('Targeted ablations (12 paired runs each). Rate changes use the inverse paired geometric elapsed-time ratio; they need not equal ratios of arithmetic mean rates. Confidence intervals are unadjusted; p-values use Holm adjustment within the three-test mechanism family.','tab:tokenfs-ablation',['Scene','Ablation','Full MiB/s','Ablation MiB/s','Rate change',r'Time-ratio 95\% CI','Holm $p$','Verdict'],rows))
rows=[]
for x in s:
 if x['strategy'] not in ['RemoteOnly','LRU','SIEVE','SIEVE-2hit','RecentLFU','Full']:continue
 rows.append([labels[x['scenario']]+' / '+x['strategy']]+[f'{v:.2f}' for v in [x['wall_s'],x['with_drain_s'],x['cpu_s'],x['rss_kib']/1024,x['p99_ms'],x['remote_mib'],x['copy_mib']]])
tables.append(tab('Descriptive resource and I/O costs (per-run means). CPU/RSS cover the daemon; p99 is the mean of per-run empirical p99. Copy and remote-read counts are logical payload bytes. Queue drain is not physical persistence.','tab:tokenfs-cost',['Scene / strategy','Foreground s','With drain s','CPU s','RSS MiB','p99 ms','Remote MiB','Copy MiB'],rows))
rows=[]
for c in sc:
 at=lambda name:next(x for x in sens if x['scenario']==c['scenario'] and x['strategy']==name)
 rows.append([labels[c['scenario']],c['n'],f"{at('RecentLFU')['mib_s']:.2f}",f"{at('Full')['mib_s']:.2f}",f"{c['throughput_change_pct']:+.2f}\\%",f"{c['with_drain_ratio']:.4f}"])
tables.append(tab('Small descriptive boundary checks at hotspot shifts. Three new paired seeds per condition. The long sequence keeps four phases and thus increases their dwell length. These results do not establish general scalability or statistically confirmed robustness.','tab:tokenfs-boundaries',['Condition','$n$/arm','RecentLFU MiB/s','Full MiB/s','Paired rate change','With-drain time ratio'],rows))
a.output.write_text(intro+'\n'+'\n'.join(tables))
