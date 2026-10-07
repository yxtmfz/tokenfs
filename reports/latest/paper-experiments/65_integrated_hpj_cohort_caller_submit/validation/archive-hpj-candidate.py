from pathlib import Path
import json,shutil,hashlib,sys
root=Path(__file__).resolve().parent;tag,num=sys.argv[1:3];repo=root/'tokenfs-eval';data=root/(tag+'-data');load=lambda p:json.loads(p.read_text())
review=load(root/(tag+'-review.json'));assert review['passed'] and review['speed_evidence']
dest=repo/'reports/latest/paper-experiments'/f'{num}_{tag.replace("-","_")}'
for folder in ['raw','provenance','validation']:(dest/folder).mkdir(parents=True,exist_ok=True)
for name in ['manifest','batch-audit','summary','comparisons']:shutil.copy2(data/'development'/f'{name}.json',dest/f'{name}.json')
for source,target in [(root/(tag+'-evidence.tar.gz'),'raw/cn7-evidence.tar.gz'),(root/(tag+'-source.tar.gz'),'provenance/source.tar.gz'),(root/(tag+'-review.json'),'validation/independent-review.json'),(root/'review-focused-hpj.py','validation/review-focused-hpj.py'),(data/'provenance/freeze.json','provenance/freeze.json'),(data/'provenance/ctest.log','validation/ctest.log'),(root/(tag+'-source')/'docs'/f'{tag}-plan.md','provenance/plan.md'),(root/'archive-hpj-candidate.py','validation/archive-hpj-candidate.py')]:shutil.copy2(source,dest/target)
for name in ['build','launch','collect','poll']:shutil.copy2(root/f'{name}-{tag}.sh',dest/f'provenance/{name}.sh')
for name in ['build','launch','collection','download']:shutil.copy2(root/f'{tag}-{name}.json',dest/f'provenance/{name}.json')
m=load(dest/'manifest.json');bs=m['spec']['blocks'];variants=bs[0]['variants'];rs={v:[load(data/'development'/b['id']/v/'result.json') for b in bs] for v in variants}
aggregate=lambda v:sum(r['logical_bytes'] for r in rs[v])/1048576/sum(r['job_wall_s'] for r in rs[v])
pairs=load(dest/'comparisons.json');rows=[]
md=f'# 移动热点两轮四比较：{tag}\n\n固定输入3293、576条2MiB请求、24MiB磁盘、4MiB共享捕获。五版本执行顺序完全反转，前三项为Full仅关闭一个模块，第四项为等能力共享SIEVE。保留本候选所有10次运行；两轮使用同一Full作全部比较。\n\n'
for title,v in [('创新点一：热点估值','NoHotspot'),('创新点二：跨域放置','NoAffinity'),('创新点三：联合准入','NoJoint'),('整体性能：共享SIEVE','PoolSIEVE1')]:
 pp=[next(p for p in pairs if p['block']==b['id'] and p['baseline']==v) for b in bs]
 md+=f'## {title}\n\n|轮次|Full MiB/s|对照 MiB/s|吞吐提升|p99变化|排空吞吐提升|机制有效|原严格筛选|\n|---|---:|---:|---:|---:|---:|---|---|\n'
 for i,p in enumerate(pp):md+=f"|{i+1}|{rs['Full'][i]['effective_mib_s']:.3f}|{rs[v][i]['effective_mib_s']:.3f}|{p['gain_pct']:+.3f}%|{p['p99_change_pct']:+.3f}%|{p['drain_gain_pct']:+.3f}%|{p['mechanism_active']}|{p['pilot_screen']}|\n"
 gain=(aggregate('Full')/aggregate(v)-1)*100
 md+=f"\n总字节÷总耗时：Full {aggregate('Full'):.3f}、对照 {aggregate(v):.3f} MiB/s，提升 {gain:+.3f}%。\n\n"
 rows.append(dict(baseline=v,full_mib_s=aggregate('Full'),baseline_mib_s=aggregate(v),gain_pct=gain,per_run_gain_pct=[p['gain_pct'] for p in pp],per_run_p99_change_pct=[p['p99_change_pct'] for p in pp],mechanism_active_both=all(p['mechanism_active'] for p in pp),passes_both=all(p['pilot_screen'] for p in pp)))
counts=[];md+='## 机制计数\n\n|轮次|版本|远端MiB|复制次数|淘汰次数|新对象先验规划数|\n|---|---|---:|---:|---:|---:|\n'
for i,b in enumerate(bs):
 for v in variants:
  metric=rs[v][i]['metrics'];c=dict(round=i+1,strategy=v,remote_mib=metric.get('read_remote_bytes',0)/1048576,copies=metric.get('promote_count',0)+metric.get('cross_gpu_replica_create_count',0),evictions=metric.get('evict_count',0),prior_plans=metric.get('measured_cohort_prior_plans',0));counts.append(c)
  md+=f"|{i+1}|{v}|{c['remote_mib']}|{c['copies']}|{c['evictions']}|{c['prior_plans']}|\n"
allpositive=all(g>0 for r in rows for g in r['per_run_gain_pct']);strict=all(r['passes_both'] for r in rows)
md+=f'\n两轮四比较吞吐全部为正：**{allpositive}**。原包含p99、排空吞吐和机制的严格条件全部通过：**{strict}**。\n\n正方向仅描述这两轮开发输入，不代表统计显著或真实GPU收益。没有重新测试固定热点、均匀随机；历史负值保持原样。\n'
roll=dict(passed=True,speed_runs=10,requests=5760,binary_sha256=m['binary_sha256'],comparisons=rows,mechanism_counts=counts,two_orders_four_throughput_gains=allpositive,all_gates_both_orders=strict,scenarios_tested=['moving_shared'],limits='Two execution orders of one known input; no statistical confirmation or physical GPU evidence.')
(root/(tag+'-rollup.json')).write_text(json.dumps(roll,indent=2)+'\n');(dest/'rollup.json').write_text(json.dumps(roll,indent=2)+'\n');(dest/'README.md').write_text(md)
(dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(dest))+'\n' for f in sorted(dest.rglob('*')) if f.is_file() and f.name!='SHA256SUMS'))
print(json.dumps(roll,indent=2))
