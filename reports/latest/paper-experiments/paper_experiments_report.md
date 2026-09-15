# AURA-KV 论文实验汇总

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

单轮速度实验用于快速检查各策略在真实 FUSE + NVMe-oF 路径下是否能跑通。

数据文件：

```text
09_real_cn14_nvmeof/02_single_run_speed/real_speed_summary.csv
09_real_cn14_nvmeof/02_single_run_speed/real_speed_report.md
09_real_cn14_nvmeof/02_single_run_speed/figures/
```

当前关键结果：

| 策略 | 总数据 MiB | 总耗时 s | 有效吞吐 MiB/s | 相对 RemoteOnly | 本地读命中率 | 远端打开读取 | 后台动作 |
|---|---:|---:|---:|---:|---:|---:|---|
| `RemoteOnly` | 16904 | 65.556 | 257.86 | 1.000x | 0.00% | 260 | promote=0, prefetch=0, xgpu=0 |
| `LocalFirst` | 16904 | 60.668 | 278.63 | 1.081x | 0.38% | 259 | promote=0, prefetch=0, xgpu=0 |
| `LRU-Local` | 16904 | 63.532 | 266.07 | 1.032x | 0.38% | 259 | promote=0, prefetch=0, xgpu=0 |
| `LFU-Local` | 16904 | 62.341 | 271.15 | 1.052x | 0.38% | 259 | promote=0, prefetch=0, xgpu=0 |
| `AURA-Joint` | 16904 | 66.688 | 253.48 | 0.983x | 95.38% | 12 | promote=1, prefetch=1, xgpu_hit=62 |

结论：AURA 机制已经明显生效，本地读命中率达到 95.38%，远端打开读取从 260 次降到 12 次；但单轮总耗时没有超过传统策略，说明当前实现开销仍需优化。

## 5. 真实 TokenFS 三轮重复速度

三轮重复实验是当前真实速度结果中最适合论文引用的表，因为它包含均值和波动范围。

数据文件：

```text
09_real_cn14_nvmeof/03_repeat_speed/repeat_summary.csv
09_real_cn14_nvmeof/03_repeat_speed/repeat_runs.csv
09_real_cn14_nvmeof/03_repeat_speed/repeat_report.md
09_real_cn14_nvmeof/03_repeat_speed/figures/
```

当前汇总：

| 策略 | 轮数 | 每轮数据 MiB | 平均总耗时 s | 耗时范围 s | 平均有效吞吐 MiB/s | 相对 RemoteOnly | 本地读命中率 | 远端打开读取 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `RemoteOnly` | 3 | 16904 | 64.818 | 63.900-66.299 | 260.89 | 1.000x | 0.00% | 260 |
| `LocalFirst` | 3 | 16904 | 63.162 | 60.668-64.629 | 267.63 | 1.026x | 0.38% | 259 |
| `LRU-Local` | 3 | 16904 | 61.487 | 59.766-63.532 | 274.94 | 1.054x | 0.38% | 259 |
| `LFU-Local` | 3 | 16904 | 61.844 | 60.055-63.136 | 273.38 | 1.049x | 0.38% | 259 |
| `AURA-Joint` | 3 | 16904 | 65.017 | 63.296-66.688 | 260.02 | 0.997x | 95.38% | 12 |

结论必须诚实写：在当前真实环境中，AURA-Joint 显著减少远端访问，但平均端到端速度尚未超过 LRU/LFU/LocalFirst。这个结果不是失败，而是指出论文后续优化重点应放在降低后台复制、指标写入和 FUSE 元数据路径的实现开销上。

## 6. 图表

Trace 模型图：

```text
figures/effective_performance_index.svg
figures/aura_improvement_vs_baselines.svg
```

真实速度图：

```text
09_real_cn14_nvmeof/02_single_run_speed/figures/
09_real_cn14_nvmeof/03_repeat_speed/figures/
```

## 7. 当前可写入论文的结论

- AURA-KV 已经形成完整原型：FUSE 统一命名空间、本地缓存目录、远端 NVMe-oF canonical 层、元数据表、策略控制器、后台任务和监控指标。
- Trace 回放中，AURA-Joint 能够在多场景下把综合服务代价降到最低，说明价值感知和 GPU 亲和联合决策是有效的。
- 真实 cn14 到 cn13 NVMe-oF 环境中，AURA 能将远端读取次数从 260 次降到 12 次，说明策略动作确实进入了真实系统路径。
- 当前真实速度尚未领先传统 LRU/LFU，说明系统实现仍有可优化空间。论文中应把这组结果作为“机制验证 + 性能边界分析”，不要写成已经在端到端速度上全面领先。

## 8. 后续优化方向

1. 前台路径降开销：减少每次读写中的 SQLite 同步写入，把细粒度指标改为批量异步落盘。
2. 后台复制降干扰：对 promote/prefetch/cross-GPU replica 使用更严格的收益门槛和限速。
3. 数据路径优化：减少 FUSE 用户态拷贝和小粒度 open/close，增加文件句柄缓存和批量读。
4. 实验环境增强：在多台真实 GPU 客户端上复测，观察跨节点亲和副本是否能带来更明显收益。
