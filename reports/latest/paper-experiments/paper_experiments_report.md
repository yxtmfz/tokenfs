# AURA-KV 论文实验汇总

本报告汇总当前仓库在无完整真实 GPU 集群条件下已经完成的前四项实验。策略实验是 trace-driven simulator 结果；NVMe-oF baseline 来自已采集的真实协议链路摘要。二者用途不同，论文中需要分别标注。

## 0. 实验配置

- 逻辑节点数：4
- 每节点 GPU 数：1
- 每节点本地缓存容量：64 MiB
- 远端 P99 代理代价：8.0 ms
- 全局重复副本预算：128 MiB
- 单节点重复副本预算：48 MiB

## 1. Trace 回放实验

当前使用 13 个 KV Cache 访问场景作为可复现 trace。真实 vLLM/SGLang trace 到位后，可以保留相同统计口径替换输入 trace。

| 场景 | 含义 |
|---|---|
| `private` | 每个逻辑 GPU 访问自己的私有缓存。 |
| `node_shared` | 同节点共享缓存。 |
| `cluster_shared` | 跨节点共享缓存。 |
| `hotspot_shift` | 热点从一个节点迁移到另一个节点。 |
| `high_recompute` | 高重算代价 KV 与普通 KV 混合。 |
| `remote_congestion` | 远端访问代价升高。 |
| `demand_estimation_error` | 访问突发且带预测误差。 |
| `tenant_isolation` | 多个租户交替访问。 |
| `scan_pollution` | 稳定热点后插入大量一次性扫描数据。 |
| `large_object_pollution` | 少量大对象挤占小热点缓存。 |
| `multi_gpu_shared_burst` | 共享 KV 在多个逻辑 GPU 间突发复用。 |
| `tight_capacity_thrash` | 本地容量紧张导致反复替换。 |
| `expensive_vs_cheap_mix` | 高重算与低重算缓存混合。 |

| 策略 | 本地命中率 | 远端读取 MiB | 迁移 MiB | Churn | P99 ms | 综合代价/请求 |
|---|---:|---:|---:|---:|---:|---:|
| `RemoteOnly` | 0.0 | 2244.77 | 0.0 | 0.0 | 9.0188 | 3.1889 |
| `LocalFirst` | 0.729 | 949.23 | 231.85 | 28.69 | 5.5199 | 1.888 |
| `LRU-Local` | 0.7362 | 400.62 | 400.62 | 38.69 | 3.0247 | 1.7085 |
| `LFU-Local` | 0.7586 | 380.31 | 380.31 | 35.62 | 3.0594 | 1.5691 |
| `DualWindowReplacement` | 0.8907 | 146.15 | 268.31 | 19.69 | 1.4685 | 0.7717 |
| `SourceAwareReplacement` | 0.9423 | 0.0 | 185.85 | 23.62 | 0.4228 | 0.9318 |
| `AffinityOnly` | 0.59 | 1182.31 | 68.0 | 7.85 | 5.5917 | 1.6883 |
| `WA-Affinity-Independent` | 0.7864 | 368.92 | 184.92 | 14.0 | 2.8872 | 0.9922 |
| `AURA-Joint` | 0.8822 | 228.31 | 64.0 | 3.62 | 1.4749 | 0.5376 |
| `OracleDemand` | 1.0 | 0.0 | 380.31 | 35.62 | 0.1291 | 0.8994 |

观察：

- `AURA-Joint` 平均综合代价为 `0.5376/request`。
- 相比 `LRU-Local` 降低 `68.5%`，相比 `LFU-Local` 降低 `65.7%`。
- AURA 的优势不只是命中率，而是同时控制远端读取、迁移量和副本抖动。

## 1.1 总性能指标

`综合代价/请求` 是越低越好的主指标。为了更直观展示“快了多少”，本报告进一步定义：

```text
等效性能指数 = LRU-Local 综合代价 / 当前策略综合代价
```

因此 `LRU-Local = 1.00x`，数值越大，表示在同一组 trace 下单位综合代价能服务更多请求。

![等效性能提升柱状图](figures/effective_performance_index.svg)

