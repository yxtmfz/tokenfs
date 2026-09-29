from pathlib import Path
import json,math,statistics
p=Path(__file__).resolve().parent;tag='integrated-hpj-cohort-caller-object';data=p/(tag+'-data/development')
load=lambda f:json.loads(f.read_text());m=load(data/'manifest.json');pairs=load(data/'comparisons.json');rows=[]
for scene in ['moving_shared','public_toolagent']:
 blocks=[b for b in m['spec']['blocks'] if b['scenario']==scene]
 def stats(v):
  rs=[load(data/b['id']/v/'result.json') for b in blocks]
  return dict(mib_s=sum(r['logical_bytes'] for r in rs)/1048576/math.fsum(r['job_wall_s'] for r in rs),p99_ms=statistics.median(r['request_p99_s']*1000 for r in rs),rates=[r['effective_mib_s'] for r in rs],tails=[r['request_p99_s']*1000 for r in rs],remote_mib=sum(r['metrics'].get('read_remote_bytes',0) for r in rs)/1048576,copies=sum(r['metrics'].get('read_fill_copy_count',0) for r in rs),cpu_s=math.fsum(r['daemon_cpu_s'] for r in rs))
 f=stats('Full')
 for v in ['NoHotspot','NoAffinity','NoJoint','PoolSIEVE1','OldFull']:
  b=stats(v);ps=[x for x in pairs if x['scenario']==scene and x['baseline']==v]
  rows.append(dict(scenario=scene,baseline=v,full=f,control=b,gain_pct=(f['mib_s']/b['mib_s']-1)*100,p99_change_pct=(f['p99_ms']/b['p99_ms']-1)*100,strict_passes=sum(x['pilot_screen'] for x in ps),pairs=ps))
summary=dict(speed_runs=24,timed_requests=24*1152,comparisons=rows,strict_ablation_and_sieve_passes=sum(x['pilot_screen'] for x in pairs if x['baseline']!='OldFull'),strict_retained_binary_passes=sum(x['pilot_screen'] for x in pairs if x['baseline']=='OldFull'),development_inputs=True)
(p/'object-hpj-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
md='# 热点估值修复：小规模开发回归\n\n24次测速，27,648次请求。两个已分析输入，各两轮反向顺序。速率为总逻辑字节/总墙钟时间；汇总p99是两次运行p99的中位数，不是合并请求p99。吞吐提升为正、p99变化为负才有利。前三表均为完整版只关闭一项功能的单开关消融。\n\n'
for title,v in [('1. 热点估值消融','NoHotspot'),('2. 跨逻辑域放置消融','NoAffinity'),('3. 联合准入消融','NoJoint'),('4. 整体对共享SIEVE','PoolSIEVE1'),('补充：新旧完整版同批对照','OldFull')]:
 md+=f'## {title}\n\n|输入|新版 MiB/s|对照 MiB/s|吞吐提升|新版p99 ms|对照p99 ms|p99变化|严格通过|\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
 for r in rows:
  if r['baseline']!=v:continue
  f,b=r['full'],r['control'];md+=f"|{r['scenario']}|{f['mib_s']:.3f}|{b['mib_s']:.3f}|{r['gain_pct']:+.3f}%|{f['p99_ms']:.3f}|{b['p99_ms']:.3f}|{r['p99_change_pct']:+.3f}%|{r['strict_passes']}/2|\n"
 md+='\n'
md+='## 全部逐轮结果\n\n|输入/轮次|对照|吞吐变化|p99变化|严格通过|\n|---|---|---:|---:|---|\n'
for x in pairs:md+=f"|{x['block']}|{x['baseline']}|{x['gain_pct']:+.3f}%|{x['p99_change_pct']:+.3f}%|{x['pilot_screen']}|\n"
md+='\n## 复制与远端读取\n\n|输入|版本|两轮远端MiB|两轮复制次数|两轮CPU秒|\n|---|---|---:|---:|---:|\n'
for scene in ['moving_shared','public_toolagent']:
 rr=[r for r in rows if r['scenario']==scene]
 for v,s in [('Full',rr[0]['full'])]+[(r['baseline'],r['control']) for r in rr]:md+=f"|{scene}|{v}|{s['remote_mib']:.0f}|{s['copies']}|{s['cpu_s']:.2f}|\n"
md+='\n仅cn7上的逻辑消费者域与cn13 NVMe/TCP；不代表物理GPU或推理加速。本轮使用已检查数据进行开发，不覆盖报告66，也不代表独立确认、显著性或全部工作负载。\n'
(p/'object-hpj-tables.md').write_text(md)
print(json.dumps(summary,indent=2))
