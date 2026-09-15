# AURA-KV / TokenFS 最新统一结果报告

本文是当前仓库的最终结果入口。详细设计看 `README.md` 和 `docs/`，机器可读结果看 `reports/latest/paper-experiments/`。

## 1. 当前结论

当前项目已经完成：

| 类型 | 是否真实 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| TokenFS/FUSE 原型 | 真实代码路径 | 本地目录、远端目录、SQLite 元数据、配额、溢写和基础文件操作可运行 | 生产级分布式文件系统 |
| 双 VM NVMe-oF | 真实 Linux NVMe/TCP 协议 | Host/Target 连接、远端 Namespace 挂载、TokenFS 远端层可接 NVMe-oF | 真实物理 SSD/GPU 集群性能 |
| 实验室单客户端 NVMe-oF | 真实内网 NVMe/TCP 链路 | 本地 NVMe 与远端 NVMe-oF 的实际访问差距 | 多客户端并发和跨机器 GPU 亲和 |
| AURA-KV 策略实验 | 模拟/代理 | 价值感知替换和共享副本放置相对 LRU/LFU 等 baseline 的趋势 | 真实 vLLM/SGLang TTFT 收益 |

论文汇报时建议写：

```text
系统原型已经实现 FUSE 分层缓存、元数据管理、后台任务队列和动态监控；
NVMe-oF 层已完成双 VM 与实验室单客户端真实 NVMe/TCP 基线；
核心策略已通过 trace-driven simulator 完成多场景消融。
```

不要写成：

```text
已经完成真实多 GPU 集群端到端 TTFT 论文实验。
```

### 1.1 当前推荐真实实验路线

在只有一台远端 NVMe-oF 服务器、没有多台真实 GPU 计算节点时，当前应采用：

```text
Ubuntu VM / 内网客户端
  ├── TokenFS / AURA-KV
  ├── gpu0/gpu1/gpu2 多逻辑 GPU 本地缓存目录
  └── /srv/tokenfs/remote0 真实 NVMe-oF 挂载目录
        ↓
老师服务器 NVMe/TCP Target
```

这条路线比目录模拟更真实，因为远端容量层确实走 Linux NVMe/TCP；同时也比完整物理集群更保守，因为多个 GPU 仍是同一客户端内的逻辑节点。

统一运行入口：

```bash
TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/lab_single_client_multigpu_experiment.sh
```

输出：

```text
reports/latest/paper-experiments/08_lab_single_client_multigpu/
├── lab_single_client_multigpu_report.md
├── environment_evidence.txt
├── 01_environment_gap/
├── 02_single_run_speed/
└── 03_repeat_speed/
```

论文里这部分建议表述为：

```text
单客户端多逻辑 GPU + 真实远端 NVMe-oF 容量层实验。
```

## 2. 论文前四项实验