| 策略 | 综合代价/请求 | 等效性能指数 | 相对 RemoteOnly | AURA 相比该策略降低代价 |
|---|---:|---:|---:|---:|
| `RemoteOnly` | 3.1889 | 0.5358x | 1.0x | 83.14% |
| `LocalFirst` | 1.888 | 0.9049x | 1.689x | 71.53% |
| `LRU-Local` | 1.7085 | 1.0x | 1.8665x | 68.53% |
| `LFU-Local` | 1.5691 | 1.0888x | 2.0323x | 65.74% |
| `DualWindowReplacement` | 0.7717 | 2.2139x | 4.1323x | 30.34% |
| `SourceAwareReplacement` | 0.9318 | 1.8335x | 3.4223x | 42.31% |
| `AffinityOnly` | 1.6883 | 1.012x | 1.8888x | 68.16% |
| `WA-Affinity-Independent` | 0.9922 | 1.7219x | 3.214x | 45.82% |
| `AURA-Joint` | 0.5376 | 3.178x | 5.9317x | 0.00% |
| `OracleDemand` | 0.8994 | 1.8996x | 3.5456x | 40.23% |

![AURA 相对基线的综合代价降低](figures/aura_improvement_vs_baselines.svg)

## 1.2 真实 TokenFS Workload 速度实验

成本模型解释控制器为什么做某个选择，但不能单独证明系统真的更快。因此仓库额外提供真实 TokenFS workload 测速入口：

```bash
TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/real_speed_benchmark.sh
```

该实验读取 FUSE/TokenFS 实际运行产生的 wall-clock 时间、有效吞吐和平均读写延迟，不使用成本模型权重。脚本默认强制检查远端后端已经通过 NVMe-oF 直连挂载，避免把 `remote-sim` 开发目录或 SSH tunnel 数据路径误写成直连网络 SSD 结果。workload 会使用独立实验命名空间，构造远端 canonical KV、本地冷缓存、容量压力、热点复用、顺序预取和跨 GPU 共享访问；因此可以同时观察总耗时和策略生效后的复用阶段收益。

| 策略 | 总数据 MiB | 总耗时 s | 有效吞吐 MiB/s | 相对 RemoteOnly 加速 | 复用阶段吞吐 MiB/s | 复用阶段相对吞吐 | 平均读 us | 本地读命中率 | 远端打开读取 | 后台动作 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `RemoteOnly` | 552.0 | 9.6369 | 57.28 | 1.0x | 59.92 | 1.0x | 2718.29 | 0.0% | 64 | promote=0, prefetch=0/0, evict=0, xgpu=0/0 |
| `LocalFirst` | 552.0 | 9.062 | 60.91 | 1.0634x | 63.69 | 1.063x | 2576.61 | 1.56% | 63 | promote=0, prefetch=0/0, evict=0, xgpu=0/0 |
| `LRU-Local` | 552.0 | 9.3226 | 59.21 | 1.0337x | 63.03 | 1.0519x | 2607.8 | 1.56% | 63 | promote=0, prefetch=0/0, evict=1, xgpu=0/0 |
| `LFU-Local` | 552.0 | 9.655 | 57.17 | 0.9981x | 58.48 | 0.976x | 2763.16 | 1.56% | 63 | promote=0, prefetch=0/0, evict=1, xgpu=0/0 |
| `AURA-Joint` | 552.0 | 9.7904 | 56.38 | 0.9843x | 61.63 | 1.0285x | 2714.6 | 96.88% | 3 | promote=1, prefetch=1/1, evict=3, xgpu=1/15 |

## 2. 端到端延迟代理实验

这里的端到端延迟是 simulator 中一次 KV 获取的代理延迟，不等同于真实 TTFT。它用于比较策略是否减少远端访问和高尾延迟路径。

| 策略 | P50 ms | P95 ms | P99 ms | SLO 违约率 | 远端读取 MiB | 综合代价/请求 |
|---|---:|---:|---:|---:|---:|---:|
| `RemoteOnly` | 1.2318 | 5.9711 | 9.0188 | 0.0051 | 2244.77 | 3.1889 |
| `LocalFirst` | 0.3933 | 3.2595 | 5.5199 | 0.0079 | 949.23 | 1.888 |
| `LRU-Local` | 0.3328 | 0.9761 | 3.0247 | 0.0 | 400.62 | 1.7085 |
| `LFU-Local` | 0.3167 | 0.9722 | 3.0594 | 0.0 | 380.31 | 1.5691 |
| `AURA-Joint` | 0.1579 | 0.6285 | 1.4749 | 0.0 | 228.31 | 0.5376 |

## 3. 参数敏感性实验

本实验分别改变本地容量、远端 P99 代价和副本预算，观察 AURA 是否只在某个特殊参数下有效。

