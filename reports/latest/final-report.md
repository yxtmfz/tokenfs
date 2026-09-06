# AURA-KV / TokenFS 最新统一结果报告

项目名称：

```text
面向多 GPU 大模型 KV Cache 的本地与 NVMe-oF 远端自适应分层缓存系统
```

本文是当前仓库的统一结果入口。人工阅读优先看本文；机器可读数据保留在 `reports/latest/` 下的 CSV、JSON 和 JSONL 文件中。

## 1. 当前结论先说清楚

当前项目已经完成两类验证：

| 类型 | 是否真实 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| 双 VM NVMe-oF 性能基线 | 真实 Linux NVMe/TCP 协议链路 | NVMe-oF Host/Target 接入、TokenFS 远端挂载、FUSE 叠加读写路径 | 真实物理 SSD、真实高速网卡、真实 GPU 集群性能 |
| AURA-KV 策略模拟 | 模拟/代理结果 | 缓存替换、副本放置、联合控制器相对趋势和可解释性 | 真实 GPU 推理 TTFT、真实 P99、真实业务收益 |

因此，当前可以用于论文前期汇报的表述是：

```text
系统原型已经在两台 Ubuntu VM 上跑通真实 NVMe/TCP Host/Target 链路，
并完成 TokenFS 远端溢写和性能基线测试；
AURA-KV 的缓存替换与共享副本放置策略已通过 trace-driven simulator 完成多场景对比。
```

不要写成：

```text
已经完成真实 GPU 集群和真实物理 NVMe SSD 论文实验。
```

## 2. 当前双 VM 实验环境

```text
Client VM:  tokenfs-dev
Client IP:  192.168.64.2
角色:       TokenFS / Linux nvme-tcp Host

Target VM:  tokenfs-target
Target IP:  192.168.64.3
角色:       Linux nvmet Target

Target Port:   4420
Subsystem NQN: nqn.2026-07.local.tokenfs:remote0
Client Device: /dev/nvme0n1
Remote Mount:  /srv/tokenfs/remote0
TokenFS Mount: /mnt/tokenfs
```

这不是普通目录模拟。客户端通过 `nvme discover` 和 `nvme connect` 发现并连接远端 NVMe/TCP Target，随后把 `/dev/nvme0n1` 挂载成 TokenFS 的远端层。

限制也要写清楚：Target 后端使用 VM 中的 loop/虚拟磁盘，网络是本机 UTM 虚拟网络，所以性能趋势可用于开发阶段验证，不能等同于真实服务器 SSD 与高速网络。

## 3. 双 VM NVMe-oF 功能验证

功能测试命令：

```bash
./scripts/nvmeof_two_vm_test.sh 192.168.64.3
```

结果：

```text
TokenFS NVMe-oF two-VM test passed.
```

元数据结果：

| 逻辑路径 | GPU | tier | 物理路径 | 大小 |
|---|---:|---|---|---:|
| `/gpu0/nvmeof-demo/local.tokens` | 0 | local | `/var/lib/tokenfs/local/gpu0/nvmeof-demo/local.tokens` | 37 B |
| `/gpu0/nvmeof-demo/remote-spill.tokens` | 0 | remote | `/srv/tokenfs/remote0/gpu0/nvmeof-demo/remote-spill.tokens` | 96 MiB |

这说明：

- 小文件保留在 GPU0 本地层。
- 大文件超过本地 64 MiB 配额后写入远端层。
- 远端层不是 `remote-sim`，而是 `/dev/nvme0n1` 挂载出来的 NVMe-oF 目录。

## 4. 双 VM NVMe-oF 性能基线

性能测试命令：

```bash
./scripts/nvmeof_perf_test.sh 192.168.64.3
```

原始结果文件：

```text
reports/latest/report.md
reports/latest/report.html
reports/latest/summary.csv
reports/latest/fio-json/
```

核心结果：

| 用例 | 操作 | 数据量 | 带宽 | 平均延迟 | P99 |
|---|---|---:|---:|---:|---:|
| direct-local-read | read | 32 MiB | 2461.54 MiB/s | 305.39 us | 1044.48 us |
| direct-local-write | write | 32 MiB | 1000.00 MiB/s | 976.65 us | 5865.47 us |
| direct-remote-read | read | 32 MiB | 359.55 MiB/s | 2691.22 us | 8093.70 us |
| direct-remote-write | write | 32 MiB | 2909.09 MiB/s | 328.77 us | 569.34 us |
| tokenfs-local-read | read | 32 MiB | 46.51 MiB/s | 21089.33 us | 53215.23 us |
| tokenfs-local-write | write | 32 MiB | 106.67 MiB/s | 9265.55 us | 12517.38 us |
| tokenfs-remote-read | read | 96 MiB | 115.66 MiB/s | 6631.07 us | 8585.22 us |
| tokenfs-remote-spill-write | write | 96 MiB | 271.19 MiB/s | 3669.19 us | 56360.96 us |

当前可以得出的工程结论：

