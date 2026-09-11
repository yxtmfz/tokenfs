# 实验与结果

本文是实验设计和结果解释入口。最新数字以 [../reports/latest/final-report.md](../reports/latest/final-report.md) 和 `reports/latest/paper-experiments/` 为准。

## 1. 实验层次

| 层次 | 是否真实 | 作用 |
|---|---|---|
| Python 单元测试 | 真实代码逻辑 | 验证模型、任务队列和策略性质 |
| FUSE 功能测试 | 真实文件系统路径 | 验证 TokenFS 基础文件操作 |
| 双 VM NVMe-oF | 真实 Linux NVMe/TCP 协议 | 验证 Host/Target 和远端挂载 |
| 实验室 NVMe-oF baseline | 真实内网协议链路 | 测量本地 NVMe 与远端 NVMe-oF 差距 |
| 真实 TokenFS workload | 真实 FUSE 程序耗时 | 直接比较不同策略是否降低总耗时、提高吞吐 |
| trace-driven simulator | 模拟/代理 | 比较不同策略和消融组合 |

## 2. 统一论文实验

运行：

```bash
python3 scripts/paper_experiments.py
```

通过 NVMe-oF 检查后输出：

```text
reports/latest/paper-experiments/
├── paper_experiments_report.md
├── 01_trace_replay/trace_summary.csv
├── 02_e2e_latency/latency_summary.csv
├── 03_sensitivity/sensitivity_summary.csv
├── 04_nvmeof_baseline/real_nvmeof_summary.csv
├── 05_performance_summary/performance_summary.csv
├── 06_real_speed_benchmark/real_speed_summary.csv
└── figures/
```

四项实验：

| 实验 | 目的 | 结果性质 |
|---|---|---|
| Trace 回放 | 多场景比较策略整体表现 | 模拟结果 |
| 端到端延迟代理 | 比较请求访问代价分布 | 代理结果 |
| 参数敏感性 | 检查容量、远端 P99、预算变化下是否稳定 | 模拟结果 |
| NVMe-oF baseline | 汇总真实 NVMe/TCP fio 数据 | 真实链路摘要 |

真实 TokenFS workload 速度实验需要 Linux/FUSE 环境，单独运行：

```bash
TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/real_speed_benchmark.sh
```

默认情况下，该脚本会在关键阶段和每次逻辑读取计时前请求清理 Linux page cache。清缓存动作会写入 `summary.csv` 的 `cache_control` 行，但不会计入 `wall_time_s`、`effective_mib_s` 和 `read_mib_s`。这样做是为了避免实验数据集小于内存时，RemoteOnly 的重复读取被 DRAM 页缓存加速，导致远端 NVMe-oF 和本地 SSD 的真实差异被掩盖。

输出：

```text
reports/latest/paper-experiments/06_real_speed_benchmark/
├── real_speed_report.md
├── real_speed_summary.csv
└── figures/
```

这项实验不使用成本模型权重，直接记录实际运行时间：

| 指标 | 含义 |
|---|---|
| `wall_time_s` | 整个 token shard workload 实际花费的秒数，越低越好 |
| `effective_mib_s` | workload 总读写数据量除以总耗时，越高越好 |
| `speedup_vs_baseline` | 相对 `RemoteOnly` 的实际加速比，大于 1 表示真的更快 |
| `read_mib_s` | 只统计读操作的数据量除以读耗时，更接近 KV Cache 获取速度 |
| `read_speedup_vs_baseline` | 读路径相对 `RemoteOnly` 的吞吐提升 |
| `steady_reuse_mib_s` | 策略生效后，热点/预取/跨 GPU 复用读取阶段的吞吐，越高越好 |
| `steady_reuse_vs_baseline` | 复用阶段相对 `RemoteOnly` 的吞吐比，大于 1 表示后台动作开始产生读取收益 |
| `avg_read_us` / `avg_write_us` | TokenFS 记录的平均读写耗时 |
| `remote_read_open` | 读取时打开远端文件的次数，越少通常越好 |

真实速度 workload 的默认参数已经从短流程验证改成更强调热点复用：热点 shard、连续 shard 和跨 GPU 共享 shard 会在同一个 loader 进程里批量重复读取，减少测试程序启动开销；同时默认使用 `posix_fadvise(DONTNEED)` 尽量降低 Linux 页缓存把远端 NVMe-oF 读取结果缓存到内存后造成的测量偏差。

AURA-Joint 的策略动作分成前台和后台两类。前台只负责完成当前读写和记录访问信息；热点提升、顺序预取和跨 GPU 本地副本创建进入后台执行，服务于后续请求。这样可以避免“为了减少未来远端读取，却把当前请求卡在复制过程里”的实现问题。

真实速度实验按论文消融分类运行：