统一入口：

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
├── 07_real_speed_repeat/repeat_summary.csv
└── figures/
```

四项实验：

| 实验 | 当前用途 | 结果性质 |
|---|---|---|
| Trace 回放 | 比较多种策略在 13 个 KV Cache 场景下的整体表现 | 模拟结果 |
| 端到端延迟代理 | 比较本地、Peer、远端和后台动作共同造成的请求代价 | 代理结果 |
| 参数敏感性 | 扫描本地容量、远端 P99、副本预算，验证稳定性 | 模拟结果 |
| NVMe-oF baseline | 汇总已有真实 fio 数据，给远端访问代价提供依据 | 真实链路摘要 |
| 真实 TokenFS 速度 | 在 NVMe-oF 挂载目录上重复运行真实 FUSE workload | 真实系统结果 |

## 3. 消融实验完整汇总

本节直接汇总 `reports/latest/paper-experiments/01_trace_replay/trace_summary.csv`，用于比较 AURA-KV 与各类基线策略。所有策略都在同一组 13 个 KV Cache 场景下运行。

| 策略 | 场景数 | 本地命中率 | 远端读取 MiB | Peer 读取 MiB | 重复副本 MiB | 迁移 MiB | 副本抖动 | P50 ms | P95 ms | P99 ms | SLO 违反率 | 综合代价/请求 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| RemoteOnly | 13 | 0.0000 | 2244.77 | 0.00 | 0.00 | 0.00 | 0.00 | 1.2318 | 5.9711 | 9.0188 | 0.0051 | 3.1889 |
| LocalFirst | 13 | 0.7290 | 949.23 | 0.00 | 38.00 | 231.85 | 28.69 | 0.3933 | 3.2595 | 5.5199 | 0.0079 | 1.8880 |
| LRU-Local | 13 | 0.7362 | 400.62 | 0.00 | 64.00 | 400.62 | 38.69 | 0.3328 | 0.9761 | 3.0247 | 0.0000 | 1.7085 |
| LFU-Local | 13 | 0.7586 | 380.31 | 0.00 | 64.00 | 380.31 | 35.62 | 0.3167 | 0.9722 | 3.0594 | 0.0000 | 1.5691 |
| DualWindowReplacement | 13 | 0.8907 | 146.15 | 0.00 | 61.23 | 268.31 | 19.69 | 0.1066 | 0.5707 | 1.4685 | 0.0000 | 0.7717 |
| SourceAwareReplacement | 13 | 0.9423 | 0.00 | 221.54 | 59.08 | 185.85 | 23.62 | 0.2815 | 0.4045 | 0.4228 | 0.0000 | 0.9318 |
| AffinityOnly | 13 | 0.5900 | 1182.31 | 0.00 | 34.77 | 68.00 | 7.85 | 0.3615 | 3.1565 | 5.5917 | 0.0063 | 1.6883 |
| WA-Affinity-Independent | 13 | 0.7864 | 368.92 | 0.00 | 61.23 | 184.92 | 14.00 | 0.1703 | 1.0483 | 2.8872 | 0.0005 | 0.9922 |
| AURA-Joint | 13 | 0.8822 | 228.31 | 0.00 | 64.00 | 64.00 | 3.62 | 0.1579 | 0.6285 | 1.4749 | 0.0000 | 0.5376 |
| OracleDemand | 13 | 1.0000 | 0.00 | 0.00 | 64.00 | 380.31 | 35.62 | 0.1021 | 0.1264 | 0.1291 | 0.0000 | 0.8994 |

结论：

- AURA-Joint 的平均综合代价为 `0.5376/request`。
- 相比 LRU-Local 的 `1.7085/request`，综合代价降低约 `68.5%`。
- 相比 LFU-Local 的 `1.5691/request`，综合代价降低约 `65.7%`。
- AURA-Joint 的优势不是单项命中率永远最高，而是同时控制远端读取、迁移量、重复副本和布局抖动。

### 3.1 更直观的总性能指标

为了回答“模型到底有没有更快”，当前报告把综合代价转换成等效性能指数：

```text
等效性能指数 = LRU-Local 综合代价 / 当前策略综合代价
```

因此 `LRU-Local = 1.00x`，数值越大越好。它不是 fio 的物理吞吐量，而是结合前台延迟、远端读取、Peer 读取、后台迁移、重复副本空间和副本抖动后的策略级总性能指标。

![等效性能提升柱状图](paper-experiments/figures/effective_performance_index.svg)

| 策略 | 综合代价/请求 | 等效性能指数 | 相对 RemoteOnly | AURA 相比该策略降低代价 |
|---|---:|---:|---:|---:|
| RemoteOnly | 3.1889 | 0.5358x | 1.0000x | 83.14% |
| LocalFirst | 1.8880 | 0.9049x | 1.6890x | 71.53% |
| LRU-Local | 1.7085 | 1.0000x | 1.8665x | 68.53% |
| LFU-Local | 1.5691 | 1.0888x | 2.0323x | 65.74% |
| DualWindowReplacement | 0.7717 | 2.2139x | 4.1323x | 30.34% |
| SourceAwareReplacement | 0.9318 | 1.8335x | 3.4223x | 42.31% |
| AffinityOnly | 1.6883 | 1.0120x | 1.8888x | 68.16% |
| WA-Affinity-Independent | 0.9922 | 1.7219x | 3.2140x | 45.82% |
| AURA-Joint | 0.5376 | 3.1780x | 5.9317x | 0.00% |

![AURA 相对基线的综合代价降低](paper-experiments/figures/aura_improvement_vs_baselines.svg)

## 4. 真实 TokenFS Workload 多轮速度实验

前面的 `综合代价/请求` 是策略模型指标，依赖代价权重；它能解释控制器为什么选择某个布局，但不能单独证明系统真实变快。因此当前报告把真实速度实验单独列出，只看 TokenFS/FUSE 在 NVMe-oF 挂载目录上的实际 wall-clock 时间、有效吞吐和平均读写延迟。

输出位置：

```text
reports/latest/paper-experiments/07_real_speed_repeat/
├── repeat_report.md
├── repeat_summary.csv
├── repeat_runs.csv
└── figures/
```

本次实验按用户要求放大数据量并重复 3 次：默认使用 `32 MiB` shard、`160 MiB` 本地缓存配额，5 个策略每个策略每轮约 `8456 MiB` 逻辑读写量，3 轮合计约 `126.8 GiB` 逻辑 workload。它不是极端的“全热点”数据，而是混合了远端 canonical KV、本地冷缓存、容量压力、热点复用、连续 shard 访问和跨 GPU 共享读取；场景会适当覆盖 AURA-KV 的目标优势，但所有策略使用同一访问形状。

运行方式：

```bash
cp config/tokenfs.nvmeof.example.yaml config/tokenfs.nvmeof.yaml
# 填入真实 target_ip、subnqn、device
sudo ./scripts/connect_nvme.sh --config config/tokenfs.nvmeof.yaml --backend remote0 --chown-current
TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/real_speed_benchmark.sh
TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/real_speed_repeat_benchmark.sh
```

最新 3 轮均值和波动范围：

| 策略 | 轮数 | 每轮数据量 | 平均总耗时 | 耗时范围 | 平均有效吞吐 | 相对 RemoteOnly | 本地读命中率 | 远端打开读取 | 后台动作 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| RemoteOnly | 3 | 8456 MiB | 9.21 s | 8.98-9.65 s | 919.43 MiB/s | 1.000x | 0.00% | 260 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| LocalFirst | 3 | 8456 MiB | 8.52 s | 8.21-9.05 s | 994.03 MiB/s | 1.081x | 0.38% | 259 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| LRU-Local | 3 | 8456 MiB | 8.78 s | 7.86-9.70 s | 969.70 MiB/s | 1.053x | 0.38% | 259 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| LFU-Local | 3 | 8456 MiB | 8.54 s | 8.24-8.78 s | 990.57 MiB/s | 1.078x | 0.38% | 259 | promote=0, prefetch=0, evict=0, xgpu_hit=0 |
| AURA-Joint | 3 | 8456 MiB | 9.12 s | 8.88-9.33 s | 927.98 MiB/s | 1.010x | 96.15% | 10 | promote=1, prefetch=1, evict=1, xgpu_hit=62 |

这组结果需要诚实解释：

- AURA-Joint 的机制已经真实触发：本地读命中率达到 `96.15%`，远端打开读取从 `260` 次降到 `10` 次，说明热点提升、预取、淘汰和跨 GPU 本地副本确实在工作。
- 当前双 VM NVMe-oF 环境下，AURA-Joint 平均端到端速度只比 RemoteOnly 快 `1.010x`，并没有超过 LocalFirst、LRU 和 LFU。原因是该环境中本地与远端性能差距不够稳定，且 AURA 的元数据和后台副本管理开销会抵消一部分收益。
- 因此论文中可以把这组数据作为“真实系统机制验证 + 真实速度边界”，但不能把它写成“AURA 在当前真实环境中显著快于所有 baseline”。

图表：

![多轮总耗时](paper-experiments/07_real_speed_repeat/figures/repeat_wall_time_mean.svg)

![多轮有效吞吐](paper-experiments/07_real_speed_repeat/figures/repeat_effective_throughput_mean.svg)

![多轮加速比](paper-experiments/07_real_speed_repeat/figures/repeat_speedup_mean.svg)

## 5. 参数敏感性摘要

当前参数敏感性已经扫描：

| 参数 | 扫描范围 |
|---|---|
| 本地缓存容量 | 32 / 48 / 64 / 96 / 128 MiB |
| 远端 P99 代价 | 2 / 4 / 8 / 16 ms |
| 全局副本预算 | 64 / 96 / 128 / 192 MiB |

总体趋势：

- 本地容量更紧时，AURA-Joint 仍优于 LRU/LFU，因为它倾向保留高重算代价、高未来收益的对象。
- 远端 P99 更高时，本地副本更有价值，AURA-Joint 的相对收益更明显。
- 副本预算过小时，所有策略都会受限；预算达到一定程度后，AURA-Joint 不会盲目复制，而是继续受收益和防抖动门控约束。

## 6. 真实 NVMe-oF baseline

当前真实单客户端结果：

| 用例 | 操作 | 带宽 | IOPS | P99 |
|---|---|---:|---:|---:|
| 本机 NVMe 顺序读 | read | 2856.99 MiB/s | 2856.99 | 6.586 ms |
| 本机 NVMe 4K 随机读 | read | 959.91 MiB/s | 245737.55 | 0.224 ms |
| 远端 NVMe-oF 顺序读 | read | 112.21 MiB/s | 112.21 | 141.558 ms |
| 远端 NVMe-oF 顺序写 | write | 112.16 MiB/s | 112.16 | 166.724 ms |
| 远端 NVMe-oF 4K 随机读 | read | 110.16 MiB/s | 28201.84 | 1.188 ms |

这组数据支撑系统动机：远端 NVMe-oF 可以作为容量层和权威层，但本地 NVMe 更适合热点缓存。

## 7. 当前可写进论文的内容

可以写：

- AURA-KV / TokenFS 的系统架构与 FUSE 原型。
- 远端 NVMe-oF 权威层 + 本地 SSD 热缓存的设计。
- 价值感知本地缓存管理：需求估计、来源代价、EvictionLoss。
- 多 GPU 共享副本放置：ReplicaGain、访问亲和、趋势判断和防抖动。
- 前台请求与后台任务解耦：PROMOTE、PREFETCH、REPLICATE、EVICT、SWAP。
- trace-driven simulator 和多 baseline 消融实验。
- 双 VM 和实验室单客户端 NVMe/TCP baseline。

暂时不要写：

- 真实多 GPU 集群已经完整验证。
- 真实 vLLM/SGLang TTFT 已经降低。
- 生产级一致性和多客户端并发已经完成。

## 8. 最新仓库阅读方式

```text
README.md                         项目总入口
docs/README.md                    文档导航
docs/system-design.md             系统架构和一致性
docs/model-and-controller.md      模型与控制器
docs/experiments.md               实验和结果解释
docs/deployment.md                部署和 NVMe-oF 接入
reports/latest/final-report.md    最新结果汇总
reports/latest/paper-experiments/ 机器可读实验数据、图表和真实速度报告
```
