from pathlib import Path
import json,math,statistics
p=Path(__file__).resolve().parent;tag='integrated-hpj-cohort-caller-final';data=p/(tag+'-data/confirmation')
load=lambda f:json.loads(f.read_text());m=load(data/'manifest.json');pairs=load(data/'comparisons.json');rows=[]
for scene in ['moving_shared','public_toolagent']:
 blocks=[b for b in m['spec']['blocks'] if b['scenario']==scene]
 def stats(v):
  rs=[load(data/b['id']/v/'result.json') for b in blocks]
  return dict(mib_s=sum(r['logical_bytes'] for r in rs)/1048576/math.fsum(r['job_wall_s'] for r in rs),p99_ms=statistics.median(r['request_p99_s']*1000 for r in rs),rates=[r['effective_mib_s'] for r in rs],tails=[r['request_p99_s']*1000 for r in rs],remote_mib=sum(r['metrics'].get('read_remote_bytes',0) for r in rs)/1048576,copies=sum(r['metrics'].get('read_fill_copy_count',0) for r in rs),cpu_s=math.fsum(r['daemon_cpu_s'] for r in rs),drain_mib_s=sum(r['logical_bytes'] for r in rs)/1048576/math.fsum(r['completed_with_background_s'] for r in rs))
 f=stats('Full')
 for v in ['NoHotspot','NoAffinity','NoJoint','PoolSIEVE1']:
  b=stats(v);ps=[x for x in pairs if x['scenario']==scene and x['baseline']==v]
  rows.append(dict(scenario=scene,baseline=v,full=f,control=b,gain_pct=(f['mib_s']/b['mib_s']-1)*100,p99_change_pct=(f['p99_ms']/b['p99_ms']-1)*100,strict_passes=sum(x['pilot_screen'] for x in ps),throughput_passes=sum(x['gain_pct']>0 for x in ps),tail_passes=sum(x['p99_change_pct']<0 for x in ps),pairs=ps))
summary=dict(speed_runs=20,timed_requests=23040,comparisons=rows,strict_passes=sum(x['pilot_screen'] for x in pairs),strict_comparisons=len(pairs),all_passed=all(x['pilot_screen'] for x in pairs),new_inputs=2,rounds_per_input=2,physical_gpu_evidence=False)
(p/'final-hpj-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
md='# TokenFS 最终小规模冻结确认：四张表\n\n20次测速、23,040次请求。移动与公开各一条未参与调参的输入，各跑两个相反顺序的完整五臂轮次。前三表为同一冻结完整版只关闭一项功能的消融，第四表为整体比较。\n\n速率=全部逻辑MiB/完整墙钟秒；p99列为两次运行p99的中位数，不是合并请求的p99。吞吐变化为正、p99变化为负才有利。严格通过还要求后台排空吞吐不退化、相应机制有实际作用。两轮不是两个独立输入，不代表统计显著性。\n\n'
for title,v in [('1. 动态热点估值消融','NoHotspot'),('2. 跨逻辑域放置消融','NoAffinity'),('3. 受害者损失感知联合准入消融','NoJoint'),('4. 整体相对共享SIEVE','PoolSIEVE1')]:
 md+=f'## {title}\n\n|场景|Full MiB/s|对照 MiB/s|吞吐变化|Full p99 ms|对照 p99 ms|p99变化|吞吐正向|p99正向|严格通过|\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n'
 for r in rows:
  if r['baseline']!=v:continue
  f,b=r['full'],r['control'];md+=f"|{r['scenario']}|{f['mib_s']:.3f}|{b['mib_s']:.3f}|{r['gain_pct']:+.3f}%|{f['p99_ms']:.3f}|{b['p99_ms']:.3f}|{r['p99_change_pct']:+.3f}%|{r['throughput_passes']}/2|{r['tail_passes']}/2|{r['strict_passes']}/2|\n"
 md+='\n'
md+='## 逐轮配对结果（不得以汇总隐藏方向）\n\n|场景/轮次|对照|吞吐变化|p99变化|排空吞吐变化|严格通过|\n|---|---|---:|---:|---:|---|\n'
for x in pairs:md+=f"|{x['block']}|{x['baseline']}|{x['gain_pct']:+.3f}%|{x['p99_change_pct']:+.3f}%|{x['drain_gain_pct']:+.3f}%|{x['pilot_screen']}|\n"
md+='\n## 逐轮绝对值与机制\n\n|输入/轮次|版本|MiB/s|p99 ms|远端MiB|复制次数|CPU秒|\n|---|---|---:|---:|---:|---:|---:|\n'
for b in m['spec']['blocks']:
 for v in b['variants']:
  r=load(data/b['id']/v/'result.json');mt=r['metrics'];md+=f"|{b['id']}|{v}|{r['effective_mib_s']:.3f}|{r['request_p99_s']*1000:.3f}|{mt.get('read_remote_bytes',0)/1048576:.0f}|{mt.get('read_fill_copy_count',0)}|{r['daemon_cpu_s']:.2f}|\n"
md+='\ncn7串行逻辑消费者域，cn13真实NVMe/TCP；不代表物理GPU共享、模型tokens/s或TTFT。公开原始块序列归一化为2MiB对象，caller为源请求序号模3。NoHotspot保留基础频率，NoJoint仅关闭已有准入损失项，SIEVE为TokenFS等能力适配。报告66和69单列，不拼接为本版结果。\n'
md+=f"\n本批严格检查通过 **{summary['strict_passes']}/{summary['strict_comparisons']}**。整批数据已报告；是否支持具体性能主张，以逐项结果及适用范围为准。\n"
(p/'final-hpj-tables.md').write_text(md)
print(json.dumps(summary,indent=2))