- 直接远端读取比直接本地读取慢，平均延迟约为 8.8 倍，说明网络路径和 Target 处理会带来额外等待。
- TokenFS 路径明显慢于直接目录读写，主要来自 FUSE 用户态转发、元数据维护、checksum 和策略逻辑。
- TokenFS 远端读取慢于直接远端读取，说明热点提升、预取和本地缓存管理有存在价值。
- 远端写入看起来可能高于本地写入，这是 VM 页缓存、顺序 1 MiB 块和虚拟磁盘共同造成的开发环境现象，不能说明远端物理 SSD 一定比本地快。

## 5. 策略矩阵测试

策略矩阵命令：

```bash
./scripts/strategy_matrix_test.sh
```

原始结果：

```text
reports/latest/strategy-matrix/strategy_summary.csv
reports/latest/strategy-matrix/strategy_report.md
```

摘要：

| 策略 | 本地读命中率 | 本地写命中率 | 远端打开读 | 本地打开读 | 平均读耗时 |
|---|---:|---:|---:|---:|---:|
| baseline | 20.00% | 41.67% | 4 | 2 | 2728.33 us |
| promote | 20.00% | 41.67% | 4 | 2 | 2499.12 us |
| prefetch | 20.00% | 41.67% | 4 | 2 | 2568.05 us |
| full | 20.00% | 41.67% | 4 | 2 | 2506.28 us |

这组矩阵是开发环境工程测试，主要证明功能开关、指标采集和报告生成链路正常。由于 workload 较小，本地命中率差异不明显；论文实验应进一步扩大数据规模、访问轮次和容量压力。

## 6. AURA-KV 策略模拟

模拟命令：

```bash
python3 scripts/aura_kv_sim.py --output reports/latest/aura-kv-sim
```

原始结果：

```text
reports/latest/aura-kv-sim/aura_sim_report.md
reports/latest/aura-kv-sim/aura_sim_results.csv
reports/latest/aura-kv-sim/aura_sim_results.json
```

模拟层用于比较当前代码中的 16 个策略或基线：

```text
RemoteOnly
LocalFirst
ProducerLocal
LRU-Local
LFU-Local
SizeAwareLRU
WeightedScoreBaseline
EWMAReplacement
DualWindowReplacement
SourceAwareReplacement
PrefixSourceAwareReplacement
StaticNReplica
AffinityOnly
WA-Affinity-Independent
AURA-Joint
OracleDemand
ExhaustiveOptimal
```

覆盖场景：

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

这部分结果必须标注：

```text
SIMULATED RESULT
```

它证明的是算法逻辑和相对趋势，不是真实硬件速度。

## 7. 当前系统机制是否闭环

当前已经闭环的路径：

```text
FUSE 前台请求
  -> 本地配额判断
  -> 本地或远端放置
  -> SQLite 元数据提交
  -> checksum 和状态记录
  -> tokenfsctl 指标查看
```

双 VM NVMe-oF 路径：

```text
TokenFS remote tier
  -> /srv/tokenfs/remote0
  -> ext4
  -> /dev/nvme0n1
  -> Linux nvme-tcp Host
  -> UTM 虚拟网络
  -> Linux nvmet Target
  -> loop/虚拟磁盘
```

AURA-KV 策略路径：

```text
访问事件
  -> 需求预测
  -> 代价模型
  -> EvictionLoss / ReplicaGain
  -> 候选动作
  -> 后台任务队列
  -> 执行器
  -> 布局和指标反馈
```

## 8. 当前适合写进论文的内容

可以写：

- 设计并实现了一个 FUSE 分层缓存文件系统原型 TokenFS。
- 实现了本地 SSD 配额隔离、远端溢写、SQLite 元数据、checksum 和状态恢复。
- 实现了 Linux NVMe/TCP 双 VM 实验环境，验证了远端 NVMe-oF 作为 TokenFS 后端的可行性。
- 提出了面向 KV Cache 的价值感知缓存替换模型，用未来访问代价衡量本地副本是否值得保留。
- 提出了面向多 GPU 共享热点的副本放置模型，用访问分布、收益密度和容量预算决定复制到哪些节点。
- 构建了 trace-driven simulator，对比 RemoteOnly、LocalFirst、LRU/LFU、SizeAwareLRU、StaticNReplica、AffinityOnly、AURA-Joint 和 OracleDemand 等策略。

不建议现在写：

- 已在真实 GPU 集群中显著降低 TTFT。
- 已验证真实 NVMe SSD 和 100GbE/RDMA 网络性能。
- 已完成生产级分布式文件系统。

## 9. 下一步论文实验增强

如果继续在当前双 VM 环境上增强实验，优先做：

1. 增大 workload：把 32/96 MiB 扩展到 512 MiB、1 GiB，降低页缓存偶然性。
2. 增加随机小块读：加入 4 KiB、16 KiB、64 KiB，观察 IOPS 和尾延迟。
3. 增加冷/热两轮测试：第一轮远端读取，第二轮本地缓存命中。
4. 增加容量压力：让本地配额明显小于工作集，逼出真实淘汰差异。
5. 增加 Target 重启、断连、重连和恢复测试。
6. 增加 Dashboard 运行截图，用事件流解释一次策略决策。

## 10. 一句话总结

当前项目已经不是停留在纯理论或纯目录模拟阶段：TokenFS 已经接入双 VM 真实 NVMe/TCP 协议路径，并拿到了可复现的功能和性能基线；AURA-KV 的核心策略仍通过模拟器验证，适合作为论文方法和前期系统实验基础。
