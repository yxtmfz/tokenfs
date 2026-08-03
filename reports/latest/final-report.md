# AURA-KV / TokenFS 统一实验报告

项目名称：

```text
面向 NVMe-oF 分层存储的自适应 KV Cache 联合替换与共享副本管理系统
```

本文件是当前仓库统一数据结果入口，整合 TokenFS 功能验证、AURA-KV 策略模拟、指标观测和真实环境复测计划。

当前结论定位：

```text
当前结果用于验证系统功能、策略逻辑、可观测指标和实验框架；
不作为真实 NVMe-oF SSD 环境下的最终性能结论。
```

谨慎说明：

```text
AURA-KV 当前属于候选研究原型；
不得声称一定能够中稿；
不得未经系统性论文、专利和开源系统检索就声称全球首次；
模拟实验必须标注 SIMULATED RESULT。
```

## 1. 实验环境

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

- 当前 `remote-sim` 是目录模拟，不代表真实远端 SSD 性能。
- 双 VM NVMe-oF 脚本已经具备真实 NVMe/TCP 协议接入能力。
- 真实 SSD Target IP、NQN、设备名到位后，应复用同一套脚本重新采集最终论文数据。

## 2. 当前系统语义

TokenFS 当前采用：

```text
远端共享主副本 + GPU 本地热缓存副本
```

副本状态：

| 状态 | 含义 |
|---|---|
| `LOCAL_ONLY` | 文件只在 GPU 本地层，适合新写入或暂不共享数据 |
| `REMOTE_ONLY` | 文件只在远端层，适合冷数据、共享数据或本地空间不足数据 |
| `REMOTE_WITH_LOCAL_CACHE` | 远端保留主副本，本地保留某 GPU 的热点缓存副本 |

关键点：

- 热点提升和顺序预取不会删除远端主副本。
- 缓存 GC 只删除远端已有主副本的本地缓存。
- 跨机器 GPU 共享通过远端主副本完成，不直接访问另一台机器的本地 SSD。

## 3. 可观测字段

文件与放置：

```text
logical_path
gpu_id
tier(local/remote)
physical_path
size_bytes
checksum
state
primary_tier
has_remote_copy
local_cache_owner_gpu
replica_state
cache_generation
producer_gpu
recompute_cost
remote_access_cost
share_count
dominant_gpu_id
dominant_gpu_read_share_x100
recent_dominant_gpu_id
recent_dominant_gpu_read_share_x100
recent_read_count
affinity_trend
target_local_replica_count
affinity_state
affinity_updated_at
```

策略与性能：

```text
本地/远端读写次数
本地/远端读写字节数
平均读写耗时
最大读写耗时
延迟桶近似 P99
溢写次数和数据量
热点提升次数和数据量
顺序预取次数和数据量
本地缓存创建/删除/GC 次数
价值感知淘汰次数和数据量
迁移到远端/迁移回本地次数
迁移恢复次数
每 GPU 读写次数和字节量
调用方 GPU 识别次数
跨 GPU 访问次数
前台读写 QoS 次数和延迟
后台迁移/预取/淘汰 QoS 次数和延迟
```

查看命令：

```bash
./scripts/tokenfsctl.py status
./scripts/tokenfsctl.py files
./scripts/tokenfsctl.py replicas
./scripts/tokenfsctl.py metrics
./scripts/tokenfsctl.py affinity
./scripts/tokenfsctl.py check
```

## 4. 两个研究重点

当前研究重点围绕同一条数据路径展开：本地 SSD 负责低延迟热点缓存，远端 NVMe-oF SSD 负责共享主副本和容量扩展，系统根据缓存价值和多 GPU 共享访问热度动态调整数据位置。

| 研究点 | 当前工程落地 | 可观测方式 |
|---|---|---|
| AI 价值感知的本地缓存管理 | 管理新写入、本地溢写、热点提升和本地淘汰，让高价值缓存尽量留在本地 | `files`、`metrics`、`eviction_test.sh` |
| 多 GPU 共享热点复制 | 观察哪个 GPU 正在高频读取共享前缀或共享 KV Cache，并把远端主副本复制到热点 GPU 的本地 SSD | `affinity`、`replicas`、`advanced_policy_test.sh` |

当前价值公式：