| 策略 | 验证点 |
|---|---|
| `RemoteOnly` | 不使用本地缓存时，远端容量层的下界表现 |
| `LocalFirst` | 只有本地优先和远端溢写，没有主动替换 |
| `LRU-Local` | 传统最近最少使用替换 |
| `LFU-Local` | 传统最少访问次数替换 |
| `AURA-Joint` | 价值感知、GPU 亲和和后台动作的联合策略 |

`promote_count`、`prefetch_count`、`evict_count` 和 `cross_gpu_local_replica_hit` 只作为内部动作统计，用来解释 `AURA-Joint` 为什么快或为什么不快，不再作为主对照组名称。

真实 workload 不是简单顺序读写压测。它会为每轮消融创建独立逻辑命名空间，先在远端 NVMe-oF 挂载目录准备 canonical KV shard，再填满本地冷缓存，然后制造容量压力、热点重复读取、连续 shard 读取和跨 GPU 共享读取。这样可以明确观察：

- 本地淘汰是否真的发生；
- 远端热点是否被提升到本地；
- 顺序 shard 是否被预取；
- 跨 GPU 访问是否产生本地副本；
- 这些动作是否最终减少远端读取并改善后续复用阶段吞吐。

该脚本默认强制检查 NVMe-oF 直连挂载：配置里的远端后端必须是 `type: nvmeof`，`nvme_target_ip` 必须是真实 Target IP，`root` 必须指向 `/srv/tokenfs/remote0` 这类挂载目录，并且该目录的实际挂载源必须是 `/dev/nvme...`。如果仍然使用 `/var/lib/tokenfs/remote-sim`，或 `nvme_target_ip` 是 `127.0.0.1` / `localhost`，脚本会直接停止，避免把目录模拟或 SSH tunnel 结果误写成直连 NVMe-oF 端到端速度。

在解释真实速度前，应先运行环境差距诊断：

```bash
TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/nvmeof_gap_diagnostic.sh
```

它只测本地目录和 NVMe-oF 挂载目录的原始顺序读写吞吐，不涉及任何 AURA 策略。如果本地/远端读吞吐比接近 `1.0x`，说明当前环境中远端并不比本地慢多少，AURA 减少远端访问也很难转换成明显的总耗时收益。此时实验结论应写成：当前环境已经验证协议接入、后台动作、远端访问减少和系统机制，但速度收益需要在更真实的物理网络差距或可记录的网络校准条件下测量。

## 3. 当前主要结果

| 策略 | 本地命中率 | 远端读取 | P99 代理延迟 | 综合代价/请求 |
|---|---:|---:|---:|---:|
| RemoteOnly | 0.0000 | 2244.77 MiB | 9.0188 ms | 3.1889 |
| LocalFirst | 0.7290 | 949.23 MiB | 5.5199 ms | 1.8880 |
| LRU-Local | 0.7362 | 400.62 MiB | 3.0247 ms | 1.7085 |
| LFU-Local | 0.7586 | 380.31 MiB | 3.0594 ms | 1.5691 |
| DualWindowReplacement | 0.8907 | 146.15 MiB | 1.4685 ms | 0.7717 |
| AURA-Joint | 0.8822 | 228.31 MiB | 1.4749 ms | 0.5376 |

解释：

- AURA-Joint 的核心优势是综合代价最低，而不是每个单项指标都第一。
- DualWindow 的命中率和远端读取很好，但没有完整考虑迁移、重复副本和布局抖动。
- AURA-Joint 更适合作为论文主策略，因为它把保留、复制、淘汰和约束放在一个共同目标里。

## 4. 消融实验

消融入口：

```bash
python3 scripts/ablation_experiment.py
```

对照策略：

| 策略 | 验证点 |
|---|---|
| RemoteOnly | 全部走远端的下界 |
| LocalFirst | 只有本地优先，没有动态策略 |
| LRU/LFU | 传统替换策略 |
| DualWindowReplacement | 时间窗口和趋势判断 |
| SourceAwareReplacement | 来源代价建模 |
| AffinityOnly | 只按 GPU 亲和复制 |
| WA-Affinity-Independent | 替换和放置分开决策 |
| AURA-Joint | 完整联合模型 |
| OracleDemand | 理想未来信息参考 |

workload 覆盖：

```text
private
node_shared
cluster_shared
hotspot_shift
high_recompute
remote_congestion
demand_estimation_error
tenant_isolation
scan_pollution
large_object_pollution
multi_gpu_shared_burst
tight_capacity_thrash
expensive_vs_cheap_mix
```

## 5. 指标

| 指标 | 含义 |
|---|---|
| local hit rate | 请求命中本地 READY 副本比例 |
| remote read bytes | 从远端 NVMe-oF 权威层读取的数据量 |
| migration bytes | 后台复制、预取或迁移的数据量 |
| replica churn | 副本创建和删除抖动 |
| P50/P95/P99 proxy latency | 模拟器中的访问代价分位数 |
| objective_cost_per_request | 综合服务代价，论文主对比指标 |
| normalized_to_lru | 等效性能指数，`LRU-Local = 1.00x`，越高越好 |
| wall_time_s | 真实 workload 总耗时，越低越好 |
| speedup_vs_baseline | 真实 workload 相对 `RemoteOnly` 加速比，越高越好 |
| IOPS | 每秒 I/O 次数，小块随机读写时尤其重要 |

