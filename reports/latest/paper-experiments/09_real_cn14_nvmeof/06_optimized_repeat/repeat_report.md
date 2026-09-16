# 真实 NVMe-oF 多轮速度实验汇总

实验规模：cn14->cn13 real NVMe-oF, optimized local-cache semantics, fast local-hit path, 64MiB shards, 512MiB local quota, 3 runs。

本报告把同一套真实 TokenFS workload 在 NVMe-oF 挂载目录上重复运行多次，并汇总均值、标准差和最小/最大范围。它用于回答 AURA-Joint 的速度收益是否稳定，而不是只依赖一次运行结果。

所有策略使用同一访问形状：远端 canonical KV Cache、本地冷缓存占满、容量压力、热点复用、连续 shard 访问和跨 GPU 共享读取。与单轮验证相比，本实验只放大 shard 规模并重复采样，不额外构造只适合 AURA 的极端 trace。

实验默认控制 Linux page cache：清缓存动作记录为证据，但不计入策略读写耗时。这样可以避免 RemoteOnly 的重复读取被内存缓存伪装成本地速度。

## 均值结果

| 策略 | 轮数 | 总数据 MiB | 总耗时均值 s | 耗时范围 s | 总吞吐均值 MiB/s | 加速比均值 | 读吞吐均值 MiB/s | 本地读命中率均值 | 远端打开读取均值 | 后台动作均值 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `RemoteOnly` | 3 | 16904 | 63.90 | 62.48-65.31 | 264.64 | 1x | 306.71 | 0% | 260 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| `LocalFirst` | 3 | 16904 | 61.29 | 59.47-62.48 | 275.92 | 1.043x | 306.95 | 0.38% | 259 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| `LRU-Local` | 3 | 16904 | 61.23 | 60.04-62.14 | 276.14 | 1.044x | 307.52 | 0.38% | 259 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| `LFU-Local` | 3 | 16904 | 62.04 | 60.36-63.74 | 272.61 | 1.030x | 303.02 | 0.38% | 259 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| `AURA-Joint` | 3 | 16904 | 58.37 | 57.27-59.25 | 289.65 | 1.095x | 324.89 | 95.38% | 12 | promote=1, prefetch=1, evict=0, xgpu_hit=62 |

## 图表

![多轮总耗时](figures/repeat_wall_time_mean.svg)

![多轮总吞吐](figures/repeat_effective_throughput_mean.svg)

![多轮加速比](figures/repeat_speedup_mean.svg)

## 结论提示

- AURA-Joint 平均端到端加速比为 `1.095x`，范围 `1.066x-1.140x`。
- AURA-Joint 平均远端打开读取为 `12` 次，RemoteOnly 为 `260` 次，说明本地副本和后台动作确实减少了远端访问。
- AURA-Joint 是本轮多次重复实验中平均总耗时最低的策略。
- 如果均值提升但波动较大，论文中应同时报告标准差或 min-max，而不是只放最好的一轮。
- 如果未来换成真实物理 GPU 服务器，只需要保持同一脚本和同一策略参数重新运行，即可得到可横向比较的数据。
