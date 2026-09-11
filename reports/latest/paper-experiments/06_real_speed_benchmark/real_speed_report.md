# TokenFS 真实速度实验

实验环境：TokenFS FUSE workload with verified NVMe-oF direct path: target=192.168.64.3, /dev/nvme0n1 -> /srv/tokenfs/remote0 (ext4)

本报告只使用真实程序运行产生的 wall-clock 时间、读写吞吐和 TokenFS 指标，不使用成本模型权重。它回答的是：在同一组 token shard workload 下，AURA-Joint 相比 RemoteOnly、LocalFirst、LRU-Local 和 LFU-Local 是否真的更快。

注意：`scripts/real_speed_benchmark.sh` 默认会强制检查远端后端已经通过 NVMe-oF 挂载，并要求 `TOKENFS_NVMEOF_PATH_MODE=direct`。只有 `backends[].type = nvmeof`、`nvme_target_ip` 是真实 Target IP、远端根目录已挂载、挂载源为 `/dev/nvme...` 时，才会生成可用于论文的直连 NVMe-oF 端到端速度结果。若显式设置 `TOKENFS_NVMEOF_PATH_MODE=tunnel`，结果只能作为功能验证，不能写成直连性能。

为避免 Linux 页缓存把远端 NVMe-oF 重复读取伪装成内存命中，真实速度脚本默认在关键阶段以及每次逻辑读取计时前请求清理 OS page cache；清理动作本身只作为 `cache_control` 证据记录，不计入策略读写耗时。这个控制条件不改变 workload 的访问分布，只用于让比较对象回到“本地 SSD 路径 vs 远端 NVMe-oF 路径”。

## 结果表

| 策略 | 总数据 MiB | 总耗时 s | 总吞吐 MiB/s | 总吞吐相对 RemoteOnly | 读吞吐 MiB/s | 读吞吐相对 RemoteOnly | 复用阶段吞吐 MiB/s | 复用阶段相对吞吐 | 平均读 us | 本地读命中率 | 远端打开读取 | 远端打开减少 | 后台动作证据 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `RemoteOnly` | 2120.0 | 9.9846 | 212.33 | 1.0x | 222.6 | 1.0x | 223.07 | 1.0x | 614.38 | 0.0% | 260 | 0.0% | promote=0, prefetch=0/0, evict=0, skip_hot=0, xgpu=0/0, spill=0 |
| `LocalFirst` | 2120.0 | 9.8412 | 215.42 | 1.0146x | 220.89 | 0.9923x | 220.81 | 0.9899x | 616.77 | 0.38% | 259 | 0.38% | promote=0, prefetch=0/0, evict=0, skip_hot=0, xgpu=0/0, spill=1 |
| `LRU-Local` | 2120.0 | 10.2084 | 207.67 | 0.9781x | 215.31 | 0.9673x | 215.26 | 0.965x | 635.81 | 0.38% | 259 | 0.38% | promote=0, prefetch=0/0, evict=1, skip_hot=0, xgpu=0/0, spill=0 |
| `LFU-Local` | 2120.0 | 10.9568 | 193.49 | 0.9113x | 198.14 | 0.8901x | 197.59 | 0.8858x | 684.0 | 0.38% | 259 | 0.38% | promote=0, prefetch=0/0, evict=1, skip_hot=0, xgpu=0/0, spill=0 |
| `AURA-Joint` | 2120.0 | 3.8229 | 554.55 | 2.6118x | 620.21 | 2.7862x | 637.74 | 2.8589x | 87.5 | 96.54% | 9 | 96.54% | promote=1, prefetch=7/1, evict=2, skip_hot=0, xgpu=1/62, spill=0 |

## 可视化

![真实总耗时](figures/real_wall_time.svg)

![真实相对加速比](figures/real_speedup_vs_baseline.svg)

![真实有效吞吐](figures/real_effective_throughput.svg)

![真实读吞吐](figures/real_read_throughput.svg)

![策略生效后复用阶段吞吐](figures/real_steady_reuse_throughput.svg)

## 解读

- 当前 workload 下总耗时最短的是 `AURA-Joint`，耗时 `3.8229 s`。
- 当前 workload 下有效吞吐最高的是 `AURA-Joint`，约 `554.55 MiB/s`。
- `AURA-Joint` 相比 `RemoteOnly` 的真实端到端速度提升为 `2.6118x`。
- 只看策略生效后的热点/预取/跨 GPU 复用阶段，`AURA-Joint` 相对 `RemoteOnly` 的吞吐为 `2.8589x`。该指标用于观察后台策略完成后，后续读取收益是否出现。

## 论文中怎么使用

- `objective_cost_per_request` 用来解释控制器的决策质量，是策略层指标。
- `wall_time_s`、`effective_mib_s`、`avg_read_us` 用来回答系统实际快不快，是真实运行指标。
- 如果两者方向不一致，必须优先相信真实速度结果，并回头检查实现开销、页缓存控制、后台迁移门槛和成本权重。
