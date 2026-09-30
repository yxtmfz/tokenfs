> 当前实验入口：[第74轮同批四表与未通过项](../reports/latest/paper-experiments/74_disk_opportunity/README.md)。24次测速、576次内容校验完成，严格9/16通过；创新1仅1/4通过，候选默认关闭，不能宣布三个创新点全部闭环。
>
> 原冻结确认：[报告70](../reports/latest/paper-experiments/70_final_confirmation/README.md)；定位依据：[报告73逐副本诊断](../reports/latest/paper-experiments/73_hotspot_lifetime_diagnostic/README.md)。各批次独立保留，不能拼接正项。

以下是历史进展记录，其中“最新”均指当时，当前结果以以上入口为准。

> 最新回归：[取消5%门槛后的12组完整结果](../reports/latest/paper-experiments/31_planning_efficiency/README.md)。已实现决策等价的规划计算优化；按正吞吐、p99及排空后吞吐不退化的新标准，9项中6项通过。固定热点相对SIEVE仍慢9.01%，另有两项约0.10/0.08ms的p99小幅增加。未宣称全部达标，历史门槛与原始负结果保留。

> 最新结果：[共享放置与联合准入12组实测](../reports/latest/paper-experiments/30_component_ablation/README.md)。跨域放置三条件吞吐均提高，但固定热点未达5%门槛；联合决策固定热点/随机提高10.49%/13.95%，迁移热点降低4.01%。完整版对SIEVE-1hit两个热点分别降低1.43%/2.99%、随机提高21.63%。整体门槛未通过，全部结果和原始证据保留，未扩量。

> 下一轮准备：[共享放置与联合准入消融](../reports/latest/paper-experiments/29_component_ablation_preflight/README.md)。已补单变量对照与固定12组输入，尚未运行；第28轮实测结论不变。

> 最新结果：[暂存共享12组实测速率与完整审计](../reports/latest/paper-experiments/28_inflight_shared_reads/README.md)。新版热点相对旧版 **+32.56%**，相对同样启用共享读取的SIEVE-1hit/2hit **+2.86%/+17.75%**，两个热点种子均更快。随机相对两种SIEVE **+19.48%/+19.85%**，但仅一个种子；相对旧版p99退化3.58%。热点对1hit未达到预设5%门槛，整体门槛未通过。全部12组保留，未追加测速；最新热点/亲和/联合独立消融仍未闭合。

> 上一轮验证：[12组剩余复制成本单变量对照](../reports/latest/paper-experiments/26_incremental_copy_cost/README.md)。候选修正对旧控制器未取得新增提速，保持默认关闭。原控制器本轮热点对SIEVE-1hit仍一胜一负；随机单种子对1hit/2hit提速25.79%/23.03%，尚非独立确认。全部原始结果保留，未扩大实验规模。

> 上一轮修复：已完成[18组小规模开发试验及成本计量修复](../reports/latest/paper-experiments/25_request_cost_repair/README.md)。最新版本对SIEVE-2hit吞吐和p99均改善，但对SIEVE-1hit吞吐仍未稳定领先；报告24失败完整保留，未进入大规模验证。

> 最新进展：已完成[六组请求级尾延迟诊断](../reports/latest/paper-experiments/23_request_tail_diagnostic/README.md)。诊断中吞吐略有优势，但p99仍更慢；报告22正式结论不变。诊断不代表新的策略提速验证。

最新见 [三个缺口优化实测与未通过门槛](../reports/latest/paper-experiments/22_adaptive_control/README.md) 和 [冻结方案](adaptive-control-sieve-plan.md)。四项平均吞吐比较均正向，但逐种子不退化及p99尚未全部闭合。

当前优先查看 [新版与两种共享SIEVE的真实对照](../reports/latest/paper-experiments/21_burst_reuse_sieve/README.md) 和 [冻结小规模方案](burst-reuse-sieve-plan.md)：热点变化场景超过原SIEVE-2hit 5.12%，但SIEVE-1hit及随机负对照的未通过结果一并保留。

# AURA-KV / TokenFS 文档导航

当前先读 [最后18次小规模实验四表](../reports/latest/paper-experiments/20_compact_planning_closeout/README.md)、[冻结方案](compact-planning-closeout-plan.md)与[规划和计账正确性说明](compact-planning-correctness.md)。联合控制本轮+5.88%，强共享基线仍未超过，所有未通过门槛与原始记录一并保留。

