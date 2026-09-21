from pathlib import Path
import json,hashlib,shutil,statistics
w=Path(__file__).resolve().parent;r=w/'tokenfs-eval';data=w/'paper-minimal-data';main=data/'cn7/paper-minimal-confirmation-01';out=r/'reports/latest/paper-experiments/16_minimal_closeout'
read=lambda p:json.loads(p.read_text())
audit=read(w/'paper-minimal-independent-audit.json');assert audit['passed']
s=read(main/'summary.json');cs=read(main/'comparisons.json');f=read(r/'study-configs/paper-minimal-freeze-01.json')
def cpu_rows(rows):
 for x in rows:
  yield x
  yield from cpu_rows(x.get('children',[]))
context=read(data/'cn7/final-context.json');hw=context['hardware'];cpu={x['field'].rstrip(':'):x['data'] for x in cpu_rows(json.loads(hw['cpu']['stdout'])['lscpu']) if x.get('data') is not None}
environment=f"客户端报告 CPU：{cpu.get('Model name','见原始 lscpu')}；逻辑 CPU 数：{cpu.get('CPU(s)','见原始 lscpu')}；内存：{hw['memory_kib']/1048576:.2f} GiB；内核：{context['kernel']}。完整设备型号、扇区大小、文件系统与编译器见 provenance/cn7-final-context.json；未在 cn13 执行额外探测。"
labels={'static_affinity':'稳定热点','hot_shift':'热点变化','public_toolagent':'公开工具代理轨迹','uniform':'均匀随机'}
verdict={'faster':'确认提速','slower':'确认变慢','uncertain':'差异未确定','descriptive':'仅描述'}
row=lambda scene,name:next(x for x in s if x['scenario']==scene and x['strategy']==name)
def table(headers,rows):
 return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,line))+' |' for line in rows])+'\n'
overall=table(['场景','RemoteOnly','LRU','SIEVE','SIEVE-2hit','RecentLFU','Full（H+J）'],[[label]+[f"{row(scene,n)['mib_s']:.2f}" for n in ['RemoteOnly','LRU','SIEVE','SIEVE-2hit','RecentLFU','Full']] for scene,label in labels.items()])
def pct(value):
 return f"{value:+.4f}%" if abs(value)<.01 else f"{value:+.2f}%"
def comparison_table(values):
 return table(['场景','对照','Full / 对照 MiB/s','配对速率变化','耗时比 95% CI','Holm p','结论'],[[labels[c['scenario']],c['baseline'],f"{row(c['scenario'],'Full')['mib_s']:.2f} / {row(c['scenario'],c['baseline'])['mib_s']:.2f}",pct(c['throughput_change_pct']),f"[{c['ci95'][0]:.4f}, {c['ci95'][1]:.4f}]",f"{c['p_holm']:.6f}",verdict[c['verdict']]] for c in values])
