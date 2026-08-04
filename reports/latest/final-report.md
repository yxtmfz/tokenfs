# AURA-KV / TokenFS 最新结果报告

项目名称：

```text
面向多 GPU 大模型 KV Cache 的本地与 NVMe-oF 远端自适应分层缓存系统
```

本文件是当前仓库统一结果入口。机器可读模拟数据保留在 `reports/latest/aura-kv-sim/`，人工阅读优先看本文。

## 1. 结果定位

当前结果用于验证：

- TokenFS 文件系统功能。
- 本地 SSD 与远端层分层语义。
- SQLite 元数据和一致性检查。
- 代价驱动本地缓存管理。
- 多 GPU 共享热点副本放置。
- AURA-KV 模拟器和 baseline 对比框架。

当前结果不能作为真实 NVMe-oF 或真实 GPU 集群的最终性能结论。所有模拟结果都应标注：

```text
SIMULATED RESULT
```

## 2. 当前开发环境

```text
Client VM: Ubuntu 24.04 ARM64
FUSE:      FUSE3
元数据:    SQLite WAL
本地层:    /var/lib/tokenfs/local/gpu0, /var/lib/tokenfs/local/gpu1
远端层:    /var/lib/tokenfs/remote-sim
挂载点:    /mnt/tokenfs
checksum:  fnv1a64
```

说明：

- `remote-sim` 是目录模拟远端层，不代表真实网络性能。
- NVMe-oF 接入脚本已经具备配置化入口。
- 真实 SSD Target IP、NQN、设备名到位后，需要重新采集真实硬件结果。

## 3. 当前系统语义

TokenFS 当前采用：

```text
远端共享主副本 + GPU 本地热缓存副本
```

常见状态：

| 状态 | 含义 |
|---|---|
| `LOCAL_ONLY` | 文件当前只在本地层，常见于新写入或未迁移数据 |
| `REMOTE_ONLY` | 文件当前只在远端层，常见于冷数据或本地空间不足数据 |
| `REMOTE_WITH_LOCAL_CACHE` | 远端保留主副本，本地保留某 GPU 的热点缓存副本 |

关键语义：

- 热点提升和顺序预取不删除远端主副本。
- 缓存 GC 只删除有远端主副本的本地缓存。
- 跨机器共享通过远端主副本完成，不直接把另一个 GPU 节点的本地 SSD 当作共享块设备使用。

## 4. 研究重点

当前保留两个研究重点。

### 4.1 代价驱动型本地缓存管理

目标：

```text
本地空间有限时，让未来价值高的数据留在本地；
低价值、冷数据或有安全替代来源的数据离开本地。
```

当前实现：

- 本地优先写入。
- 本地不足远端溢写。
- 热点提升。
- 顺序预取。
- 本地缓存 GC。
- 价值感知淘汰。
- `EvictionLoss` 模型和 AURA-KV baseline 对比。

核心含义：

```text
删除一个本地副本之前，先估计它被删除后未来访问会多付出多少代价。
```

### 4.2 多 GPU 共享热点副本放置

目标：

```text
当远端主副本被某个 GPU 或某组 GPU 高频访问时，
判断是否值得把它复制到对应 GPU 节点本地。
```

当前实现：

- 识别调用方 GPU。
- 记录累计访问次数。
- 记录短窗口访问事件。
- 判断长期 dominant GPU、最近 dominant GPU 和趋势变化。
- 支持多级亲和状态。
- 支持目标本地副本数量。
- 支持本地副本冷却时间、最短驻留时间和副本上限。
- 支持隐藏本地副本表和管理工具展示。

这个机制不假设所有 GPU 都共享数据。若每个 GPU 工作完全独立，它会自然退化为“谁产生、谁访问、谁本地缓存”。只有前缀共享、KV Cache 共享或任务迁移带来跨 GPU 高频访问时，副本放置才产生意义。

## 5. AURA-KV 模拟层

代码入口：

