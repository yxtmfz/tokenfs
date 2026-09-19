> **历史报告，不能作为当前论文性能证据。** 下文保留旧批次及当时叙述。当前结果请读 [第二轮 756 次实测与消融报告](11_measured_admission/README.md)；第一轮 400 次结果仍单独保留。

# AURA-KV 历史论文实验汇总

本文是当前仓库的论文实验结果入口。完整叙述版请看：

```text
reports/latest/final-report.md
```

当前最重要的真实系统结果位于：

```text
reports/latest/paper-experiments/09_real_cn14_nvmeof/
```

## 1. 当前真实实验环境

最新实验已经从本地双 VM Target 切换到老师提供的真实存储网络环境：

```text
cn14 单客户端
  ├── TokenFS / AURA Controller
  ├── gpu0/gpu1/gpu2 逻辑本地缓存目录
  └── /srv/tokenfs/remote0
          ↑
          └── /dev/nvme3n1，来自 cn13:4420 Linux NVMe/TCP Target
```

这组结果可以证明真实 NVMe-oF 远端层已经参与 TokenFS 端到端路径。需要注意：`gpu0/gpu1/gpu2` 仍是单客户端上的逻辑 GPU，用来验证多 GPU 缓存策略；它还不是多台真实 GPU 物理服务器并发实验。

环境证据文件：

```text
09_real_cn14_nvmeof/environment_evidence.txt
09_real_cn14_nvmeof/02_single_run_speed/nvmeof_mount_evidence.txt
```

## 2. Trace 回放消融实验

Trace 回放用于验证策略模型本身是否有效，不直接等同于真实速度。它比较 AURA-Joint 与 RemoteOnly、LocalFirst、LRU/LFU 等策略在同一批 KV Cache 访问场景下的命中率、远端读取、迁移量和综合服务代价。

数据文件：

```text
01_trace_replay/trace_summary.csv
01_trace_replay/trace_detail.csv
01_trace_replay/trace_results.json
```

当前汇总：

| 策略 | 本地命中率 | 远端读取 MiB | 迁移 MiB | Churn | P99 ms | 综合代价/请求 |
|---|---:|---:|---:|---:|---:|---:|
| `RemoteOnly` | 0.0000 | 2244.77 | 0.00 | 0.00 | 9.0188 | 3.1889 |
| `LocalFirst` | 0.7290 | 949.23 | 231.85 | 28.69 | 5.5199 | 1.8880 |
| `LRU-Local` | 0.7362 | 400.62 | 400.62 | 38.69 | 3.0247 | 1.7085 |
| `LFU-Local` | 0.7586 | 380.31 | 380.31 | 35.62 | 3.0594 | 1.5691 |
| `DualWindowReplacement` | 0.8907 | 146.15 | 268.31 | 19.69 | 1.4685 | 0.7717 |
| `SourceAwareReplacement` | 0.9423 | 0.00 | 185.85 | 23.62 | 0.4228 | 0.9318 |
| `AffinityOnly` | 0.5900 | 1182.31 | 68.00 | 7.85 | 5.5917 | 1.6883 |
| `WA-Affinity-Independent` | 0.7864 | 368.92 | 184.92 | 14.00 | 2.8872 | 0.9922 |
| `AURA-Joint` | 0.8822 | 228.31 | 64.00 | 3.62 | 1.4749 | 0.5376 |
| `OracleDemand` | 1.0000 | 0.00 | 380.31 | 35.62 | 0.1291 | 0.8994 |

结论：AURA-Joint 的优势不是单纯让命中率最高，而是在命中收益、远端代价、迁移代价和副本抖动之间做联合权衡，使综合代价最低。

## 3. 真实 NVMe-oF 环境差距

环境差距诊断直接测试 cn14 本地目录和 `/srv/tokenfs/remote0` 远端 NVMe-oF 挂载目录的读写速度。

数据文件：

```text
09_real_cn14_nvmeof/01_environment_gap/storage_gap_summary.csv
09_real_cn14_nvmeof/01_environment_gap/storage_gap_report.md
```

当前结果：

| 层级 | 数据量 | 写入耗时 | 写入吞吐 | 读取耗时 | 读取吞吐 |
|---|---:|---:|---:|---:|---:|
| local | 1024 MiB | 6.855 s | 149.37 MiB/s | 6.234 s | 164.27 MiB/s |
| remote NVMe-oF | 1024 MiB | 13.019 s | 78.65 MiB/s | 9.272 s | 110.45 MiB/s |

结论：当前真实环境中，本地读确实快于远端 NVMe-oF 读，但差距属于中等，不是特别悬殊。因此策略减少远端读取后，仍可能被 FUSE、SQLite 指标记录、后台复制和迁移调度开销抵消。

## 4. 真实 TokenFS 单轮速度

单轮速度实验用于快速检查各策略在真实 FUSE + NVMe-oF 路径下是否能跑通。早期单轮结果发现：AURA 已经显著减少远端访问，但如果把本地缓存创建当作强持久化事务，并且每次本地命中都同步更新控制面，wall-clock 总耗时会被实现开销抵消。因此后续加入了“远端权威、本地可重建缓存语义”和“本地命中快路径”。

数据文件：

```text
09_real_cn14_nvmeof/02_single_run_speed/real_speed_summary.csv
09_real_cn14_nvmeof/02_single_run_speed/real_speed_report.md
09_real_cn14_nvmeof/02_single_run_speed/figures/
```

优化前单轮关键结果：

