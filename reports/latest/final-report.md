# TokenFS 最新实验总报告

项目名称：

```text
面向多 GPU 大模型 KV Cache 的本地-远程自适应分层文件系统
```

本文件是仓库唯一保留的数据结果入口。它整合当前开发 VM 环境下的功能验证、策略实验、指标观测和真实环境复测计划。

当前结论定位：

```text
当前结果用于验证系统功能、策略逻辑、可观测指标和实验框架；
不作为真实 NVMe-oF SSD 环境下的最终性能结论。
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

- 当前 remote-sim 是目录模拟，不代表真实远端 SSD 性能。
- 双 VM NVMe-oF 脚本已经具备真实 NVMe/TCP 协议接入能力。
- 真实 SSD Target IP、NQN、设备名到位后，应复用同一套脚本重新采集最终论文数据。

## 2. 当前已具备的可测指标

文件与放置：

```text
logical_path
gpu_id
tier(local/remote)
physical_path
size_bytes
checksum
state
producer_gpu
recompute_cost
remote_access_cost
share_count
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
价值感知淘汰次数和数据量
迁移到远端/迁移回本地次数
迁移恢复次数
每 GPU 读写次数和字节量
QoS 延迟次数和总延迟
```

查看命令：

```bash
./scripts/tokenfsctl.py status
./scripts/tokenfsctl.py files
./scripts/tokenfsctl.py metrics
./scripts/tokenfsctl.py affinity
./scripts/tokenfsctl.py check
```

## 3. Token Workload 样例结果

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

- 目录模拟环境受页缓存、虚拟磁盘和 FUSE 调度影响，所以 remote-sim 可能看起来不慢。
- 这组结果主要证明 workload、GPU 隔离、本地/远端元数据路径、预分配和读写闭环可用。
- 真实论文数据不能引用这组结果作为最终性能，只能作为开发阶段功能验证。

## 4. 策略矩阵实验

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

- `promote` 提升本地读命中率，因为远端热点 shard 被迁回本地。
- `prefetch` 减少远端打开读取，因为下一片连续 shard 被提前拉回本地。
- `full` 本地读命中率最高，说明热点提升、顺序预取和价值感知淘汰可以协同工作。
- `full` 在目录模拟中总耗时没有降低，是因为迁移、预取、淘汰也有额外开销；真实 NVMe-oF 环境中应重点观察远端读取等待是否下降。

## 5. 三个创新点的当前工程落地

| 创新点 | 当前实现状态 | 可观测方式 |
|---|---|---|
| AI 价值感知放置 | 已接入淘汰和远端提升决策，支持配置阈值 | `tokenfsctl.py files`、`metrics` |
| GPU 亲和感知 | 已记录每个文件按 GPU 的读取统计 | `tokenfsctl.py affinity` |
| 多 GPU QoS | 已记录每 GPU 读写量，并支持按 GPU 读/写 IOPS 限速 | `metrics`、`advanced_policy_test.sh` |

### 工程可靠性能力

跨层迁移一致性是文件系统必备能力，不作为论文创新点单独包装。当前实现把本地到远端、远端到本地的迁移拆成可恢复状态：

```text
LOCAL -> COPYING_TO_REMOTE -> REMOTE_READY -> COMMITTED
REMOTE -> COPYING_TO_LOCAL -> LOCAL_READY -> COMMITTED
```

它依赖 SQLite WAL、临时文件、fsync、原子 rename、checksum 和启动恢复，目标是在进程崩溃或远端中断后仍能恢复到可解释状态。

P95/P99 延迟仍保留为性能评估指标，但不再作为当前论文主创新点。由于当前系统规模和虚拟环境较小，P99 驱动迁移难以稳定形成可复现实验收益，后续不把它作为主线。

## 6. 高级策略专项验证

新增专项脚本：

```bash
./scripts/advanced_policy_test.sh
```

该脚本验证：

- 价值感知淘汰会优先保护高价值热点文件；
- GPU 亲和统计能记录文件被哪个 GPU 读取；
- 每 GPU QoS 限速会产生可观测延迟；
- `tokenfsctl.py metrics`、`affinity`、`check` 均可正常输出。

## 7. 当前能证明什么

当前能证明：

- TokenFS 的 FUSE 文件系统功能可用。
- GPU namespace 和本地配额隔离可用。
- 本地优先、远端溢写、热点提升、顺序预取和价值感知淘汰逻辑可运行。
- SQLite 元数据、checksum、提交状态和一致性检查可用。
- 跨层迁移已经具备可恢复状态机。
- GPU 亲和、价值感知放置和 QoS 限速都已经有可运行原型。
- 策略矩阵实验可作为论文消融实验模板。

当前不能证明：

- 真实 NVMe-oF SSD 的最终带宽。
- 真实网络下的 P95/P99 延迟。
- 真实 GPU 推理任务的等待时间下降比例。
- 多 GPU 并发时的系统性能上限。

## 8. 真实环境到位后的复测计划

拿到真实环境后替换配置：

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
sudo ./scripts/connect_nvme.sh config/tokenfs.dev.yaml
./scripts/nvmeof_two_vm_test.sh
./scripts/nvmeof_perf_test.sh
./scripts/strategy_matrix_test.sh
```

论文最终结果建议补充：

```text
直接本地 SSD baseline
直接 NVMe-oF SSD baseline
TokenFS baseline
TokenFS + 热点提升
TokenFS + 顺序预取
TokenFS + 价值感知淘汰
TokenFS full
P50/P95/P99 延迟
多 GPU 并发读取
GPU 等待数据时间
Jain 公平性指数
SLO 违反率
```