overall_comparisons=comparison_table([c for c in cs if c['family']=='overall'])
mechanism=comparison_table([c for c in cs if c['family']=='mechanism'])
factorial_rates=table(['热点变化配置','H','J','实际 MiB/s'],[[n,h,j,f"{row('hot_shift',n)['mib_s']:.2f}"] for n,h,j in [('no-HJ','关','关'),('no-H','关','开'),('no-J','开','关'),('Full','开','开')]])
activity=table(['场景','消融','Full 机制活动配对数','实际复制/淘汰动作不同配对数','含后台收尾耗时比'],[[labels[c['scenario']],c['baseline'],f"{c['mechanism_active_pairs']}/12",f"{c['different_action_pairs']}/12",f"{c['with_drain_ratio']:.4f}"] for c in cs if c['family']=='mechanism'])
overhead=table(['场景','策略','前台秒','含后台收尾秒','CPU 秒','峰值 RSS MiB','每轮 p99 均值 ms','远端读 MiB','复制 MiB'],[[labels[x['scenario']],x['strategy']]+[f"{v:.2f}" for v in [x['wall_s'],x['with_drain_s'],x['cpu_s'],x['rss_kib']/1024,x['p99_ms'],x['remote_mib'],x['copy_mib']]] for x in s if x['strategy'] in ['RemoteOnly','LRU','SIEVE','SIEVE-2hit','RecentLFU','Full']])
sens=read(data/'cn7/paper-minimal-sensitivity-01/summary.json');sensc=read(data/'cn7/paper-minimal-sensitivity-01/comparisons.json')
sensitivity=table(['边界条件','n/组','RecentLFU MiB/s','Full MiB/s','配对速率变化','含后台收尾耗时比'],[[c['scenario'],c['n'],f"{next(x for x in sens if x['scenario']==c['scenario'] and x['strategy']=='RecentLFU')['mib_s']:.2f}",f"{next(x for x in sens if x['scenario']==c['scenario'] and x['strategy']=='Full')['mib_s']:.2f}",pct(c['throughput_change_pct']),f"{c['with_drain_ratio']:.4f}"] for c in sensc])
comp=lambda scene,baseline:next(c for c in cs if c['scenario']==scene and c['baseline']==baseline)
primary=[c for c in cs if c['family']=='overall'];components=[c for c in cs if c['family']=='mechanism']
status=dict(performance_runs=336,content_cases=56,development_runs=28,sensitivity_runs=12,primary_comparisons=16,primary_faster=[dict(scenario=c['scenario'],baseline=c['baseline'],change_pct=c['throughput_change_pct']) for c in primary if c['verdict']=='faster'],primary_slower=[dict(scenario=c['scenario'],baseline=c['baseline'],change_pct=c['throughput_change_pct']) for c in primary if c['verdict']=='slower'],primary_uncertain=[dict(scenario=c['scenario'],baseline=c['baseline']) for c in primary if c['verdict']=='uncertain'],mechanisms=components,all_baselines_faster_scenes=[scene for scene in labels if all(c['verdict']=='faster' for c in primary if c['scenario']==scene)],original_three_contribution_claim_supported=False,physical_gpu_verified=False,real_inference_verified=False,affinity_independent_gain_confirmed=False,algorithm_revision=f['algorithm_revision'],binary_sha256=f['binary_sha256'])
for folder in ['raw','confirmation','development','sensitivity','validation','provenance']:(out/folder).mkdir(parents=True,exist_ok=True)
for host in ['cn7','cn8']:
 shutil.copy2(w/f'tokenfs-paper-minimal-{host}.tar.gz',out/'raw'/f'tokenfs-paper-minimal-{host}.tar.gz')
 for name in ['final-context.json','preflight.json']:shutil.copy2(data/host/name,out/'provenance'/f'{host}-{name}')
 for p in (data/host).glob('build*'):
  if p.suffix in ['.log','.exit']:shutil.copy2(p,out/'validation'/f'{host}-{p.name}')
 shutil.copy2(data/host/'paper-minimal-correctness-01/batch-audit.json',out/'validation'/f'{host}-content-audit.json')
for folder in ['confirmation','development','sensitivity']:
 for name in ['summary.json','comparisons.json','interactions.json','manifest.json','batch-audit.json']:shutil.copy2(main.parent/f'paper-minimal-{folder}-01'/name,out/folder/name)
for name in ['paper-minimal-src-01.tar.gz','paper-minimal-src-02.tar.gz','paper-minimal-python-deps.tar.gz','paper-minimal-freeze-launch.tar.gz','launch-paper-minimal-development.sh','launch-paper-minimal-development-02.sh','launch-paper-minimal-development-03.sh','launch-paper-minimal-confirmation.sh','preflight-paper-minimal.sh','collect-paper-minimal.sh','freeze-paper-minimal.py','make-paper-minimal-specs.py','build-paper-minimal-report.py','reproduce-paper-minimal.py','package-paper-minimal.py','analyze-paper-minimal-phases.py','export-paper-minimal-tex.py','update-paper-minimal-index.py']:
 shutil.copy2(w/name,out/'provenance'/name)
