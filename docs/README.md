# AURA-KV / TokenFS 文档导航

当前文档已经整理为最终阅读结构。阅读顺序建议如下：

| 顺序 | 文档 | 作用 |
|---:|---|---|
| 1 | [../README.md](../README.md) | 项目总入口，先了解项目做什么、完成到哪一步 |
| 2 | [system-design.md](system-design.md) | 系统架构、数据模型、生命周期、一致性与恢复 |
| 3 | [model-and-controller.md](model-and-controller.md) | 价值感知缓存管理、多 GPU 副本放置和联合控制器 |
| 4 | [experiments.md](experiments.md) | 实验设计、指标、已有结果和论文边界 |
| 5 | [deployment.md](deployment.md) | Ubuntu、FUSE、NVMe-oF、脚本和配置说明 |
| 6 | [../reports/latest/final-report.md](../reports/latest/final-report.md) | 最新统一实验结果 |

仓库不再保留大量 `01_xxx.md` 到 `15_xxx.md` 的分散文档；对应内容已经合并到上面四份核心文档里。之后继续优化时，也优先更新这些文件。

当前结果分两类读：

- 策略模型结果：看 `reports/latest/paper-experiments/01_trace_replay/` 和 `05_performance_summary/`，用于解释 AURA-KV 相比 LRU/LFU 为什么降低综合代价。
- 真实速度结果：看 `reports/latest/paper-experiments/06_real_speed_benchmark/`，用于按 `RemoteOnly`、`LocalFirst`、`LRU-Local`、`LFU-Local`、`AURA-Joint` 消融分类，直接回答同一组 TokenFS workload 是否真的更快。该结果默认要求 NVMe-oF 直连挂载；SSH tunnel 只能作为功能验证。
- 当前推荐真实实验入口：运行 `TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/lab_single_client_multigpu_experiment.sh`，结果看 `reports/latest/paper-experiments/08_lab_single_client_multigpu/lab_single_client_multigpu_report.md`。这一路线对应“单 Ubuntu 客户端模拟多逻辑 GPU + 老师服务器真实 NVMe-oF 远端层”。