`objective_cost_per_request` 包含：

```text
前台访问延迟
+ 远端读取代价
+ Peer 读取代价
+ 后台迁移代价
+ 重复副本空间代价
+ 副本创建/删除抖动代价
```

它不是一个真实延迟，而是策略比较用的综合代理目标。

因此论文里要分开写：

```text
成本模型指标：解释策略为什么可能更优。
真实速度指标：验证策略在当前系统和 workload 下到底有没有跑得更快。
```

如果两者结论不一致，应优先相信真实速度实验，再调整系统实现、策略阈值或成本权重。

但这里的“调整”不能理解成专门构造有利于 AURA 的极端访问序列。正确做法是：

- 先用 `nvmeof_gap_diagnostic.sh` 证明当前本地/远端物理差距是否足够；
- 再检查 AURA 的后台迁移是否阻塞前台请求；
- 再降低前台路径的实现开销，例如减少每次 FUSE read/write 中的同步数据库写入；
- 然后用迁移收益门槛约束热点提升和跨 GPU 复制，只在预计未来复用能覆盖复制成本时才搬；
- 最后才根据真实 KV Cache trace 调整阈值和权重。

如果环境本身没有远端代价，任何缓存系统都不应被期待产生大幅速度提升。

当前 AURA 的后台动作不再只看命中率，而是经过三道门槛：

| 门槛 | 配置项 | 含义 |
|---|---|---|
| 复用次数 | `migration_min_reuse_reads` | 至少观察到一定次数复用，避免一热就搬 |
| 数据价值 | `value_promote_threshold` | 对象本身要足够有价值，低价值大对象不轻易进本地 |
| 收益摊销 | `migration_min_benefit_x100`、`migration_copy_cost_per_mib` | 预计未来少走远端节省的代价，要能覆盖复制和淘汰成本 |
| 推测动作余量 | `speculative_copy_may_evict` | 默认 `false`，预取/跨 GPU 副本不能为了自己驱逐已有本地缓存 |

这些门槛的目标是让 AURA 少做无效后台迁移，减少“本地命中率提高但总耗时更差”的情况。

为了让结果更直观，论文实验还输出：

```text
normalized_to_lru = LRU-Local 综合代价 / 当前策略综合代价
```

这个值可以粗略理解成“在同一组 trace 和同一套代价模型下，相对 LRU 的等效服务能力”。例如 `AURA-Joint = 3.178x` 表示它的综合代价约为 LRU 的 `1 / 3.178`。

## 6. 真实 NVMe-oF baseline

当前真实单客户端结果摘要：

| 用例 | 操作 | 带宽 | IOPS | P99 |
|---|---|---:|---:|---:|
| 本机 NVMe 顺序读 | read | 2856.99 MiB/s | 2856.99 | 6.586 ms |
| 本机 NVMe 4K 随机读 | read | 959.91 MiB/s | 245737.55 | 0.224 ms |
| 远端 NVMe-oF 顺序读 | read | 112.21 MiB/s | 112.21 | 141.558 ms |
| 远端 NVMe-oF 顺序写 | write | 112.16 MiB/s | 112.16 | 166.724 ms |
| 远端 NVMe-oF 4K 随机读 | read | 110.16 MiB/s | 28201.84 | 1.188 ms |

这组数据说明远端访问代价真实存在，支撑“本地 SSD 作为热点缓存层”的动机。但它还不能证明真实多 GPU 亲和放置效果，因为当前真实环境只有一台已接入的内网客户端。

## 7. 动态监控

运行：

```bash
python3 scripts/aura_kv_monitor.py run \
  --workload hotspot-migration \
  --policy AURA-Joint \
  --dashboard
```

输出：

```text
reports/latest/aura-kv-live/<run-id>/
├── events.jsonl
├── metrics.jsonl
├── layout_snapshots.jsonl
├── results.csv
├── results.json
└── state.json
```

Dashboard 用于观察：

- 前台请求命中本地、Peer 还是远端。
- 控制器生成了哪些候选动作。
- 后台任务队列如何执行。
- Node x Cache 副本矩阵如何变化。

## 8. 论文边界

可以写：

- 已实现 FUSE 分层缓存文件系统原型。
- 已跑通双 VM 和实验室单客户端 NVMe/TCP baseline。
- 已实现价值感知本地缓存管理和共享副本放置模型。
- 已通过 13 个 trace 场景和多个 baseline 完成消融。

暂时不要写：

- 已在真实 GPU 集群中降低 TTFT。
- 已完成生产级分布式文件系统。
- 已验证多客户端共享远端 Target 的并发极限。
