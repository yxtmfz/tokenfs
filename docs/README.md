# AURA-KV / TokenFS 文档导航

本文是 `docs/` 的总入口。根目录 [README.md](../README.md) 用来快速了解项目和运行命令；`docs/` 用来承载完整设计、公式、实现状态和实验计划。

## 1. 初次了解项目

1. [01_overview.md](01_overview.md)：用一篇文章理解项目定位、核心问题和当前边界。
2. [02_background_and_problem.md](02_background_and_problem.md)：解释 LLM 推理、Prompt、Prefill、Decode、KV Cache、本地 SSD 和 NVMe-oF 为什么会放在同一个问题里。
3. [03_system_architecture.md](03_system_architecture.md)：看整体架构图，区分前台数据路径、后台控制路径、控制面和数据面。
4. [04_data_model_and_lifecycle.md](04_data_model_and_lifecycle.md)：跟随一份 KV Cache 从创建、读取、复制、续租到删除的全过程。
5. [14_implementation_status.md](14_implementation_status.md)：确认当前仓库已经实现了什么，哪些还只是设计。

## 2. 参与代码开发

1. [03_system_architecture.md](03_system_architecture.md)：了解 TokenFS 和 AURA-KV 的模块分层。
2. [04_data_model_and_lifecycle.md](04_data_model_and_lifecycle.md)：理解核心数据结构、SQLite 表和副本状态。
3. [12_configuration.md](12_configuration.md)：查看配置项、脚本入口和 NVMe-oF 占位字段。
4. [13_testing_and_experiments.md](13_testing_and_experiments.md)：运行单元测试、FUSE 测试和模拟实验。
5. [14_implementation_status.md](14_implementation_status.md)：按模块查代码位置、测试位置和限制。

## 3. 准备论文或研究汇报

1. [02_background_and_problem.md](02_background_and_problem.md)：研究动机和问题定义。
2. [06_cost_model.md](06_cost_model.md)：正式代价模型、符号表、公式、数值例子和代码映射。
3. [07_replacement_policy.md](07_replacement_policy.md)：候选研究方向一，代价驱动替换策略。
4. [08_replica_placement.md](08_replica_placement.md)：候选研究方向二，共享感知副本放置。
5. [09_joint_controller.md](09_joint_controller.md)：ADD、REMOVE、SWAP 的联合控制逻辑。
6. [13_testing_and_experiments.md](13_testing_and_experiments.md)：baseline、模拟场景、指标和真实硬件实验计划。
7. [15_research_and_paper_plan.md](15_research_and_paper_plan.md)：论文结构、可验证主张和后续路线。
8. [model_assumptions.md](model_assumptions.md)、[model_limitations.md](model_limitations.md)：模型假设和局限性。

## 4. 文档列表

| 文档 | 回答的问题 |
|---|---|
| [01_overview.md](01_overview.md) | 项目是什么，当前做到哪一步 |
| [02_background_and_problem.md](02_background_and_problem.md) | 为什么大模型 KV Cache 需要分层存储 |
| [03_system_architecture.md](03_system_architecture.md) | 系统有哪些模块，前台和后台如何分工 |
| [04_data_model_and_lifecycle.md](04_data_model_and_lifecycle.md) | 缓存对象、副本、请求和节点如何流转 |
| [05_demand_and_prefix_model.md](05_demand_and_prefix_model.md) | 未来需求和前缀有效需求如何估计 |
| [06_cost_model.md](06_cost_model.md) | 正式公式、变量、单位和代码测试映射 |
| [07_replacement_policy.md](07_replacement_policy.md) | 本地满了删谁，为什么不能只用 LRU/LFU |
| [08_replica_placement.md](08_replica_placement.md) | 共享缓存复制到哪里，复制几份 |
| [09_joint_controller.md](09_joint_controller.md) | 替换和副本放置如何联合决策 |
| [10_storage_and_nvmeof.md](10_storage_and_nvmeof.md) | 目录后端和真实 NVMe-oF 如何接入 |
| [11_consistency_and_recovery.md](11_consistency_and_recovery.md) | 迁移、校验、租约和崩溃恢复如何保证安全 |
| [12_configuration.md](12_configuration.md) | 配置文件和命令入口 |
| [13_testing_and_experiments.md](13_testing_and_experiments.md) | 如何运行测试和模拟实验 |
| [14_implementation_status.md](14_implementation_status.md) | Implemented、Partial、Planned 能力清单 |
| [15_research_and_paper_plan.md](15_research_and_paper_plan.md) | 论文计划和后续真实实验 |
| [model_assumptions.md](model_assumptions.md) | 模型成立需要哪些假设 |
| [model_limitations.md](model_limitations.md) | 哪些结论目前不能过度解释 |

