# 14 实现状态

本文按模块列出当前仓库真实实现状态。状态含义：

| 状态 | 含义 |
|---|---|
| Implemented | 当前代码已经可运行或可测试 |
| Partial | 已有部分实现，但还没有完整工程闭环或真实环境验证 |
| Planned | 文档设计存在，但当前仓库尚未实现 |

## 1. 模块清单

| 模块 | 状态 | 代码位置 | 测试位置 | 当前能力 | 当前限制 |
|---|---|---|---|---|---|
| 存储后端 | Implemented / Partial | `src/main.cpp`、`config/tokenfs.dev.yaml` | `scripts/smoke_test.sh`、`scripts/integration_test.sh` | 本地目录、远端目录模拟、本地优先、远端溢写 | 真实 NVMe-oF 需外部挂载后作为目录使用 |
| 元数据 | Implemented | `src/main.cpp`、`scripts/tokenfsctl.py` | `scripts/integration_test.sh`、`scripts/consistency_test.sh` | SQLite WAL、文件表、指标表、GPU 访问表、本地副本表 | 多节点集中式 MDS 未实现 |
| 缓存身份 | Implemented | `aura_kv/core.py` | `tests/aura_kv_unit_test.py` | `CacheIdentity` 和 `share_safe_key` 用于共享安全判断 | TokenFS 主路径尚未接入完整 KV Tensor 标识 |
| 访问统计 | Implemented | `src/main.cpp`、`aura_kv/core.py` | `scripts/advanced_policy_test.sh` | 记录调用 GPU、累计访问和窗口访问事件 | 真实 GPU runtime trace 未接入 |
| 需求估计 | Implemented | `aura_kv/demand.py` | `tests/aura_kv_unit_test.py` | EWMA、Gamma-Poisson、DualWindow、上下界估计和预测误差指标 | 真实业务突发热点无法完全预测 |
| 前缀有效需求 | Implemented | `aura_kv/demand.py` | `tests/aura_kv_unit_test.py` | 根据 prefix path 汇总有效需求并按请求去重 | 真实 vLLM/SGLang prefix trace 未接入 |
| 来源代价 | Implemented | `aura_kv/cost_model.py` | `tests/aura_kv_unit_test.py` | 本地、peer、远端、重计算代价分解 | 真实网络排队和 GPU H2D metrics 未接入 |
| 最优与第二优来源 | Implemented | `aura_kv/cost_model.py` | `tests/aura_kv_unit_test.py` | `BestSourceResult.best` 和 `second_best` | TokenFS 前台路径未完整使用 Python 来源解析器 |
| 删除损失 | Implemented | `aura_kv/layout.py` | `tests/aura_kv_unit_test.py` | `EvictionLoss` 和密度计算 | 真实线上淘汰仍由 TokenFS 工程评分承担 |
| 副本收益 | Implemented | `aura_kv/layout.py` | `tests/aura_kv_unit_test.py` | `ReplicaGain`、READY 延迟和收益密度 | 后台复制时间仍依赖配置估计 |
| RobustBenefit | Partial | `aura_kv/layout.py` | `tests/aura_kv_unit_test.py` | ADD/REMOVE 差分收益原型 | 完整 SWAP 候选布局事务未实现 |
| 后台任务队列 | Implemented | `aura_kv/tasks.py` | `tests/aura_kv_unit_test.py` | SQLite 持久化任务、状态机、依赖任务、重试和取消 | 尚未接入 TokenFS C++ 主进程 |
| 后台执行器 | Implemented / Partial | `aura_kv/executor.py` | `tests/aura_kv_unit_test.py` | 目录后端复制、校验、原子 rename、淘汰和 SWAP 依赖执行 | 当前用于模拟和论文原型；真实远端需挂载 NVMe-oF 目录 |
| 联合控制 | Implemented / Partial | `aura_kv/controller.py`、`aura_kv/policies.py`、`aura_kv/simulator.py` | `tests/aura_kv_unit_test.py`、`scripts/aura_kv_test.sh` | 前台访问生成 PROMOTE/PREFETCH/REPLICATE/EVICT/SWAP 任务计划，另有 `AuraKVPolicy` 和 baseline 模拟 | TokenFS C++ 前台路径尚未直接调用 Python 控制器 |
| 容量预算 | Implemented | `aura_kv/optimization.py`、`src/main.cpp` | `tests/aura_kv_unit_test.py`、`scripts/eviction_test.sh` | 本地配额、节点容量检查 | 多节点真实容量回收未集中管理 |
| 重复预算 | Implemented | `aura_kv/optimization.py` | `tests/aura_kv_unit_test.py` | 全局和单节点重复副本预算 | TokenFS 主路径使用工程化副本上限 |
| 后台带宽 | Partial | `aura_kv/optimization.py`、`src/main.cpp` | `tests/aura_kv_unit_test.py` | 字段、预算检查和工程 QoS 记录 | 未接入真实 NVMe-oF 带宽和队列反馈 |
| 副本租约 | Partial | `aura_kv/core.py`、`aura_kv/optimization.py` | `tests/aura_kv_unit_test.py` | `lease_expire_at`、最短驻留、安全删除检查 | 没有独立分布式租约服务 |
| 迁移 | Implemented / Partial | `src/main.cpp`、`aura_kv/tasks.py`、`aura_kv/executor.py` | `scripts/promote_test.sh`、`scripts/prefetch_test.sh`、`scripts/consistency_test.sh`、`tests/aura_kv_unit_test.py` | 临时文件、fsync、rename、状态切换、缓存提升；Python AURA-KV 层已有持久化后台任务日志 | C++ 与 Python 两条路径尚未合并为同一个线上任务表 |
| 恢复 | Partial | `src/main.cpp`、`scripts/tokenfsctl.py` | `scripts/consistency_test.sh`、`scripts/fault_injection_test.sh` | 启动恢复扫描、一致性检查、临时状态处理 | 真实断电和 Target 重启需要硬件验证 |
| FUSE | Implemented | `src/main.cpp` | `scripts/smoke_test.sh`、`scripts/integration_test.sh` | 常见 POSIX 文件操作 | 不支持完整生产级 POSIX 语义，如复杂锁和 mmap |
| NVMe-oF | Partial | `scripts/connect_nvme.sh`、`scripts/setup_nvme_target.sh` | `scripts/nvmeof_two_vm_test.sh`、`scripts/nvmeof_perf_test.sh` | 配置化 connect、Target、dry-run 和测试脚本 | 当前仓库没有真实 SSD Target 结果 |
| 模拟器 | Implemented | `aura_kv/simulator.py`、`scripts/aura_kv_sim.py` | `scripts/aura_kv_test.sh` | 8 个场景、15 个策略或 baseline | 模拟结果不是硬件性能 |
| 实验基线 | Implemented | `aura_kv/policies.py`、`aura_kv/simulator.py` | `scripts/aura_kv_test.sh` | RemoteOnly、LocalFirst、LRU/LFU、SizeAwareLRU、DualWindow、StaticNReplica、AffinityOnly、WA-Affinity-Independent、AURA-Joint 等 | SIEVE-StaticN 尚未单独实现；需要真实 workload 进一步校准 |
| 统一事件流 | Implemented / Partial | `aura_kv/monitoring.py`、`aura_kv/simulator.py` | `tests/aura_kv_unit_test.py` | 前台请求、缓存查询、控制器周期、候选动作、后台任务、布局变化统一写入 `events.jsonl` | TokenFS C++ 主进程尚未直接输出同一套事件 |
| 指标导出 | Implemented / Partial | `scripts/tokenfsctl.py`、`aura_kv/monitoring.py`、`scripts/aura_kv_monitor.py` | `tests/aura_kv_unit_test.py`、`scripts/strategy_matrix_test.sh` | TokenFS status/files/replicas/affinity/metrics；AURA-KV `metrics.jsonl`、`layout_snapshots.jsonl`、`results.json/csv`、`state.json` | Prometheus 等外部监控未接入；真实 GPU/NVMe-oF metrics 未接入 |
| 动态 Dashboard | Implemented / Partial | `aura_kv/dashboard.py`、`scripts/aura_kv_monitor.py` | `tests/aura_kv_unit_test.py` | 本地 HTTP Dashboard，展示状态、指标卡、请求流、控制器候选、任务队列、Node x Cache 布局矩阵、时间序列和 trace 搜索 | 当前展示的是 AURA-KV Python 模拟/代理指标，不是生产监控系统 |