```text
本地缓存价值 =
复用概率
× 重新计算代价
× 远端访问代价
× GPU 访问亲和度
× 共享收益
÷ 数据大小
```

该公式是启发式框架，不声称数学最优。它的意义是让系统在本地空间有限时，不只是按照 LRU 删除文件，而是优先保护热、重算贵、远端访问代价高、和 GPU 访问关系强的数据。

当前代码中 `remote_access_cost` 以归一化权重参与评分，避免默认配置下把低热度冷数据也误判为高价值。

多 GPU 共享热点复制的核心机制：

```text
1. 通过 TOKENFS_GPU_ID / CUDA_VISIBLE_DEVICES 识别调用方 GPU
2. 记录每个文件被哪些 GPU 读取
3. 使用短窗口访问事件判断最近热点 GPU
4. 如果远端主副本被某个 GPU 高频访问，就在该 GPU 本地创建隐藏缓存副本
5. 后续同一 GPU 再读时优先命中本地副本
6. 使用副本上限、冷却时间和最短驻留时间避免复制抖动
```

这个机制不是默认假设所有 GPU 都共享数据；没有共享访问时，它自然退化为“谁产生谁管理”。只有在前缀共享、KV Cache 共享或任务迁移导致的跨 GPU 高频访问出现时，才触发副本创建。

## 5. AURA-KV 研究实验层

为满足论文级原型要求，当前仓库新增了独立的 AURA-KV 实验层：

```text
aura_kv/core.py
aura_kv/prediction.py
aura_kv/policies.py
aura_kv/simulator.py
scripts/aura_kv_sim.py
tests/aura_kv_unit_test.py
```

它不替代当前 FUSE 主程序，而是用于在无真实 IP、无真实 GPU/NVMe-oF 环境时，先验证两个候选创新的联合策略逻辑。

### 5.1 已实现 baseline

当前 trace simulator 已支持 9 个策略：

```text
RemoteOnly
ProducerLocal
NodeLRU
NodeLFU
StaticNReplica
AffinityOnly
AIReplacementOnly
AlternativeAwareNoLearning
AURA-KV
```

这避免了“只和 LRU 比”的问题。

### 5.2 已实现场景

当前模拟器支持 8 个场景：

```text
private
node_shared
cluster_shared
hotspot_shift
high_recompute
remote_congestion
prediction_error
tenant_isolation
```

覆盖私有缓存、同节点共享、跨节点共享、热点迁移、高重算成本、远端拥塞、预测误差和租户隔离。

### 5.3 模拟实验结果入口

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

当前已生成完整矩阵：

```text
8 个场景 × 9 个策略 = 72 组模拟结果
```

报告第一行明确标注：

```text
SIMULATED RESULT
```

因此这些数据只能说明策略逻辑是否工作，不能作为真实 NVMe-oF 性能结论。

### 5.4 当前 AURA-KV 指标

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

### 5.5 当前测试结果

已通过：

```text
python3 -m unittest tests.aura_kv_unit_test
./scripts/aura_kv_test.sh
python3 scripts/aura_kv_sim.py --output reports/latest/aura-kv-sim
```

含义：

```text
CacheIdentity 能阻止跨 sharing_domain 共享
EWMA 预测器能低置信度回退
共享状态分类具备最小样本限制
模拟器能运行 9 个 baseline
AURA-KV 能跑核心共享/迁移场景
```

### 5.6 TokenFS 主路径中的亲和分类

TokenFS FUSE 主路径当前仍保留较工程化的 GPU 亲和分类，用于真实挂载读写时快速决策；AURA-KV 研究层则在模拟器中进一步抽象为共享拓扑分类和预算化副本放置。

TokenFS 主路径当前使用：

| 状态 | 含义 | 策略含义 |
|---|---|---|
| `GPU_LOCAL_HOT` | 最近访问集中在某张 GPU，且热度高 | 目标是保留 1 个本地热点副本 |
| `GPU_LOCAL_WARM` | 最近访问集中在某张 GPU，但热度一般 | 可以保留 1 个本地温副本 |
| `REMOTE_SHARED_HOT` | 多 GPU 近期都在访问，且整体热 | 远端主副本保留，目标本地副本数可大于 1 |
| `CROSS_GPU_SHARED` | 多 GPU 访问较均衡，但热度不高 | 倾向远端共享，暂不复制太多本地副本 |
| `AFFINITY_SHIFTING` | 最近 dominant GPU 与长期 dominant GPU 不一致 | 表示亲和正在转移，先观测并准备迁移 |
| `REMOTE_COLD` | 最近访问量很低 | 不主动创建本地副本 |
| `MIXED_AFFINITY` | 有偏向但还不够稳定 | 暂不激进迁移，继续观察访问 |
| `UNKNOWN` | 访问样本不足 | 使用默认本地优先/远端溢写策略 |

