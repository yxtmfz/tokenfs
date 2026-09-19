# AURA-KV / TokenFS 文档导航

当前真实评估迁移到 cn7→cn13；cn14 保持停用。优先阅读 [证据实验方案](evidence-experiments.md) 与 [正式批次预先固定方案](evidence-preregistration.md)。历史模拟和 cn14 表格不能替代修复后的真实速度证据。

阅读顺序建议如下：

| 顺序 | 文档 | 作用 |
|---:|---|---|
| 1 | [../README.md](../README.md) | 项目总入口，先了解项目做什么、完成到哪一步 |
| 2 | [system-design.md](system-design.md) | 系统架构、数据模型、生命周期、一致性与恢复 |
| 3 | [model-and-controller.md](model-and-controller.md) | 价值感知缓存管理、多 GPU 副本放置和联合控制器 |
| 4 | [experiments.md](experiments.md) | 实验设计、指标、已有结果和论文边界 |
| 5 | [deployment.md](deployment.md) | Ubuntu、FUSE、NVMe-oF、脚本和配置说明 |
| 6 | [cn7 正式实测报告](../reports/latest/paper-experiments/10_real_cn7_evidence/README.md) | 最新统一实验结果 |

仓库不再保留大量 `01_xxx.md` 到 `15_xxx.md` 的分散文档；对应内容已经合并到上面四份核心文档里。之后继续优化时，也优先更新这些文件。

当前结果按证据级别阅读：

- 策略模型历史结果：`reports/latest/paper-experiments/01_trace_replay/` 和 `05_performance_summary/`。修复前在途复制、容量和统计问题影响这些结果，不能直接沿用旧优势结论。
- 旧真实结果：`reports/latest/paper-experiments/09_real_cn14_nvmeof/`，保留用于追溯；旧计时口径和基线差异尚不足以支持新的公平性能比较。
- 当前真实入口：cn7 上运行 `scripts/evidence_benchmark.py`；统一使用实际 NVMe/TCP 路径、相同任务字节、完整任务耗时、配对种子和独立输出目录。`evidence_audit.py` 先审计整批完整性，`evidence_report.py` 再生成速度优先的结论。