## 2. 当前可运行能力

- 在 Ubuntu 上构建并启动 TokenFS FUSE。
- 使用目录模拟本地 SSD 和远端 SSD。
- 为 `/gpu0`、`/gpu1` 等逻辑空间实施本地配额。
- 本地不足时自动写入远端模拟层。
- 记录 SQLite 元数据和指标。
- 查看文件、指标、亲和和副本状态。
- 运行 AURA-KV 单元测试和 trace simulator。
- 运行 AURA-KV workload 监控，生成 `events.jsonl`、`metrics.jsonl`、`layout_snapshots.jsonl` 和本地 Dashboard。
- 使用 NVMe-oF 脚本准备真实接入。

## 3. Partial 重点

- AURA-KV Python 控制器、任务队列和目录执行器已经形成闭环，但 TokenFS C++ 主路径尚未直接调用这套 Python 队列。
- 动态 Dashboard 已经能跟随 Python workload 执行实时刷新；真实 TokenFS C++ 前台请求和真实 NVMe-oF 指标还需要接入同一套事件模型。
- SWAP 已具备“先复制校验新副本，再删除旧副本”的任务依赖原型；真实 NVMe-oF 和多进程恢复仍需硬件环境验证。
- 租约是副本安全字段和删除门控，不是独立分布式租约系统。
- NVMe-oF 已配置化，但真实硬件尚未验证。

## 4. Planned 重点

- 接入真实 vLLM/SGLang KV Cache trace。
- 接入真实 GPU 节点拓扑。
- 接入真实 NVMe-oF 远端 SSD 指标。
- 完成论文级硬件实验。