亲和判断当前同时使用：

```text
累计访问次数：判断长期 dominant GPU
短窗口访问事件：判断最近真正变热的 GPU
长窗口访问事件：判断短期变化是否偏离历史趋势
目标本地副本数：把亲和分类转化为副本策略建议
```

QoS 当前作为工程观测能力保留，不作为论文创新点。它分为两类：

```text
前台 QoS：用户 read/write 路径，直接影响上层推理或训练等待时间
后台 QoS：promote、prefetch、evict 等迁移任务，不能抢占太多前台资源
```

这些指标用于解释前台读写、后台迁移和预取是否互相干扰；后续如果老师要求再扩展公平性，可以作为附加工程实验。

## 5. Token Workload 样例结果

该 workload 模拟机器学习 token shard：

- 16 MiB 普通 shard。
- 96 MiB 大 shard。
- `fallocate` 预分配。
- 顺序写入。
- 重复读取热点 shard。
- 读取连续编号 shard。
- `/gpu0` 与 `/gpu1` 隔离。

| 操作 | 分组 | GPU | 数据量 MiB | 预分配 | 耗时 s | 带宽 MiB/s |
|---|---|---:|---:|---:|---:|---:|
| write | normal-local-fill | 0 | 16 | 1 | 0.232934 | 68.69 |
| write | normal-local-fill | 0 | 16 | 1 | 0.292277 | 54.74 |
| write | normal-local-fill | 0 | 16 | 1 | 0.288402 | 55.48 |
| write | normal-local-fill | 0 | 16 | 1 | 0.284331 | 56.27 |
| write | overflow-sequential | 0 | 16 | 1 | 0.277306 | 57.70 |
| write | overflow-sequential | 0 | 16 | 1 | 0.293451 | 54.52 |
| write | large-remote-spill | 0 | 96 | 1 | 1.149555 | 83.51 |
| write | gpu1-isolation | 1 | 16 | 1 | 0.664263 | 24.09 |
| read | local-hot-read | 0 | 16 | - | 0.226526 | 70.63 |
| read | remote-first-read | 0 | 16 | - | 0.130478 | 122.63 |
| read | remote-second-read | 0 | 16 | - | 0.130932 | 122.20 |
| read | sequential-next-read | 0 | 16 | - | 0.169124 | 94.61 |
| read | large-remote-spill-read | 0 | 96 | - | 0.815721 | 117.69 |
| read | gpu1-isolation-read | 1 | 16 | - | 0.131137 | 122.01 |

解读：

- 目录模拟环境受页缓存、虚拟磁盘和 FUSE 调度影响，所以 `remote-sim` 可能看起来不慢。
- 这组结果主要证明 workload、GPU 隔离、本地/远端元数据路径、预分配和读写闭环可用。
- 真实论文数据不能引用这组结果作为最终性能，只能作为开发阶段功能验证。

## 6. 策略矩阵实验

同一组 token shard workload 下比较：

```text
baseline: 本地优先 + 远端溢写
promote:  热点提升
prefetch: 顺序预取
full:     热点提升 + 顺序预取 + 价值感知淘汰
```

| 策略 | 本地读命中率 % | 远端打开读取 | 热点提升 | 顺序预取 | 本地淘汰 | 平均读 us | 平均写 us | workload 总耗时 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 20.0 | 4 | 0 | 0 | 0 | 2457.9 | 3536.05 | 2.6623 |
| promote | 30.0 | 4 | 1 | 0 | 1 | 2469.35 | 3659.58 | 2.6757 |
| prefetch | 30.0 | 3 | 0 | 1 | 1 | 2514.52 | 3475.61 | 2.6755 |
| full | 40.0 | 3 | 1 | 1 | 2 | 2621.17 | 3884.29 | 2.7569 |

