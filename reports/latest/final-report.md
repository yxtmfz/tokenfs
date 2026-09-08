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
└── 04_nvmeof_baseline/real_nvmeof_summary.csv
```

四项实验：

| 实验 | 当前用途 | 结果性质 |
|---|---|---|
| Trace 回放 | 比较多种策略在 13 个 KV Cache 场景下的整体表现 | 模拟结果 |
| 端到端延迟代理 | 比较本地、Peer、远端和后台动作共同造成的请求代价 | 代理结果 |
| 参数敏感性 | 扫描本地容量、远端 P99、副本预算，验证稳定性 | 模拟结果 |
| NVMe-oF baseline | 汇总已有真实 fio 数据，给远端访问代价提供依据 | 真实链路摘要 |

## 3. 策略实验摘要

| 策略 | 本地命中率 | 远端读取 | P99 代理延迟 | 综合代价/请求 |
|---|---:|---:|---:|---:|
| RemoteOnly | 0.0000 | 2244.77 MiB | 9.0188 ms | 3.1889 |
| LocalFirst | 0.7290 | 949.23 MiB | 5.5199 ms | 1.8880 |
| LRU-Local | 0.7362 | 400.62 MiB | 3.0247 ms | 1.7085 |
| LFU-Local | 0.7586 | 380.31 MiB | 3.0594 ms | 1.5691 |
| DualWindowReplacement | 0.8907 | 146.15 MiB | 1.4685 ms | 0.7717 |
| AURA-Joint | 0.8822 | 228.31 MiB | 1.4749 ms | 0.5376 |

结论：

- AURA-Joint 的平均综合代价为 `0.5376/request`。
- 相比 LRU-Local 的 `1.7085/request`，综合代价降低约 `68.5%`。
- 相比 LFU-Local 的 `1.5691/request`，综合代价降低约 `65.7%`。
- AURA-Joint 的优势不是单项命中率永远最高，而是同时控制远端读取、迁移量、重复副本和布局抖动。

## 4. 参数敏感性摘要

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

## 5. 真实 NVMe-oF baseline

当前真实单客户端结果：

| 用例 | 操作 | 带宽 | IOPS | P99 |
|---|---|---:|---:|---:|
| 本机 NVMe 顺序读 | read | 2856.99 MiB/s | 2856.99 | 6.586 ms |
| 本机 NVMe 4K 随机读 | read | 959.91 MiB/s | 245737.55 | 0.224 ms |
| 远端 NVMe-oF 顺序读 | read | 112.21 MiB/s | 112.21 | 141.558 ms |
| 远端 NVMe-oF 顺序写 | write | 112.16 MiB/s | 112.16 | 166.724 ms |
| 远端 NVMe-oF 4K 随机读 | read | 110.16 MiB/s | 28201.84 | 1.188 ms |

这组数据支撑系统动机：远端 NVMe-oF 可以作为容量层和权威层，但本地 NVMe 更适合热点缓存。

## 6. 当前可写进论文的内容

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

## 7. 最新仓库阅读方式

```text
README.md                         项目总入口
docs/README.md                    文档导航
docs/system-design.md             系统架构和一致性
docs/model-and-controller.md      模型与控制器
docs/experiments.md               实验和结果解释
docs/deployment.md                部署和 NVMe-oF 接入
reports/latest/final-report.md    最新结果汇总
reports/latest/paper-experiments/ 机器可读实验数据
```
