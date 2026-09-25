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
