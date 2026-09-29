from pathlib import Path
import sys,json,statistics,math
w=Path(__file__).resolve().parent;tag='integrated-hpj-cohort-caller-independent';data=w/(tag+'-data')/'development'
load=lambda p:json.loads(p.read_text())
m=load(data/'manifest.json');pairs=load(data/'comparisons.json');summary=load(data/'summary.json')
assert m['spec']['stage']=='independent'
rs={(b['id'],v):load(data/b['id']/v/'result.json') for b in m['spec']['blocks'] for v in b['variants']}
rows=[]
for baseline in ['NoHotspot','NoAffinity','NoJoint','PoolSIEVE1']:
 for scene in ['moving_shared','public_toolagent','stationary_shared','uniform']:
  blocks=[b for b in m['spec']['blocks'] if b['scenario']==scene and baseline in b['variants']]
  if not blocks:continue
  a=[rs[b['id'],'Full'] for b in blocks];z=[rs[b['id'],baseline] for b in blocks]
  rate=lambda runs:sum(r['logical_bytes'] for r in runs)/1048576/math.fsum(r['job_wall_s'] for r in runs)
  pp=[next(p for p in pairs if p['block']==b['id'] and p['baseline']==baseline) for b in blocks]
  extra={}
  for label,runs in [('full',a),('baseline',z)]:
   mt=[r['metrics'] for r in runs]
   extra[label]=dict(remote_mib=sum(x.get('read_remote_bytes',0) for x in mt)/1048576,
    copied_mib=sum(x.get('promote_bytes',0)+x.get('cross_gpu_replica_create_bytes',0) for x in mt)/1048576,
    cpu_s=math.fsum(r['daemon_cpu_s'] for r in runs),peak_rss_kib=max(r['daemon_peak_rss_kib'] for r in runs),
    drain_mib_s=sum(r['logical_bytes'] for r in runs)/1048576/math.fsum(r['completed_with_background_s'] for r in runs),
    p99_ms=[r['request_p99_s']*1000 for r in runs],rates_mib_s=[r['effective_mib_s'] for r in runs])
  rows.append(dict(baseline=baseline,scenario=scene,n=len(blocks),blocks=[b['id'] for b in blocks],
   full_mib_s=rate(a),baseline_mib_s=rate(z),aggregate_gain_pct=(rate(a)/rate(z)-1)*100,
   full_p99_median_ms=statistics.median(r['request_p99_s']*1000 for r in a),
   baseline_p99_median_ms=statistics.median(r['request_p99_s']*1000 for r in z),
   gains_pct=[p['gain_pct'] for p in pp],p99_reduction_pct=[-p['p99_change_pct'] for p in pp],
   throughput_positive=sum(p['gain_pct']>0 for p in pp),p99_positive=sum(p['p99_change_pct']<0 for p in pp),
   mechanism_active=sum(p['mechanism_active'] for p in pp),strict_passes=sum(p['pilot_screen'] for p in pp),
   aggregate_drain_gain_pct=(extra['full']['drain_mib_s']/extra['baseline']['drain_mib_s']-1)*100,
   details=extra))
result=dict(passed=True,valid_speed_runs=len(rs),logical_requests=sum(len(load(data/b['id']/v/'requests.json')) for b in m['spec']['blocks'] for v in b['variants']),
 frozen_binary=m['binary_sha256'],rows=rows,strict_passes=sum(p['pilot_screen'] for p in pairs),strict_total=len(pairs),
 all_strict_comparisons_passed=all(p['pilot_screen'] for p in pairs),statistical_confirmation=False,
 p99_summary='median of per-run empirical p99 values within each family; not a pooled percentile',
 throughput_summary='total completed logical bytes divided by total wall seconds within each workload family')
(w/'independent-final-summary.json').write_text(json.dumps(result,indent=2)+'\n')
labels={'moving_shared':'移动热点（新种子）','public_toolagent':'公开工具调用轨迹','stationary_shared':'固定热点边界','uniform':'均匀随机边界'}
titles=[('热点估值消融','NoHotspot'),('逻辑域亲和放置消融','NoAffinity'),('受害缓存损失感知的联合准入消融','NoJoint'),('完整策略与共享 SIEVE','PoolSIEVE1')]
md='''# TokenFS 冻结版本独立验证：最终四表

本批为独立于调参输入的新验证，生产实现与报告64及其二进制完全一致；不含已撤回的报告65优化。先冻结输入/顺序/协议，完成全部预定运行后统一汇总，未按输赢改参数或补跑。历史开发结果单列，不能替代本批结论。

实际速率为完成的逻辑读取MiB÷墙钟秒，非命中率推算、网络线速或模型tokens/s。表中p99为各次运行p99的中位数，**不是合并请求的p99**；逐次原值、正负方向和机制计数均保留。正向项分母是独立输入个数，不是请求数；3个输入不构成统计显著性确认。前三表仅关闭一个模块，第四表才是整体策略比较。

'''
for i,(title,baseline) in enumerate(titles,1):
 md+=f'## 表{i}：{title}\n\n'
 md+='|场景|n|Full MiB/s|对照 MiB/s|吞吐变化|p99 Full/对照 ms|吞吐正向|p99正向|机制有效|严格通过|\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n'
 for r in rows:
  if r['baseline']!=baseline:continue
  n=r['n'];md+=f"|{labels[r['scenario']]}|{n}|{r['full_mib_s']:.3f}|{r['baseline_mib_s']:.3f}|{r['aggregate_gain_pct']:+.3f}%|{r['full_p99_median_ms']:.3f} / {r['baseline_p99_median_ms']:.3f}|{r['throughput_positive']}/{n}|{r['p99_positive']}/{n}|{r['mechanism_active']}/{n}|{r['strict_passes']}/{n}|\n"
 md+='\n'
md+=f"全部严格检查：**{result['strict_passes']}/{result['strict_total']}**。严格通过同时要求吞吐提高、p99降低、后台排空吞吐不退步，以及对应机制有效。零差异不算改善。\n\n"
md+='''## 固定环境与论文边界

cn7为单客户端，cn13为真实NVMe/TCP远端；3个逻辑消费域串行回放，共享主机磁盘，不是物理GPU并行。每次1152×2MiB请求，24MiB磁盘缓存与4MiB共享捕获内存。所有版本共享同一执行优化、直接前台I/O和复制校验；cn13系统缓存未控制，未调整共享服务器环境。

三个移动输入为73501–73503；公开输入为73601–73603。公开Mooncake轨迹保持原块标识与顺序，统一为2MiB随机有效载荷，以源请求序号模3构造逻辑调用域，饱和串行回放，不能解释为真实模型KV字节、真实GPU身份或端到端推理性能。固定热点与随机各只有一个边界输入，未对它们进行三项消融，不作稳定性结论。

NoJoint只关闭现有受害缓存损失感知的准入项。这一消融只识别其边际作用，不能推出完整控制器优于所有独立H+P组合、全局最优或超加性。共同的元数据与复制路径优化不能算作三个策略模块的新贡献。SIEVE是TokenFS中的等能力算法适配，非原生SIEVE系统的端到端对比。

运行级完整数据见raw/cn7-evidence.tar.gz；严格比较见comparisons.json；各模块复制、远端读取、CPU、RSS和排空性能见final-summary.json。内容校验单独计时，不混入速度结果。所有零收益、负收益和未触发项均为最终结果的一部分。
'''
(w/'independent-four-tables.md').write_text(md)
print(json.dumps(result,indent=2))
