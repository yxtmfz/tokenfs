from pathlib import Path
import json,shutil,hashlib,sys
root=Path(__file__).resolve().parent;tag,num=sys.argv[1:3];repo=root/'tokenfs-eval';data=root/(tag+'-data');load=lambda p:json.loads(p.read_text())
review=load(root/(tag+'-review.json'));assert review['passed']
dest=repo/'reports/latest/paper-experiments'/f'{num}_{tag.replace("-","_")}'
for folder in ['raw','provenance','validation']:(dest/folder).mkdir(parents=True,exist_ok=True)
for name in ['manifest','batch-audit','summary','comparisons']:shutil.copy2(data/'development'/f'{name}.json',dest/f'{name}.json')
for source,target in [(root/(tag+'-evidence.tar.gz'),'raw/cn7-evidence.tar.gz'),(root/(tag+'-source.tar.gz'),'provenance/source.tar.gz'),(root/(tag+'-review.json'),'validation/independent-review.json'),(root/'review-focused-hpj.py','validation/review-focused-hpj.py'),(data/'provenance/freeze.json','provenance/freeze.json'),(data/'provenance/ctest.log','validation/ctest.log'),(root/(tag+'-source')/'docs'/f'{tag}-plan.md','provenance/plan.md')]:shutil.copy2(source,dest/target)
for name in ['build','launch','collect','poll']:shutil.copy2(root/f'{name}-{tag}.sh',dest/f'provenance/{name}.sh')
for name in ['build','launch','collection','download']:shutil.copy2(root/f'{tag}-{name}.json',dest/f'provenance/{name}.json')
if not review['speed_evidence']:
 for n in [tag+'-profile.json','analyze-contention.py']:shutil.copy2(root/n,dest/'validation'/n)
 md='''# 移动热点复制路径诊断（五组，开启探针）\n\n仅用于定位，不作为最终速率证据。保持原始文件不改：继承的 comparisons.json 中 interpretation 字段误写 uninstrumented；实际 config.json 明确 profile_control_path=true 并含 request_trace_path。独立复核明确 speed_evidence=false，原始 pilot_screen 标志不得用作性能验收。\n\n|版本|每次复制总耗时 ms|其中校验 ms|其中写入 ms|每次打开 ms|每次遥测刷新 ms|\n|---|---:|---:|---:|---:|---:|\n'''
 for r in load(root/(tag+'-profile.json')):
  md+=f"|{r['strategy']}|{r['copy_mean_ms']:.3f}|{r['copy_verify_mean_ms']:.3f}|{r['copy_io_mean_ms']:.3f}|{r['all_means']['daemon_open_ms']:.3f}|{r['all_means']['metric_flush_ms']:.3f}|\n"
 md+='\n复制阶段的校验占比约81%。下一步为完整只读捕获数据的逐字节目标读回验证，保留源身份与全长度检查。不能由一次探针数据推导全部顺序波动的原因。\n'
else:
 for n in ['exactverify-hpj-correctness-review.json','integrated-hpj-exactverify-local-tests.log','integrated-hpj-exactverify-correctness-run.json','review-exactverify-correctness.py','run-exactverify-hpj-correctness.sh']:
  shutil.copy2(root/n,dest/'validation'/n)
 m=load(dest/'manifest.json');bs=m['spec']['blocks'];variants=bs[0]['variants'];rs={v:[load(data/'development'/b['id']/v/'result.json') for b in bs] for v in variants}
 aggregate=lambda v:sum(r['logical_bytes'] for r in rs[v])/1048576/sum(r['job_wall_s'] for r in rs[v])
 pairs=load(dest/'comparisons.json');rows=[]
 md='''# 移动热点：精确读回校验修复后的四张表\n\n本轮5组探针定位＋10组无探针测速，另有480次SHA256内容检查。测速只有移动热点3293，相同576条请求、2MiB对象、24MiB磁盘和4MiB共享捕获预算，五个版本先倒序后正序。每轮从空项目缓存开始；同一二进制，同一Full用于所有比较，前三张只关闭一个模块。\n\n固定热点保留为稳定负载对照，均匀随机保留为不可预测边界；本轮未重测这两个负载，不能把旧二进制的结果当作此版验证。此前全部数据保留在报告55。\n\n修复：源捕获已完整且不可变时，完整读回复制目标并逐字节比较，检查大小与目标身份未变、源身份仍有效；其余复制继续原有校验。所有版本共用，容量、持久化和策略公式不变。这是执行优化，不单列新创新。\n\n'''
 for title,v in [('创新点一：热点时变估值','NoHotspot'),('创新点二：跨逻辑域放置','NoAffinity'),('创新点三：联合准入','NoJoint'),('整体性能：共享SIEVE','PoolSIEVE1')]:
  pp=[next(p for p in pairs if p['block']==b['id'] and p['baseline']==v) for b in bs]
  md+=f'## {title}\n\n|轮次|Full MiB/s|对照 MiB/s|吞吐提升|p99变化|排空吞吐提升|机制有效|严格筛选|\n|---|---:|---:|---:|---:|---:|---|---|\n'
  for i,p in enumerate(pp):
   md+=f"|{i+1}|{rs['Full'][i]['effective_mib_s']:.3f}|{rs[v][i]['effective_mib_s']:.3f}|{p['gain_pct']:+.3f}%|{p['p99_change_pct']:+.3f}%|{p['drain_gain_pct']:+.3f}%|{p['mechanism_active']}|{p['pilot_screen']}|\n"
  gain=(aggregate('Full')/aggregate(v)-1)*100
  md+=f"\n合并速率（总字节÷总耗时）：Full **{aggregate('Full'):.3f} MiB/s**，对照 **{aggregate(v):.3f} MiB/s**，提升 **{gain:+.3f}%**。\n\n"
  rows.append(dict(baseline=v,full_mib_s=aggregate('Full'),baseline_mib_s=aggregate(v),gain_pct=gain,per_run_gain_pct=[p['gain_pct'] for p in pp],per_run_p99_change_pct=[p['p99_change_pct'] for p in pp],mechanism_active_both=all(p['mechanism_active'] for p in pp),passes_both=all(p['pilot_screen'] for p in pp)))
 md+='速率越高越好，p99变化越低越好。严格筛选保留正吞吐、排空吞吐不降、p99不增、机制实际改变的联合条件；合并平均不能覆盖某轮负值。两轮同一开发输入只能做描述性小样本筛选，不能证明统计显著、真实多GPU通信收益或泛化。\n'
 roll=dict(passed=True,speed_runs=10,requests=5760,correctness_requests=480,binary_sha256=m['binary_sha256'],comparisons=rows,all_gates_both_orders=all(r['passes_both'] for r in rows),scenarios_tested=['moving_shared'],limits='Two execution orders of one known input; no statistical confirmation or physical GPU evidence.')
 (root/'exactverify-hpj-rollup.json').write_text(json.dumps(roll,indent=2)+'\n');(dest/'rollup.json').write_text(json.dumps(roll,indent=2)+'\n')
 (root.parent/'outputs/TokenFS移动热点校验优化四表.md').write_text(md)
(dest/'README.md').write_text(md)
files=sorted(f for f in dest.rglob('*') if f.is_file() and f.name!='SHA256SUMS');(dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(dest))+'\n' for f in files));print(dest)
