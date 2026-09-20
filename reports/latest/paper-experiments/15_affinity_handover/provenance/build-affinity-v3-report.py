from pathlib import Path
import json,hashlib,shutil
w=Path(__file__).resolve().parent;r=w/'tokenfs-eval';data=w/'affinity-v3-data';main=data/'cn7/affinity-v3-confirmation-01';out=r/'reports/latest/paper-experiments/15_affinity_handover'
read=lambda p:json.loads(p.read_text())
audit=read(w/'affinity-v3-independent-audit.json');assert audit['passed']
s=read(main/'summary.json');cs=read(main/'comparisons.json');f=read(r/'study-configs/affinity-v3-freeze-01.json')
labels={'static_affinity':'稳定亲和','caller_shift':'访问者迁移','hot_shift':'热点变化','coupled':'双重变化/容量竞争','public_toolagent':'公开工具代理','uniform':'均匀随机','domain_return':'域闲置后返回','affinity_handover':'热点跨域交接/缓存已满'}
row=lambda scene,name:next(x for x in s if x['scenario']==scene and x['strategy']==name)
comp=lambda scene,base:next(x for x in cs if x['scenario']==scene and x['baseline']==base)
v={'faster':'确认提速','slower':'确认变慢','uncertain':'差异未确定'}
lines=['| 场景 | 旧亲和 MiB/s | 关闭亲和 MiB/s | 优化亲和 MiB/s | 相对关闭亲和 | 结论 |','|---|---:|---:|---:|---:|---|']
for scene,label in labels.items():
 c=comp(scene,'P-off');verdict='未触发；不归因' if not c['mechanism_active_pairs'] and c['verdict']!='slower' else v[c['verdict']]
 lines.append(f"| {label} | {row(scene,'P-old')['mib_s']:.2f} | {row(scene,'P-off')['mib_s']:.2f} | {row(scene,'P-new')['mib_s']:.2f} | {c['throughput_change_pct']:+.2f}% | {verdict} |")
table='\n'.join(lines).replace('-0.00%','0.00%')+'\n';primary=[x for x in cs if x['baseline']=='P-off']
status=dict(independent_gain_confirmed=False,performance_runs=288,content_cases=48,development_runs=48,previous_failed_confirmation_runs=288,previous_development_runs=186,previous_content_cases=186,per_study_family_alpha=.025,supported_scenes=[x['scenario'] for x in primary if x['verdict']=='faster'],slower_scenes=[x['scenario'] for x in primary if x['verdict']=='slower'],uncertain_scenes=[x['scenario'] for x in primary if x['verdict']=='uncertain'],practical_5pct_time_reduction=[x['scenario'] for x in primary if x['verdict']=='faster' and x['time_ratio']<=.95],physical_gpu_performance_verified=False,algorithm_revision=f['algorithm_revision'],binary_sha256=f['binary_sha256'])
for d in ['raw','confirmation','development','validation','provenance']:(out/d).mkdir(parents=True,exist_ok=True)
for host in ['cn7','cn8']:
 shutil.copy2(w/f'tokenfs-affinity-v3-{host}.tar.gz',out/'raw'/f'tokenfs-affinity-v3-{host}.tar.gz')
 for name,dest in [('final-context.json','provenance'),('build.log','validation')]:shutil.copy2(data/host/name,out/dest/f'{host}-{name}')
 shutil.copy2(data/host/'affinity-v3-correctness-01/batch-audit.json',out/'validation'/f'{host}-content-audit.json')
for folder in ['confirmation','development']:
 for name in ['summary.json','comparisons.json','manifest.json','batch-audit.json']:shutil.copy2(main.parent/f'affinity-v3-{folder}-01'/name,out/folder/name)
for name in ['affinity-v3-src-05.tar.gz','affinity-v3-freeze-launch.tar.gz','launch-affinity-v3-development.sh','launch-affinity-v3-confirmation.sh','preflight-affinity-v3.sh','collect-affinity-v3.sh','freeze-affinity-v3.py','make-affinity-v3-specs.py','reproduce-affinity-bundle.py','build-affinity-v3-report.py','package-affinity-v3.py']:shutil.copy2(w/name,out/'provenance'/name)
shutil.copy2(data/'cn7/confirmation-launch-context.json',out/'provenance/confirmation-launch-context.json');shutil.copy2(w/'affinity-v3-independent-audit.json',out/'validation/independent-audit.json')
drains=[dict(scenario=x['scenario'],baseline=x['baseline'],foreground_ratio=x['time_ratio'],with_drain_ratio=x['with_drain_ratio']) for x in cs if x['time_ratio']<1 and x['with_drain_ratio']>=1]
mechanism=[]
for scene in labels:
 for strategy in ['P-off','P-old','P-new']:
  runs=[read(p) for p in main.glob(scene+'-*/'+strategy+'/result.json')];assert len(runs)==12
  keys=sorted({k for run in runs for k in run['metrics'] if k.startswith(('measured_','background_','evict_','cross_gpu_'))})
  mechanism.append(dict(scenario=scene,strategy=strategy,n=12,mean_metrics={k:sum(x['metrics'].get(k,0) for x in runs)/12 for k in keys}))