```text
aura_kv/core.py
aura_kv/demand.py
aura_kv/cost_model.py
aura_kv/layout.py
aura_kv/optimization.py
aura_kv/policies.py
aura_kv/simulator.py
scripts/aura_kv_sim.py
tests/aura_kv_unit_test.py
```

当前支持 15 个策略或 baseline：

```text
RemoteOnly
ProducerLocal
NodeLRU
NodeLFU
SizeAwareLRU
WeightedScoreBaseline
EWMAReplacement
SourceAwareReplacement
PrefixSourceAwareReplacement
StaticNReplica
AffinityOnly
IndependentControllers
AURA-KV
OracleDemand
ExhaustiveOptimal
```

当前支持 8 个场景：

```text
private
node_shared
cluster_shared
hotspot_shift
high_recompute
remote_congestion
demand_estimation_error
tenant_isolation
```

运行：

```bash
python3 scripts/aura_kv_sim.py --output reports/latest/aura-kv-sim
```

输出：

```text
reports/latest/aura-kv-sim/aura_sim_report.md
reports/latest/aura-kv-sim/aura_sim_results.csv
reports/latest/aura-kv-sim/aura_sim_results.json
```

## 6. 当前指标

TokenFS 可观测：

```text
文件逻辑路径、物理路径、tier、size、checksum、state
本地/远端读写次数和字节数
平均读写耗时和最大耗时
本地溢写、热点提升、预取、淘汰次数
GPU 访问统计、亲和状态、最近热点 GPU
本地副本创建、删除、GC 和迁移状态
```

AURA-KV 模拟指标：

```text
local_cache_hit_rate
remote_read_bytes
peer_read_bytes
recomputed_ms
duplicate_bytes
replica_count
replica_churn
migration_bytes
ttft_p50_ms
ttft_p95_ms
ttft_p99_ms
slo_violation_rate
decision_count
```

查看 TokenFS 状态：

```bash
./scripts/tokenfsctl.py status
./scripts/tokenfsctl.py files
./scripts/tokenfsctl.py replicas
./scripts/tokenfsctl.py affinity
./scripts/tokenfsctl.py metrics
./scripts/tokenfsctl.py check
```

## 7. 当前可证明结论

当前能够证明：

- FUSE 统一命名空间可挂载和读写。
- GPU 逻辑目录和本地配额隔离可用。
- 本地优先和远端溢写路径可用。
- 元数据、checksum 和提交状态可观测。
- 远端主副本与本地缓存副本的生命周期可运行。
- 代价驱动替换和共享副本放置已有可运行原型。
- AURA-KV 可以在 8 个模拟场景下对比 15 个策略或 baseline。
- 文档、测试和模拟结果已经按统一入口组织。

当前不能证明：

- 真实 NVMe-oF SSD 的最终带宽。
- 真实网络下 P50/P95/P99 延迟。
- 真实 GPU 推理任务的数据等待时间下降比例。
- 多 GPU 并发访问远端 SSD 时的系统上限。

## 8. 真实环境复测计划

真实环境到位后需要获得：

```text
SSD Target IP
NVMe/TCP 端口
Subsystem NQN
Host NQN / ACL
/dev/nvmeXnY 设备名
Namespace 是否独占
远端挂载目录
GPU 服务器数量和 GPU 拓扑
```

推荐复测：

```bash
./scripts/check_environment.sh
sudo ./scripts/connect_nvme.sh --config config/tokenfs.dev.yaml --backend remote0 --chown-current
./scripts/nvmeof_two_vm_test.sh
./scripts/nvmeof_perf_test.sh
./scripts/strategy_matrix_test.sh
python3 scripts/aura_kv_sim.py --output reports/latest/aura-kv-sim
```

论文最终应补充：

- 直接本地 SSD baseline。
- 直接 NVMe-oF SSD baseline。
- TokenFS baseline。
- TokenFS + 代价驱动型本地缓存管理。
- TokenFS + 多 GPU 共享热点副本放置。
- AURA-KV full。
- P50/P95/P99 延迟。
- 远端读取减少比例。
- 本地命中率提升。
- 副本抖动和空间开销。