| 策略 | 总数据 MiB | 总耗时 s | 有效吞吐 MiB/s | 相对 RemoteOnly | 本地读命中率 | 远端打开读取 | 后台动作 |
|---|---:|---:|---:|---:|---:|---:|---|
| `RemoteOnly` | 16904 | 65.556 | 257.86 | 1.000x | 0.00% | 260 | promote=0, prefetch=0, xgpu=0 |
| `LocalFirst` | 16904 | 60.668 | 278.63 | 1.081x | 0.38% | 259 | promote=0, prefetch=0, xgpu=0 |
| `LRU-Local` | 16904 | 63.532 | 266.07 | 1.032x | 0.38% | 259 | promote=0, prefetch=0, xgpu=0 |
| `LFU-Local` | 16904 | 62.341 | 271.15 | 1.052x | 0.38% | 259 | promote=0, prefetch=0, xgpu=0 |
| `AURA-Joint` | 16904 | 66.688 | 253.48 | 0.983x | 95.38% | 12 | promote=1, prefetch=1, xgpu_hit=62 |

结论：AURA 机制已经明显生效，本地读命中率达到 95.38%，远端打开读取从 260 次降到 12 次；但优化前单轮总耗时没有超过传统策略，说明实现开销需要进入论文分析，而不能只汇报命中率。

## 5. 真实 TokenFS 三轮重复速度

三轮重复实验是当前真实速度结果中最适合论文引用的表，因为它包含均值和波动范围。

当前主引用数据文件：

```text
09_real_cn14_nvmeof/07_fair_readthrough_repeat/repeat_summary.csv
09_real_cn14_nvmeof/07_fair_readthrough_repeat/repeat_runs.csv
09_real_cn14_nvmeof/07_fair_readthrough_repeat/repeat_report.md
09_real_cn14_nvmeof/07_fair_readthrough_repeat/figures/
```

当前汇总：

| 策略 | 轮数 | 每轮数据 MiB | 平均总耗时 s | 耗时范围 s | 平均有效吞吐 MiB/s | 相对 RemoteOnly | 本地读命中率 | 远端打开读取 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `RemoteOnly` | 3 | 16904 | 63.896 | 62.476-65.310 | 264.64 | 1.000x | 0.00% | 260 |
| `LocalFirst` | 3 | 16904 | 61.293 | 59.474-62.481 | 275.92 | 1.043x | 0.38% | 259 |
| `LRU-Local` | 3 | 16904 | 61.229 | 60.039-62.136 | 276.14 | 1.044x | 0.38% | 259 |
| `LFU-Local` | 3 | 16904 | 62.038 | 60.357-63.736 | 272.61 | 1.030x | 0.38% | 259 |
| `LRU-ReadThrough` | 3 | 16904 | 59.278 | 58.127-60.604 | 285.25 | 1.098x | 73.85% | 68 |
| `LFU-ReadThrough` | 3 | 16904 | 59.409 | 58.361-61.032 | 284.64 | 1.095x | 73.85% | 68 |
| `AURA-no-prefetch` | 3 | 16904 | 58.674 | 58.512-58.829 | 288.10 | 1.109x | 91.15% | 23 |
| `AURA-no-xgpu` | 3 | 16904 | 60.035 | 59.462-60.509 | 281.58 | 1.083x | 71.54% | 74 |
| `AURA-Joint` | 3 | 16904 | **57.977** | **57.429-58.973** | **291.61** | **1.122x** | **95.25%** | **12.3** |

结论：优化后的 AURA-Joint 在同一真实 NVMe-oF workload 上平均总耗时最低。相比 RemoteOnly 快约 `10.87%`，相比更强的 LRU-ReadThrough 快约 `2.20%`，相比 LFU-ReadThrough 快约 `2.41%`。同时，远端打开读取从 `260` 次降到约 `12.3` 次。强 LRU/LFU baseline 已经通过读后回填把本地读命中率提高到 `73.85%`，因此该结果比旧 5 策略结果更适合作为论文主表。

## 6. 图表

Trace 模型图：

```text
figures/effective_performance_index.svg
figures/aura_improvement_vs_baselines.svg
```

真实速度图：

```text
09_real_cn14_nvmeof/02_single_run_speed/figures/
09_real_cn14_nvmeof/07_fair_readthrough_repeat/figures/
```

## 7. 当前可写入论文的结论

- AURA-KV 已经形成完整原型：FUSE 统一命名空间、本地缓存目录、远端 NVMe-oF canonical 层、元数据表、策略控制器、后台任务和监控指标。
- Trace 回放中，AURA-Joint 能够在多场景下把综合服务代价降到最低，说明价值感知和 GPU 亲和联合决策是有效的。
- 真实 cn14 到 cn13 NVMe-oF 环境中，AURA 能将远端打开读取从 260 次降到约 12.3 次，说明策略动作确实进入了真实系统路径。
- 最新真实三轮重复实验中，AURA-Joint 的平均总耗时低于 RemoteOnly、LocalFirst、LRU-Local、LFU-Local、LRU-ReadThrough 和 LFU-ReadThrough，说明当前实现已经能在更公平的强 baseline 下把模型收益转化为端到端速度提升。

## 8. 后续优化方向

1. 接入真实 KV Cache trace：让访问序列更接近 vLLM/SGLang。
2. 多物理客户端实验：验证真正跨 GPU 服务器的亲和副本收益。
3. 前台路径进一步降开销：把更多指标更新改为采样或异步批量落盘。
4. 后台复制限速与批量化：避免大规模 promote/prefetch 抢占前台 I/O。
