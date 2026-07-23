# TokenFS 最新实验总报告

本报告是当前仓库唯一保留的数据结果入口。它整合了开发 VM 环境下的 token shard workload、系统指标、文件分布和策略矩阵实验。

当前结果的定位是：

```text
验证 TokenFS 功能闭环、策略逻辑和实验框架；
不作为真实 NVMe-oF SSD 环境下的最终性能结论。
```

## 实验环境

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

- 当前远端层是目录模拟，不是真实 SSD Target。
- 双 VM NVMe-oF 路径已经有脚本支持，但最终绝对性能仍需真实实验室环境复测。
- 当前报告主要看策略是否生效，而不是宣称真实网络性能。

## Token Workload 结果

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

- 当前目录模拟环境会受到页缓存、虚拟磁盘和 FUSE 调度影响，因此远端模拟读写可能看起来不慢。
- 这组结果可以证明 workload、预分配、GPU 隔离、本地/远端元数据路径都能跑通。
- 真实论文数据应在 NVMe-oF SSD 和真实网络上重新采集。

## 系统指标

| 指标 | 当前值 |
|---|---:|
| 读请求 | 1408 次 / 176.00 MiB |
| 写请求 | 208 次 / 208.00 MiB |
| 本地读 | 256 次 / 32.00 MiB |
| 远端读 | 1152 次 / 144.00 MiB |
| 本地写 | 80 次 / 80.00 MiB |
| 远端写 | 128 次 / 128.00 MiB |
| 本地读命中率 | 18.2% |
| 本地写命中率 | 38.5% |
| 平均读耗时 | 1756.2 us |
| 平均写耗时 | 3663.9 us |
| 文件打开读取 | 6 次 |
| 本地打开读取 | 2 次 |
| 远端打开读取 | 4 次 |
| 远端初始放置 | 3 次 |
| 预分配次数 | 8 次 |
| 预分配数据量 | 208.00 MiB |

## 文件分布

| 逻辑路径 | GPU | 层级 | 大小 MiB | 状态 |
|---|---:|---|---:|---|
| `/gpu0/dataset-a/shard-000000.tokens` | 0 | local | 16 | COMMITTED |
| `/gpu0/dataset-a/shard-000001.tokens` | 0 | local | 16 | COMMITTED |
| `/gpu0/dataset-a/shard-000002.tokens` | 0 | local | 16 | COMMITTED |
| `/gpu0/dataset-a/shard-000003.tokens` | 0 | local | 16 | COMMITTED |
| `/gpu0/dataset-a/shard-000100.tokens` | 0 | remote | 16 | COMMITTED |
| `/gpu0/dataset-a/shard-000101.tokens` | 0 | remote | 16 | COMMITTED |
| `/gpu0/dataset-a/shard-900000.tokens` | 0 | remote | 96 | COMMITTED |
| `/gpu1/dataset-a/shard-000000.tokens` | 1 | local | 16 | COMMITTED |

这说明：

- GPU0 的本地配额被普通 shard 占用后，后续部分 shard 进入 remote 层。
- GPU1 有独立 namespace 和本地目录。
- 所有记录都处于 `COMMITTED`，没有未完成写入。

## 策略矩阵实验

该实验用同一组 token shard workload 比较四种策略：

```text
baseline  本地优先 + 远端溢写
promote   热点提升
prefetch  顺序预取
full      热点提升 + 顺序预取 + Cost-aware 淘汰
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

- `promote` 能提升本地读命中率，因为远端热点 shard 重复读取后回迁本地。
- `prefetch` 能减少远端打开读取次数，因为下一片连续 shard 提前被拉回本地。
- `full` 的本地读命中率最高，说明热点提升、顺序预取和 Cost-aware 淘汰能协同工作。
- 当前 `full` 的总耗时没有变低，是因为目录模拟环境下迁移、预取和淘汰本身也有开销；真实 NVMe-oF 环境中，需要重点观察它是否减少远端读取等待。

## 当前能证明什么

当前结果可以证明：

- TokenFS 的 FUSE 文件系统功能可用。
- GPU 本地配额和 namespace 隔离可用。
- 本地优先、远端溢写、热点提升、顺序预取、Cost-aware 淘汰逻辑可用。
- SQLite 元数据、checksum、提交状态和一致性检查可用。
- 策略矩阵实验已经能作为论文消融实验模板。

当前结果不能证明：

- 真实 NVMe-oF SSD 的最终带宽。
- 真实网络下的 P99 延迟。
- 真实 GPU 训练任务的等待时间下降比例。
- 多 GPU 并发时的系统上限。

## 真实环境到位后的复现实验

拿到真实环境后，按同一套流程复测：

```bash
./scripts/check_environment.sh
sudo ./scripts/connect_nvme.sh config/tokenfs.dev.yaml
./scripts/nvmeof_two_vm_test.sh
./scripts/nvmeof_perf_test.sh
./scripts/strategy_matrix_test.sh
```

真实论文版结果应补充：

- 直接本地 SSD 基线。
- 直接 NVMe-oF SSD 基线。
- TokenFS baseline。
- TokenFS promote。
- TokenFS prefetch。
- TokenFS full。
- P95/P99 延迟。
- 多 GPU 并发读取。
- GPU 等待数据时间。