上一轮见 [18次热点、亲和与联合优化结果](../reports/latest/paper-experiments/19_causal_reuse_pilot/README.md)、[冻结先导方案](causal-reuse-pilot-plan.md)和[候选创新与已有工作边界](causal-reuse-novelty-boundary.md)。本轮三个组件配对均值均正向，完整版本尚未超过同总容量共享SIEVE；小样本与逻辑GPU边界保留。此前 [共享读取试验](../reports/latest/paper-experiments/17_shared_cache_pilot/README.md)和[第一轮共享联合试验](../reports/latest/paper-experiments/18_shared_joint_pilot/README.md)的结果不改写、不混算。

旧大样本实验见 [三项机制与整体速度四表](../reports/latest/paper-experiments/13_affinity_joint/README.md)，以及 [本轮预先固定方案](affinity-joint-confirmation-plan.md)。本轮完成 **576 次正式实测、132 项内容验证**，按热点、访问亲和、联合净收益和整体速度给出四张表。组件采用完整策略逐项关闭的对照，实际 MiB/s 与配对统计决定结论；未确定、未触发和退化结果全部保留。范围为三个私有逻辑缓存域与真实 NVMe/TCP 远端，不是物理 GPU 推理，也不代表完整 Python RobustBenefit 已接入。

上一轮 B3 的论文边界见 [实验收口与论文可用结论](../reports/latest/paper-experiments/12_paper_closeout/README.md)：它区分已支持的热点自适应收益、尚未成立的 GPU 亲和贡献，并给出可直接引用的结果表和独立离线复核入口。

各轮真实评估迁移到 cn7→cn13；cn14 保持停用。优先阅读 [第二轮策略与消融对象](measured-admission-study.md)、[冻结确认方案](measured-confirmation-plan.md) 和 [第二轮完整结果](../reports/latest/paper-experiments/11_measured_admission/README.md)。第一轮方案仍见 [证据实验方案](evidence-experiments.md) 与 [预先固定方案](evidence-preregistration.md)。历史模拟和 cn14 表格不能替代修复后的真实速度证据。

阅读顺序建议如下：

| 顺序 | 文档 | 作用 |
|---:|---|---|
| 1 | [../README.md](../README.md) | 项目总入口，先了解项目做什么、完成到哪一步 |
| 2 | [system-design.md](system-design.md) | 系统架构、数据模型、生命周期、一致性与恢复 |
| 3 | [model-and-controller.md](model-and-controller.md) | 价值感知缓存管理、多 GPU 副本放置和联合控制器 |
| 4 | [experiments.md](experiments.md) | 实验设计、指标、已有结果和论文边界 |
| 5 | [deployment.md](deployment.md) | Ubuntu、FUSE、NVMe-oF、脚本和配置说明 |
| 6 | [第二轮完整实测报告](../reports/latest/paper-experiments/11_measured_admission/README.md) | 756 次速度实验与全部消融结果 |

核心设计集中在上述系统、模型、实验和部署文档；各轮冻结方案与审计证据单独保留版本，避免把旧结果改写成新结论。

当前结果按证据级别阅读：

- 策略模型历史结果：`reports/latest/paper-experiments/01_trace_replay/` 和 `05_performance_summary/`。修复前在途复制、容量和统计问题影响这些结果，不能直接沿用旧优势结论。
- 旧真实结果：`reports/latest/paper-experiments/09_real_cn14_nvmeof/`，保留用于追溯；旧计时口径和基线差异尚不足以支持新的公平性能比较。
- 第一轮真实入口：cn7 上运行 `scripts/evidence_benchmark.py`；统一使用实际 NVMe/TCP 路径、相同任务字节、完整任务耗时、配对种子和独立输出目录。`evidence_audit.py` 先审计整批完整性，`evidence_report.py` 再生成速度优先的结论。

- 第二轮入口：`scripts/measured_study.py`、`scripts/measured_domain_study.py`；离线使用 `measured_artifacts.py` 和 `measured_freeze_audit.py`。原始数据与复算方法见 [第二轮证据索引](../reports/latest/paper-experiments/11_measured_admission/EVIDENCE-INDEX.md)。
