# TokenFS 真实速度实验

实验环境：已有 TokenFS workload 样例结果（当前仓库保存的开发环境数据）

本报告只使用真实程序运行产生的 wall-clock 时间、读写吞吐和 TokenFS 指标，不使用成本模型权重。它回答的是：在同一组 token shard workload 下，开启热点提升、顺序预取和联合策略后，系统端到端是否真的更快。

注意：如果远端后端配置为 `/srv/tokenfs/remote0` 且该目录来自 NVMe-oF 挂载，本报告就是 TokenFS + 真实 NVMe-oF 路径的结果；如果远端后端仍是 `remote-sim` 目录，它只能说明软件策略开销，不能代表真实网络 SSD 性能。

## 结果表

| 策略 | 总数据 MiB | 总耗时 s | 有效吞吐 MiB/s | 相对 baseline 加速 | 平均读 us | 读延迟变化 | 本地读命中率 | 远端打开读取 | 远端打开减少 | 后台动作 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `baseline` | 176.0 | 2.9234 | 60.2 | 1.0x | 2728.33 | 0.0% | 20.0% | 4 | 0.0% | promote=0, prefetch=0, evict=0, spill=0 |
| `promote` | 176.0 | 2.7416 | 64.2 | 1.0663x | 2499.12 | 8.4% | 20.0% | 4 | 0.0% | promote=0, prefetch=0, evict=0, spill=0 |
| `prefetch` | 176.0 | 2.8129 | 62.57 | 1.0393x | 2568.05 | 5.87% | 20.0% | 4 | 0.0% | promote=0, prefetch=0, evict=0, spill=0 |
| `full` | 176.0 | 3.0414 | 57.87 | 0.9612x | 2506.28 | 8.14% | 20.0% | 4 | 0.0% | promote=0, prefetch=0, evict=0, spill=0 |

## 可视化

![真实总耗时](figures/real_wall_time.svg)

![真实相对加速比](figures/real_speedup_vs_baseline.svg)

![真实有效吞吐](figures/real_effective_throughput.svg)

## 解读

- 当前 workload 下总耗时最短的是 `promote`，耗时 `2.7416 s`。
- 当前 workload 下有效吞吐最高的是 `promote`，约 `64.2 MiB/s`。
- `full` 相比 baseline 的真实端到端速度为 `0.9612x`，说明当前 workload 或参数下策略开销尚未被命中收益抵消。
- 这不是坏结果，而是后续调参和论文分析的依据：成本模型预测的是长期服务代价，真实速度还受 FUSE 开销、后台任务是否真正触发、远端是否足够慢、热点复用强度等因素影响。

## 论文中怎么使用

- `objective_cost_per_request` 用来解释控制器的决策质量，是策略层指标。
- `wall_time_s`、`effective_mib_s`、`avg_read_us` 用来回答系统实际快不快，是真实运行指标。
- 如果两者方向不一致，必须优先相信真实速度结果，并回头调整 workload、参数和成本权重。