for name,obj in [('verdict',status),('drain-review',drains),('mechanism-summary',mechanism)]:(out/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
positive='、'.join(labels[x] for x in status['supported_scenes']) or '无';negative='、'.join(labels[x] for x in status['slower_scenes']) or '无'
x=row('affinity_handover','P-new');b=row('affinity_handover','P-off');c=comp('affinity_handover','P-off')
text=f'''# 创新点二：任务交接亲和的独立真实速率验证

**结果尚未达到“创新点二已证实独立提速”的目标。** 交接场景观察到平均 +3.36%，但 Holm p=0.0546875，未通过预定 0.025 门槛，也未达到预定 5% 耗时下降目标。新机制保持实验性、显式启用，不据此建议默认启用或宣称所有场景更快。

完成本版 **288 次正式测速、48 项内容检查、48 次开发测速**。相对关闭亲和确认提速：{positive}；确认变慢：{negative}。只把通过预定检验的场景视为性能贡献，不能以“比旧版快”代替独立收益。

{table}

速率为每组 12 次运行的算术均值；百分比按配对几何耗时比取倒数，不能用表中两个均值直接相除代替。所有三组在本版相同二进制下重新测量。这里没有合并不同版本的数据。

## 原因与最终修正

旧份额门槛要求新访问域追赶旧域历史热度，导致有收益的迁入被拒绝。A/B/C 开发候选进一步暴露出全局缩减、迁入/驻留估值不一致和窗口切换时估值突降等问题。D 修正这些问题后，首轮独立确认仍只有访问者迁移 +0.84%、交接 -0.90%，均未证实独立提升；完整的 288 次负面确认结果见 [首轮确认](../14_affinity_refinement/README.md)，没有删除、混入新轮或重新标成开发数据。

本版 E 针对另一个明确问题：**接收域沿用上个任务的旧热度，阻碍已经在其他域变热的新任务进入**。仅当接收域至少闲置 32 次全局访问、返回后的前 8 次观察中出现既有交接证据，才清除激活前的计数，并保留激活以来的所有本域观察。交接证据要求当前域占最近 4 次访问至少 3 次、份额至少为长窗口的两倍、对象在长窗口中至少出现 8 次且其他域计数至少为当前域两倍。普通闲置和陌生冷对象不触发。

复用预测仍对迁入与驻留对象一致，并逐步衰减；复制成本、被淘汰数据的损失、容量和后台执行前重检都保留。热点策略 H 的重置逻辑保持原实现，亲和交接重置使用独立计数。没有额外缓存、未来请求、阶段标签、主动预取或跨域读取捷径。

P-new 与 P-off 的配置只差 `measured_affinity_gate`；两组都记录相同类型的历史、预测和激活边界，只有开启组应用亲和修正。H 与 J 开启并保持配置一致，所以验证的是完整控制器内、相同统计开销下亲和决策的增量收益，而非亲和独立运行时的表现。对照保留亲和历史采集，未额外测试彻底移除全部亲和统计的最轻基线，不能把本表当作这部分采集开销已经得到偿还的证据。

交接场景平均每轮：远端读取从 {b['remote_mib']:.2f} MiB 变为 {x['remote_mib']:.2f} MiB，复制从 {b['copy_mib']:.2f} MiB 变为 {x['copy_mib']:.2f} MiB；亲和上下文重置 {x['context_resets']:.2f} 次。相对关闭亲和的耗时比 {c['time_ratio']:.5f}，95% 区间 [{c['ci95'][0]:.5f}, {c['ci95'][1]:.5f}]，Holm p={c['p_holm']:.6f}。该场景结论为“{v[c['verdict']]}”。

## 尚未解决的不足

访问者迁移场景仍有 -1.97% 的平均变化，远端读取从 173.17 增至 182.00 MiB。当前上下文重置条件没有额外要求“当前读取未命中”；已经缓存相同热点的返回域也可能重置历史。这是代码层面仍需研究的边界，不能仅凭汇总数据就断言它是此处退化的唯一原因。本轮不再根据确认结果修改候选或更换检验口径。

因此，已完成的是修复、实测和完整验证链；**尚未完成的是可靠的独立性能优势证明**。均值正向、单场景未校正区间排除零、修复旧版三个事实，都不能替代预定的主比较通过。

## 测量、统计和边界

- cn7 读取 cn13 的既有独立 NVMe/TCP namespace，cn8 只作目录后端内容校验。三逻辑域共用客户端物理磁盘，串行饱和回放；不是物理多 GPU、PCIe/NVLink、TTFT 或 tokens/s 试验。
- 八场景、三组、十二个新种子 1901–1912。每轮真实读取 768 MiB、每域容量 8 MiB。每组从空应用缓存开始，随机化场景区块和策略顺序。前台两层均 O_DIRECT，后台复制保持原 buffered 实现；未清空共享目标机缓存，其他共享负载不完全受控。
- 12 个公开 toolagent 窗口与 B3、第三轮、首轮亲和确认、本轮彼此完全不重叠。域编号由源请求编号模 3 构造，块大小归一化；没有冒充原始轨迹含有真实 GPU ID。
- 主指标为客户端 monotonic 外层完整前台耗时，吞吐为真实逻辑字节除以耗时。另列用户态后台队列收尾，不能等同于物理持久化写回。复制量是实际副本 payload 计账，不等于网卡或物理磁盘总字节。
- 配对几何耗时比、5000 次配对 bootstrap、精确双侧符号翻转检验（零假设下配对对数耗时差对称）；八项新/关闭比较作 Holm 校正，八项新/旧修复比较另成家族。本轮额外收紧为 **Holm p<0.025**，同时要求 95% 区间低于 1、12 个完整配对和实际机制活动。区间本身未作多重比较校正，显著性按上述 Holm 标准判断。首轮使用原定 .05 门槛且无独立阳性，在 .025 下同样无阳性；两轮均完整保留。第二轮的从严门槛不能追溯地把整个自适应开发过程变成预先固定的两次检验，因此不声称控制全部研发尝试或整篇论文的全局错误率。
- 本轮代码、二进制、全部样本和先前失败统计哈希均在查看本轮性能之前冻结。没有根据本轮结果调参、补样本、删除场景或再做第三轮确认。预设 5% 耗时降低是实际收益目标，不是保证。

[完整比较](confirmation/comparisons.json) 给出 16 项区间、p 值及含队列收尾比值；[资源汇总](confirmation/summary.json) 给出实际 MiB/s、远端读取、复制、CPU、经验 p99 与两类亲和活动；[机制计账](mechanism-summary.json) 单列各类 H/亲和重置和准入记录。加入后台收尾后前台优势反转的记录有 {len(drains)} 项，见 [收尾复核](drain-review.json)。尾延迟和资源数值是描述性结果，不将吞吐改善外推为 p99 改善。

[独立审计](validation/independent-audit.json) 验证全部批次、内容、字节、请求/域/来源、配置、配额、队列、时间线、12 个公开窗口及 16 项配对统计，并拒绝字节、配置和时间线篡改。跨平台派生浮点差异仅允许绝对误差 1e-12 内的已记录舍入，原始数据不改写。

此前 A/B/C/D 的全部失败开发、内容记录和 D 的正式确认保留在报告 14。本版结果不能与前轮热点/联合策略的百分比相加，也未重测完整策略对 LRU/LFU 的整体矩阵。

方案：[预定方案](../../../../docs/affinity-v3-plan.md)。冻结：[冻结文件](../../../../study-configs/affinity-v3-freeze-01.json)。算法版本 `{f['algorithm_revision']}`，二进制 SHA256 `{f['binary_sha256']}`。旧报告须在对应版本或冻结源代码下复核，不用新源码冒充旧源码。

Python 3.12+，仓库根目录可离线复核：

```bash
mkdir -p work/affinity-review
tar -xzf reports/latest/paper-experiments/15_affinity_handover/raw/tokenfs-affinity-v3-cn7.tar.gz -C work/affinity-review
tar -xzf reports/latest/paper-experiments/15_affinity_handover/raw/tokenfs-affinity-v3-cn8.tar.gz -C work/affinity-review
python3 scripts/affinity_v3_evidence.py --data-root work/affinity-review --public-source /path/to/toolagent_trace.jsonl --output /tmp/affinity-audit.json
```

SHA256SUMS 覆盖报告内除自身外所有文件。源代码包和远端执行脚本在 provenance 中；证据包不含 SSH 配置、密码、私钥或缓存 payload。
'''
(out/'README.md').write_text(text);(out/'TABLE.md').write_text('# 创新点二实测速率表\n\n'+table)
files=sorted(p for p in out.rglob('*') if p.is_file() and p.name!='SHA256SUMS');(out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in files))
print(json.dumps(status,ensure_ascii=False));print(table)
