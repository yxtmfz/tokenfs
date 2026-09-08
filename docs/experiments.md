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

输出：

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
./scripts/real_speed_benchmark.sh
```

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
| `speedup_vs_baseline` | 相对 baseline 的实际加速比，大于 1 表示真的更快 |
| `avg_read_us` / `avg_write_us` | TokenFS 记录的平均读写耗时 |
| `remote_read_open` | 读取时打开远端文件的次数，越少通常越好 |

如果远端目录已经配置为 NVMe-oF 挂载点，例如 `/srv/tokenfs/remote0`，该实验就是真实 TokenFS + NVMe-oF 端到端速度测试；如果仍然使用 `/var/lib/tokenfs/remote-sim`，它只能衡量软件层策略开销。

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
| speedup_vs_baseline | 真实 workload 相对 baseline 加速比，越高越好 |
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

如果两者结论不一致，应优先相信真实速度实验，再调整 workload、阈值或成本权重。

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
