# 真实 NVMe-oF 多轮速度实验汇总

实验规模：32MiB shards, 160MiB local quota, 3 repeated runs, verified NVMe-oF。

本报告把同一套真实 TokenFS workload 在 NVMe-oF 挂载目录上重复运行多次，并汇总均值、标准差和最小/最大范围。它用于回答 AURA-Joint 的速度收益是否稳定，而不是只依赖一次运行结果。

所有策略使用同一访问形状：远端 canonical KV Cache、本地冷缓存占满、容量压力、热点复用、连续 shard 访问和跨 GPU 共享读取。与单轮验证相比，本实验只放大 shard 规模并重复采样，不额外构造只适合 AURA 的极端 trace。

实验默认控制 Linux page cache：清缓存动作记录为证据，但不计入策略读写耗时。这样可以避免 RemoteOnly 的重复读取被内存缓存伪装成本地速度。

## 均值结果

| 策略 | 轮数 | 总数据 MiB | 总耗时均值 s | 耗时范围 s | 总吞吐均值 MiB/s | 加速比均值 | 读吞吐均值 MiB/s | 本地读命中率均值 | 远端打开读取均值 | 后台动作均值 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `RemoteOnly` | 3 | 8456 | 9.21 | 8.98-9.65 | 919.43 | 1x | 1261.89 | 0% | 260 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| `LocalFirst` | 3 | 8456 | 8.52 | 8.21-9.05 | 994.03 | 1.081x | 1269.05 | 0.38% | 259 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| `LRU-Local` | 3 | 8456 | 8.78 | 7.86-9.70 | 969.70 | 1.053x | 1244.10 | 0.38% | 259 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| `LFU-Local` | 3 | 8456 | 8.54 | 8.24-8.78 | 990.57 | 1.078x | 1248.69 | 0.38% | 259 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| `AURA-Joint` | 3 | 8456 | 9.12 | 8.88-9.33 | 927.98 | 1.010x | 1187.30 | 96.15% | 10 | promote=1, prefetch=1, evict=1, xgpu_hit=62 |

## 图表

![多轮总耗时](figures/repeat_wall_time_mean.svg)

![多轮总吞吐](figures/repeat_effective_throughput_mean.svg)

![多轮加速比](figures/repeat_speedup_mean.svg)

## 结论提示

- AURA-Joint 平均端到端加速比为 `1.010x`，范围 `0.962x-1.056x`。
- AURA-Joint 平均远端打开读取为 `10` 次，RemoteOnly 为 `260` 次，说明本地副本和后台动作确实减少了远端访问。
- 当前环境中平均总耗时最低的是 `LocalFirst`，不是 AURA-Joint；这说明当前双 VM NVMe-oF 环境更适合证明机制和远端访问减少，暂时不能直接声称 AURA 端到端速度显著领先所有 baseline。
- 如果均值提升但波动较大，论文中应同时报告标准差或 min-max，而不是只放最好的一轮。
- 如果未来换成真实物理 GPU 服务器，只需要保持同一脚本和同一策略参数重新运行，即可得到可横向比较的数据。
