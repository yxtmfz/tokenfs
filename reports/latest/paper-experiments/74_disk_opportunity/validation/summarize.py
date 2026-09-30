import json,math,statistics,sys
from pathlib import Path
root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
comparisons=json.loads((root/'comparisons.json').read_text())
scenes=['moving_shared','public_toolagent'];names={'moving_shared':'移动热点','public_toolagent':'公开回放'}
groups=[('创新点一：热点估值消融','NoHotspot'),('创新点二：亲和放置消融','NoAffinity'),('创新点三：联合决策消融','NoJoint'),('整体：共享 SIEVE 对比','PoolSIEVE1')]
allrows=[];parts=['# 第74轮：同批四张实验结果表\n','吞吐为总逻辑字节/总墙钟时间；p99为两次运行p99的中位数。吞吐变化为正、p99降低率为正才是改善。两轮双指标通过数要求每轮同时吞吐更高、p99更低。全部为同批已知输入的小规模开发验证。\n']
for title,baseline in groups+[('附：新旧完整版同批对比','OldFull')]:
 parts.extend(['## '+title+'\n','|场景|Full MiB/s|对照 MiB/s|吞吐变化|Full p99 ms|对照 p99 ms|p99降低|两轮双指标通过|严格通过|','|---|---:|---:|---:|---:|---:|---:|---:|---:|'])
 for scene in scenes:
  cases={arm:[json.loads(p.read_text()) for p in sorted(root.glob(scene+'-*/'+arm+'/result.json'))] for arm in ['Full',baseline]}
  assert all(len(v)==2 for v in cases.values())
  def rate(rs):return sum(r['logical_bytes'] for r in rs)/1048576/math.fsum(r['job_wall_s'] for r in rs)
  x,y=cases['Full'],cases[baseline];a,b=rate(x),rate(y)
  p,q=statistics.median(r['request_p99_s']*1000 for r in x),statistics.median(r['request_p99_s']*1000 for r in y)
  pairs=[r for r in comparisons if r['scenario']==scene and r['baseline']==baseline]
  assert len(pairs)==2
  dual=sum(r['gain_pct']>0 and r['p99_change_pct']<0 for r in pairs)
  strict=sum(r['pilot_screen'] for r in pairs)
  row=dict(scene=scene,baseline=baseline,full_mib_s=a,baseline_mib_s=b,gain_pct=(a/b-1)*100,full_p99_ms=p,baseline_p99_ms=q,p99_reduction_pct=(1-p/q)*100,dual_pass=dual,strict_pass=strict,rounds=pairs)
  allrows.append(row)
  parts.append(f"|{names[scene]}|{a:.3f}|{b:.3f}|{row['gain_pct']:+.3f}%|{p:.3f}|{q:.3f}|{row['p99_reduction_pct']:+.3f}%|{dual}/2|{strict}/2|")
 parts.append('')
parts+=['## 每轮结果（保留方向不一致项）\n','|场景/轮次|对照|吞吐变化|p99降低|排空吞吐变化|动作变化|双指标通过|','|---|---|---:|---:|---:|---|---|']
for r in comparisons:
 parts.append(f"|{r['block']}|{r['baseline']}|{r['gain_pct']:+.4f}%|{-r['p99_change_pct']:+.4f}%|{r['drain_gain_pct']:+.4f}%|{r['executed_actions_changed']}|{r['gain_pct']>0 and r['p99_change_pct']<0}|")
(out/'tables.md').write_text('\n'.join(parts)+'\n');(out/'table-values.json').write_text(json.dumps(allrows,indent=2)+'\n')
print('\n'.join(parts[:35]))