| 扫描参数 | 取值 | AURA 综合代价/请求 | LRU 综合代价/请求 | LFU 综合代价/请求 |
|---|---:|---:|---:|---:|
| `local_capacity_mib` | 32 | 1.3884 | 4.3667 | 4.1692 |
| `local_capacity_mib` | 48 | 1.1370 | 4.0774 | 3.7149 |
| `local_capacity_mib` | 64 | 1.1370 | 4.0774 | 3.7149 |
| `local_capacity_mib` | 96 | 1.1370 | 4.0774 | 3.7149 |
| `local_capacity_mib` | 128 | 1.1370 | 4.0774 | 3.7149 |
| `remote_p99_ms` | 2.0 | 1.0772 | 3.8518 | 3.5231 |
| `remote_p99_ms` | 4.0 | 1.0971 | 3.9270 | 3.5870 |
| `remote_p99_ms` | 8.0 | 1.1370 | 4.0774 | 3.7149 |
| `remote_p99_ms` | 16.0 | 1.2169 | 4.3784 | 3.9706 |
| `duplicate_budget_mib` | 64 | 1.3379 | 4.6049 | 4.1124 |
| `duplicate_budget_mib` | 96 | 1.2146 | 4.6030 | 3.9688 |
| `duplicate_budget_mib` | 128 | 1.1370 | 4.0774 | 3.7149 |
| `duplicate_budget_mib` | 192 | 1.1370 | 4.0774 | 3.7149 |

## 4. NVMe-oF Baseline

该部分读取仓库中已有真实 NVMe/TCP 链路摘要。如果换到新的实验室节点，应重新运行 Linux 端 baseline 脚本生成同格式 CSV。

| 用例 | 操作 | 带宽 MiB/s | IOPS | P50 ms | P95 ms | P99 ms | 备注 |
|---|---|---:|---:|---:|---:|---:|---|
| `local_nvme_randread_4k` | read | 959.91 | 245737.55 | 0.102 | 0.196 | 0.224 | lab compute local NVMe read-only baseline |
| `local_nvme_seq_read` | read | 2856.99 | 2856.99 | 5.276 | 6.390 | 6.586 | lab compute local NVMe read-only baseline |
| `local_home_randread_4k` | read | 3.02 | 772.24 | 21.889 | 145.752 | 270.533 | lab compute home file baseline; not local NVMe cache |
| `local_home_seq_read` | read | 167.48 | 167.48 | 91.750 | 96.993 | 200.278 | lab compute home file baseline; not local NVMe cache |
| `local_home_seq_write` | write | 166.47 | 166.47 | 91.750 | 108.528 | 212.861 | lab compute home file baseline; not local NVMe cache |
| `remote_nvmeof_randread_4k` | read | 110.16 | 28201.84 | 1.122 | 1.171 | 1.188 | lab compute to lab storage Linux NVMe/TCP target |
| `remote_nvmeof_seq_read` | read | 112.21 | 112.21 | 141.558 | 141.558 | 141.558 | lab compute to lab storage Linux NVMe/TCP target |
| `remote_nvmeof_seq_write` | write | 112.16 | 112.16 | 141.558 | 143.655 | 166.724 | lab compute to lab storage Linux NVMe/TCP target; writes only to test backing file |

## 5. 论文写作可用结论

- 策略层：AURA-Joint 在 13 个 trace 场景中降低综合服务代价，尤其适合扫描污染、大对象污染、容量紧张和重算代价差异明显的 KV Cache 场景。
- 系统层：TokenFS/AURA-KV 已具备本地缓存、远端权威层、策略控制器、后台任务、指标输出和 Dashboard 的原型能力。
- NVMe-oF 层：已有真实 NVMe/TCP baseline 摘要，能说明远端路径存在额外延迟和带宽上限；完整 GPU 端到端收益仍需要在真实推理 workload 上复测。

## 6. 输出文件

```text
01_trace_replay/trace_summary.csv
01_trace_replay/trace_detail.csv
02_e2e_latency/latency_summary.csv
02_e2e_latency/latency_detail.csv
03_sensitivity/sensitivity_summary.csv
04_nvmeof_baseline/real_nvmeof_summary.csv
05_performance_summary/performance_summary.csv
06_real_speed_benchmark/real_speed_summary.csv
06_real_speed_benchmark/real_speed_report.md
06_real_speed_benchmark/figures/
figures/effective_performance_index.svg
figures/aura_improvement_vs_baselines.svg
paper_experiments_report.md
```