### 本地读命中率

```text
baseline   ██████████████░░░░░░░░░░░░░░ 20.0%
promote    █████████████████████░░░░░░░ 30.0%
prefetch   █████████████████████░░░░░░░ 30.0%
full       ████████████████████████████ 40.0%
```

### 远端打开读取次数

```text
baseline   ████████████████████████████ 4 次
promote    ████████████████████████████ 4 次
prefetch   █████████████████████░░░░░░░ 3 次
full       █████████████████████░░░░░░░ 3 次
```

解读：

- `promote` 提升本地读命中率，因为远端热点 shard 被复制成本地缓存。
- `prefetch` 减少远端打开读取，因为下一片连续 shard 被提前拉回本地。
- `full` 本地读命中率最高，说明热点提升、顺序预取和价值感知淘汰可以协同工作。
- `full` 在目录模拟中总耗时没有降低，是因为迁移、预取、淘汰也有额外开销；真实 NVMe-oF 环境中应重点观察远端读取等待是否下降。

## 7. 专项验证脚本

```bash
./scripts/integration_test.sh
./scripts/token_workload_test.sh
./scripts/strategy_matrix_test.sh
./scripts/promote_test.sh
./scripts/prefetch_test.sh
./scripts/eviction_test.sh
./scripts/replica_lifecycle_test.sh
./scripts/advanced_policy_test.sh
./scripts/fault_injection_test.sh
```

专项覆盖：

- 基础 FUSE 读写、目录、删除、重命名。
- 本地优先和远端溢写。
- 热点提升：远端主副本保留，本地生成 GPU 热缓存。
- 顺序预取：连续 shard 的下一片提前生成本地缓存。
- 缓存 GC：只删除本地缓存，不删除远端主副本。
- 价值感知淘汰：低价值数据优先迁远端或删本地缓存。
- 多 GPU 共享热点复制：识别调用方 GPU，记录跨 GPU 访问，计算短窗口热度、亲和趋势、多级状态和目标副本数。
- QoS 工程观测：记录并限制每 GPU 前台读写 IOPS，同时观测后台迁移/预取/淘汰开销。
- 故障恢复：临时文件和未完成迁移状态可恢复。

## 8. 当前能证明什么

当前能证明：

```text
TokenFS 的 FUSE 文件系统功能可用
GPU namespace 和本地配额隔离可用
本地优先、远端溢写、热点提升、顺序预取和价值感知淘汰可运行
远端主副本 + 本地热缓存的副本生命周期可运行
SQLite 元数据、checksum、提交状态和一致性检查可用
跨层迁移已经具备可恢复状态机
价值感知本地缓存管理和多 GPU 共享热点复制已有可运行原型
调用方 GPU、累计 dominant GPU、短窗口 dominant GPU、亲和趋势、共享热状态和目标副本数已经进入元数据和管理工具
前台 I/O 与后台迁移/预取/淘汰已经分开观测
策略矩阵实验可作为论文消融实验模板
```

当前不能证明：

```text
真实 NVMe-oF SSD 的最终带宽
真实网络下的 P50/P95/P99 延迟
真实 GPU 推理任务的数据等待时间下降比例
多 GPU 并发访问远端 SSD 时的系统上限
```

## 9. 真实环境到位后的复测计划

拿到真实环境后替换：

```text
SSD Target IP
NVMe/TCP 端口
Subsystem NQN
/dev/nvmeXnY 设备名
挂载目录 /srv/tokenfs/remote0
```

执行：

```bash
./scripts/check_environment.sh
sudo ./scripts/connect_nvme.sh --config config/tokenfs.dev.yaml --backend remote0 --chown-current
./scripts/nvmeof_two_vm_test.sh
./scripts/nvmeof_perf_test.sh
./scripts/strategy_matrix_test.sh
```

论文最终结果建议补充：

```text
直接本地 SSD baseline
直接 NVMe-oF SSD baseline
TokenFS baseline
TokenFS + AI 价值感知本地缓存管理
TokenFS + 多 GPU 共享热点复制
TokenFS full
P50/P95/P99 延迟
多 GPU 并发读取
GPU 等待数据时间
共享缓存命中率
跨 GPU 副本创建次数
远端读取减少比例
```