shutil.copy2(w/'paper-minimal-phase-review.json',out/'phase-review.json')
shutil.copy2(data/'cn7/confirmation-launch-context.json',out/'provenance/confirmation-launch-context.json');shutil.copy2(w/'paper-minimal-independent-audit.json',out/'validation/independent-audit.json')
drains=[dict(scenario=c['scenario'],baseline=c['baseline'],foreground_ratio=c['time_ratio'],with_drain_ratio=c['with_drain_ratio']) for c in cs if c['time_ratio']<1<=c['with_drain_ratio']]
for name,obj in [('verdict',status),('drain-review',drains)]:(out/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
supported='、'.join(labels[x] for x in status['all_baselines_faster_scenes']) or '无'
claimrows=[]
for c in components:
 claimrows.append([('热点适应 H' if c['baseline']=='no-H' else '联合准入 J')+'：'+labels[c['scenario']],verdict[c['verdict']],f"Full 对 {c['baseline']}，{c['throughput_change_pct']:+.2f}%",'仅对应场景与当前配置'])
claimrows += [['完整系统更快',f"{len(status['primary_faster'])}/16 项确认提速",'四场景、四缓存参照逐项报告','不能把组件阳性替代整体阳性'],['GPU 亲和独立提速','未证实','既有报告 14、15 保留失败/不确定结果','本轮关闭亲和决策，不增加亲和证据'],['包含 GPU 亲和的三模块联合控制','本轮不验证','本轮亲和关闭，J 仅指迁入与淘汰损失联合准入','不能外推成热点与 GPU 亲和的总体协同'],['真实多 GPU / 推理提升','未测试','逻辑域与存储轨迹回放','不能写 tokens/s、TTFT、GPU 利用率收益'],['中科院二区/三区录用','无法由实验保证','尚需创新性定位与目标期刊审查','分区不是固定性能百分比门槛']]
ledger=table(['拟写论点','证据状态','证据','论文边界'],claimrows)
text=f'''# TokenFS 最小补实验闭环：真实存储速率与论文论点

本轮完成 **336 次正式测速、56 项内容检查、28 次开发测速、12 次描述性边界测速**。主矩阵相较旧版 576 次缩小约 42%。四场景与四个缓存对照的 16 项主比较中，确认提速 **{len(status['primary_faster'])}** 项，确认变慢 **{len(status['primary_slower'])}** 项，差异未确定 **{len(status['primary_uncertain'])}** 项；同时胜过全部四个缓存参照的场景：**{supported}**。

这是一轮预先固定的 H+J 存储实验。H 为热点变化后的需求历史适应，J 为将待迁入收益与被淘汰对象损失共同考虑的准入决策。五个实验亲和开关均关闭，停用 measured 控制器的跨域亲和历史与亲和决策；共享的旧元数据统计仍保留，详见下述口径说明。新数据不与前轮混算，不将旧亲和的未证实结果改写为正面创新。

## 表 1：整体实际速度

单位 MiB/s，每格为 12 次运行的算术均值。

{overall}

主指标 = 实际读取逻辑字节 / 客户端 monotonic 完整前台耗时。每轮 768 MiB，配额为每逻辑域 8 MiB。表内速率是实际文件读取结果，不是模型预测、仿真延迟或 GPU 算力。百分比采用配对几何耗时比的倒数，因此不等于两个算术均值相除。

{overall_comparisons}

“确认提速”同时要求 12 个完整配对、Holm p<.05、95% 耗时比区间低于 1；16 项主比较在一个家族内校正。不确定并不表示性能相同。RemoteOnly 的四项诊断比较在 [完整比较](confirmation/comparisons.json)，单独校正，不代替缓存基线。

## 表 2：机制消融和控制变量

{mechanism}

Full 与 no-H 只差热点历史重置开关；Full 与 no-J 只差将被淘汰损失纳入准入的开关。容量、轨迹、请求数、复制通路和其他估计均一致。no-H 仍保留 128 次近期历史的自然衰减；no-J 仍保留复制成本、容量约束和相同受害者排序，仅不向准入决策计入被淘汰损失，因此不是关闭全部保护的弱对照。这里检验的是另一个组件开启时的增量收益，不等于组件在任意环境独立运行都有效。热点变化还运行 no-HJ，构成 H/J 的完整 2×2 组合。三个机制比较另作 Holm 校正；不能把 no-J 当作成熟外部算法。复制与淘汰是异步的，动作序列差异仅佐证决策活动，不单独证明速度原因。

{activity}

{factorial_rates}

热点切换的四阶段实际耗时与速率见 [阶段复核](phase-review.json)。这是复用原始请求时间线的事后描述性分析；阶段标签没有传给策略，各阶段字节与耗时之和严格等于整轮，不按有利阶段重新检验显著性。

热点场景的 H×J 交互项见 [交互结果](confirmation/interactions.json)，仅作探索性描述，不宣称超加性，也不把各组件百分比相加。

H 的实际行为是：检测到连续未命中、最近访问集中于小工作集、且工作集外的旧热度仍明显占优时，缩短该域历史以解除旧热度阻碍。J 的行为是：以观测成本估计迁入收益，同时计入复制开销和为释放容量所选受害集合的损失，再在异步执行阶段重检。两者均使用已观察到的访问与成本，没有阶段标签或未来请求。对这些启发式的性能验证不等于最优性证明，也不自动构成相对既有工作的学术新颖性。

## 表 3：后台成本和资源

{overhead}

每个值是每轮指标的均值。CPU/RSS 只统计 TokenFS 守护进程，CPU 区间含前台与队列收尾，RSS 是进程峰值；p99 是每轮经验 p99 的均值，不是合并请求后的全局 p99。远端读取和复制为逻辑 payload 计账，不等于物理网卡/磁盘总字节。后台收尾为用户态任务完成，不等于物理持久化。加入收尾后，前台均值优势反转的配对比较共 {len(drains)} 项，见 [收尾复核](drain-review.json)。资源与尾延迟仅描述，不随吞吐显著性自动获得显著性。

这些记录提供了两条不同的收益链。打开 H 后，热点场景远端读取从 {row('hot_shift','no-H')['remote_mib']:.2f} 降至 {row('hot_shift','Full')['remote_mib']:.2f} MiB，复制从 {row('hot_shift','no-H')['copy_mib']:.2f} 增至 {row('hot_shift','Full')['copy_mib']:.2f} MiB：增加部分迁入换来了真实提速。打开 J 后，同场景复制从 {row('hot_shift','no-J')['copy_mib']:.2f} 降至 {row('hot_shift','Full')['copy_mib']:.2f} MiB，虽然远端读取从 {row('hot_shift','no-J')['remote_mib']:.2f} 略增至 {row('hot_shift','Full')['remote_mib']:.2f} MiB，整体仍更快。**命中率、复制量单独改善都不是最终判据，实际耗时才是。**

也有明确的不足：热点场景 Full 比 SIEVE 少复制（{row('hot_shift','Full')['copy_mib']:.2f} 对 {row('hot_shift','SIEVE')['copy_mib']:.2f} MiB），却读了更多远端数据（{row('hot_shift','Full')['remote_mib']:.2f} 对 {row('hot_shift','SIEVE')['remote_mib']:.2f} MiB），最终速度更低。数据指向准入过于保守与适应时机的权衡，不能只凭汇总数据确定唯一根因。本轮保持算法冻结，未根据确认结果重调准入参数。

控制变量指算法和配置的开关隔离，并不强制内部状态轨迹相同。例如热点场景 Full/no-J 的 H 重置次数均值分别为 {row('hot_shift','Full')['shift_resets']:.2f}/{row('hot_shift','no-J')['shift_resets']:.2f}；J 改变缓存命中序列后，H 的触发也会变化。因此上述 J 结果是其在完整控制器内的增量效应，包含正常反馈，不能解释成 H 执行轨迹被固定后的纯直接效应。

## 表 4：最小边界检查

{sensitivity}

分别把热点变化的每域配额增至 16 MiB，或把请求数增至 1536；各 3 个新配对，仅比较 Full 与 RecentLFU，共 12 次。长序列仍为四个热点阶段，因此每阶段驻留请求数也变为四倍；它不是固定变化频率下的长时压测。样本少，仅用于暴露方向反转，不形成稳健性或长期运行的确认性主张。没有根据结果追加样本或选择性停止。

## 论文论点与证据闭环

{ledger}

本轮最有依据的结论是：**H 缓解了当前控制器的热点切换问题，J 在目标场景提供了额外净收益；完整系统仍不是各场景最佳策略。** 热点场景相对 RecentLFU 的配对提升为 {comp('hot_shift','RecentLFU')['throughput_change_pct']:+.2f}%，但相对 SIEVE 为 {comp('hot_shift','SIEVE')['throughput_change_pct']:+.2f}%。不能用内部消融的阳性掩盖外部基线仍更快。

公开轨迹中，Full 相对普通 SIEVE 为 {comp('public_toolagent','SIEVE')['throughput_change_pct']:+.2f}%，加入两次访问过滤的参照后优势缩至 {comp('public_toolagent','SIEVE-2hit')['throughput_change_pct']:+.2f}%。这说明参照的准入能力会显著影响比较，不能把前一个涨幅全归功于 J。Full 相对 RemoteOnly 为 {comp('public_toolagent','RemoteOnly')['throughput_change_pct']:+.2f}%，结论为“{verdict[comp('public_toolagent','RemoteOnly')['verdict']]}”；该场景没有确认超越直接远端读取。均匀随机中相对 RemoteOnly 为 {comp('uniform','RemoteOnly')['throughput_change_pct']:+.2f}%，结论为“{verdict[comp('uniform','RemoteOnly')['verdict']]}”，保留缓存/控制开销造成净退化的反例。

Full 对 RecentLFU 的稳定、公开、均匀随机三项比较均未确认提速；“不显著”不证明等价或没有退化。本轮也没有对稳定场景做 J 开/关，不能把稳定场景的整体优势单独归因于 J。下一步写作宜围绕**动态热点历史适应与净收益准入的性能折中**，而不是“热点、GPU 亲和、联合控制三项已全面证实”。

历史亲和结果单独保留：报告 15 的热点交接中，关闭/优化亲和分别为 102.50/106.00 MiB/s，配对变化 +3.36%，Holm p=0.0546875，未通过该轮 .025 门槛；访问者迁移分别为 119.68/117.35 MiB/s，配对变化 −1.97%，同样未确定。它们来自另一冻结版本，不能与本轮速率横向拼比或将涨幅相加。这里只引用原报告，不用本轮源码重新计算旧结果。

可以开始以“动态热点适应＋净收益准入”为主线的存储论文初稿，三个预定机制比较已有真实速率增益证据。但数据不支持原三创新点均已验证、全场景全基线领先或真实 GPU 应用加速。GPU 亲和应保留为未证实的设计/负面结果，而不是性能贡献。若准备投稿中科院二区/三区匹配期刊，仍需核对方法新颖性，并补足论文实际主张所需要的应用证据；本轮短回放和三配对边界检查不能替代这些工作。

## 对照、样本与适用范围

{environment}

**口径更正：** 冻结方案中“全部亲和采集关闭”不能理解为删除所有旧元数据统计。逐行核查发现每次读取仍在共同的 SQLite 路径更新访问序号、事件表和旧亲和统计；所有参照同样承担这部分开销。被关闭的是五个实验亲和开关、measured 控制器跨域亲和历史与亲和决策。调用 Observe 的策略仍保留域激活/epoch 计账，也没有宣称这部分开销已去除。该实验能比较当前共享数据通路上的 H/J 净收益，不能声称已经消除所有亲和采集开销。见 [协议解释说明](../../../../docs/paper-minimal-protocol-notes.md)。冻结方案和样本未改写，没有为此重跑或选择结果。

- LRU 为首次未命中准入，区别于旧报告的两次访问准入 LRU。SIEVE 按 [NSDI 2024 论文](https://www.usenix.org/conference/nsdi24/presentation/zhang-yazhuo) 的队列、访问位与淘汰指针实现；另列 SIEVE-2hit，控制过滤首次访问的收益。SIEVE 是共享 TokenFS 数据通路的策略适配器，有锁和元数据开销，不声称复现原作者无锁实现的绝对吞吐；仅空缓存实验，不支持持久化队列恢复。RecentLFU 是本项目共同框架下的近期频率参照，也不是外部产品吞吐。
- cn7 客户端通过既有 NVMe/TCP namespace 访问 cn13，cn8 只作目录后端的内容正确性交叉校验，没有使用 cn14。三个逻辑域共用客户端物理盘且请求串行，不能代表真实多 GPU、PCIe/NVLink 或并发扩展性。正式性能样本为只读请求、场景内固定块大小；不验证写入负载、变长对象管理或完整文件系统崩溃恢复语义。
- 每组清空应用缓存并随机化区块/策略顺序；前台两层 O_DIRECT，后台验证复制仍 buffered。共享目标机缓存和其他负载没有完全隔离。12 次运行不能替代跨日期、跨机器的独立复验。
- 主种子 2101–2112；公开轨迹的 12 个新窗口与 B3、第三轮及两轮亲和确认互不重叠。保留原块身份/顺序/时间戳，归一化块字节数，调用域由源请求编号模 3 构造。是饱和存储回放，不是原请求到达节奏下的在线推理。
- 5000 次配对 bootstrap 给未校正 95% 区间，精确双侧符号翻转检验基于配对对数耗时差在零假设下对称。主比较、机制比较、远端诊断分属预定家族，不声称控制历次自适应研发或整篇论文所有检验的全局错误率。预定 5% 耗时减少仅为工程参考，不是录用门槛。
- 四场景基于既有研究选择，包括旧版整体弱项和均匀随机负对照；未加入本轮的访问者迁移、热点交接失败仍保留在 [亲和报告 15](https://github.com/yxtmfz/tokenfs/blob/fb6aecf1ce92aae47763f65dec3367953aa84147/reports/latest/paper-experiments/15_affinity_handover/README.md)。本轮不用于抹掉它们，也不新增亲和确认轮。

## 审计与复现

[独立审计](validation/independent-audit.json) 已核对全部运行、源码/二进制/方案/样本哈希、实际字节、请求时间线、配置与配额、后台队列、公开窗口来源和 23 项正式配对比较；并检查字节、配置、时间线三类篡改会被拒绝。原始结果不改写，仅允许并记录派生浮点绝对误差 1e-12 以内的跨平台舍入。

正式测速前曾发生 SIEVE 测试夹具缺少允许淘汰的配置、服务器部署包缺少 Python 模块两类预检失败；已修复并保留原日志。它们没有形成正式性能样本。正式样本不因速度不佳被删改或重跑。

预定方案：[plan](../../../../docs/paper-minimal-plan.md)；冻结文件：[freeze](../../../../study-configs/paper-minimal-freeze-01.json)。算法版本 `{f['algorithm_revision']}`，二进制 SHA256 `{f['binary_sha256']}`。raw 保存两台主机原始记录归档；provenance 保存源代码包与执行脚本；不含 SSH 凭据或缓存 payload。旧报告须使用各自冻结源码复核。

Python 3.12+，完整证据 ZIP 解压后执行 `python3 REPRODUCE.py --output /tmp/tokenfs-minimal-audit.json`，无需服务器或 GPU。该脚本先校验包内全部文件哈希，再从原始数据重新审计与计算结果。报告内 SHA256SUMS 覆盖除自身外全部文件。
'''
(out/'README.md').write_text(text)
(out/'TABLE.md').write_text('# 最小补实验四表\n\n## 整体速度\n\n'+overall+'\n## 机制消融\n\n'+mechanism+'\n## 成本\n\n'+overhead+'\n## 边界\n\n'+sensitivity)
(out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
print(json.dumps(status,ensure_ascii=False));print(overall);print(mechanism)
