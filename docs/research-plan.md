# TokenFS 研究计划

## 研究定位

TokenFS 的目标不是重复实现一个通用分布式文件系统，而是面向大模型 Prompt、Token shard 和 KV cache 类数据，研究 GPU 本地 SSD 与 NVMe-oF 远端 SSD 之间的分层存储策略。

核心问题是：

```text
在 GPU 本地 SSD 容量有限、远端 NVMe-oF SSD 容量更大但访问更慢的条件下，
如何组织、放置、迁移和读取 Token 数据，降低 GPU 等待数据的时间。
```

## 已有系统和技术基础

### NVMe-oF 与 SPDK

NVMe-oF 已经是成熟的远程块设备访问技术。SPDK 官方文档说明，SPDK NVMe-oF Target 是用户态应用，可以通过 Ethernet、InfiniBand 或 Fibre Channel 暴露块设备，并支持 TCP 与 RDMA transport；Linux 内核也实现了 NVMe-oF Host 和 Target，并与 SPDK 有互通测试。

参考：

- SPDK NVMe-oF Target: https://spdk.io/doc/nvmf.html
- SPDK NVMe-oF Target Programming Guide: https://spdk.io/doc/nvmf_tgt_pg.html

TokenFS 不把“能连接 NVMe-oF”作为创新点，而是把它作为远端高速 SSD 后端。

### 通用分布式文件系统

CephFS、BeeGFS、3FS 等系统已经解决了通用分布式文件系统中的很多问题。

CephFS 基于 Ceph RADOS，使用 MDS 管理文件元数据，客户端可以直接访问底层对象存储读写文件数据。BeeGFS 将系统拆成 Management、Metadata、Storage 和 Client 服务，客户端可以并行访问多个存储服务器。DeepSeek 3FS 是面向 AI 训练和推理工作负载的高性能分布式文件系统，强调现代 SSD 和 RDMA 网络。

参考：

- Ceph Architecture: https://docs.ceph.com/en/latest/architecture/
- BeeGFS Architecture: https://doc.beegfs.io/8.1/architecture/overview.html
- DeepSeek 3FS: https://github.com/deepseek-ai/3fs

TokenFS 不直接挑战这些完整系统，而是选择更窄的机器学习 Token 数据场景做优化。

### 分层缓存与 KV Cache 系统

Alluxio 已经提供跨存储系统的缓存层，并支持 MEM、SSD、HDD 等多级存储。LMCache 面向 LLM KV cache，提供 GPU 外的持久化、分层缓存和复用能力；SGLang HiCache 将 GPU 显存、主机内存和分布式存储组织为 L1/L2/L3，并支持多种 L3 存储后端。

参考：

- Alluxio Caching: https://documentation.alluxio.io/os-en/core-services/caching
- LMCache: https://docs.lmcache.ai/
- LMCache Local Storage: https://docs.lmcache.ai/kv_cache/local_storage.html
- SGLang HiCache: https://docs.sglang.com.cn/advanced_features/hicache_design.html

TokenFS 可以借鉴这些系统的分层思想，但研究对象放在文件系统接口下的大容量 token shard、prompt 数据和本地/远端 SSD 布局。

## TokenFS 的差异化方向

TokenFS 的差异点应围绕以下问题展开：

1. GPU 感知：不同 GPU 有独立本地配额和访问统计，不再把所有数据当成同一种文件。
2. Token 感知：以 token shard、prompt prefix、model id、tokenizer version 等元数据组织文件。
3. 本地优先：优先使用 GPU 所在节点本地 SSD，空间不足时自动溢写到远端 NVMe-oF。
4. 连续布局：通过 `fallocate` 和顺序 shard 写入减少碎片，提高大文件顺序读写性能。
5. 可观测性：记录本地/远端读写次数、字节量、平均耗时、溢写次数和预分配次数。
6. 真实部署可迁移：开发阶段使用目录模拟远端，真实环境到位后改配置即可接入 NVMe-oF。

## 可优化点

### 1. 连续存储优化

Token 数据通常适合被组织成较大的 shard 文件。可以在写入前用 `fallocate` 预分配空间，再按固定 chunk 顺序写入，减少文件系统碎片和元数据更新压力。

可对比：

```text
普通写入
预分配 + 顺序写入
预分配 + 大 chunk 顺序写入
```

指标：

- 写入吞吐 MiB/s
- 读取吞吐 MiB/s
- 平均写耗时
- 平均读耗时
- P95/P99 延迟，后续加入

### 2. 本地命中率优化

当前策略是本地空间够就写本地，不够就写远端。后续可以加入：

- LRU：最近最少使用文件优先迁移到远端。
- LFU：低频文件优先迁移。
- Cost-aware：综合文件大小、远端读取成本、最近访问时间。
- GPU-aware：不同 GPU 的数据独立统计，避免一个 GPU 挤占全部本地空间。

指标：

- 本地读命中率
- 本地写命中率
- 远端读取比例
- GPU 等待数据时间

### 3. 远端预取

远端 NVMe-oF 的延迟通常高于本地 SSD。对于顺序读取的 token shard，可以提前预取后续 chunk 到本地缓存目录。

可设计策略：

- 顺序读检测：连续读取超过阈值后触发预取。
- shard 级预取：读取 shard-000001 后，提前拉取 shard-000002。
- 异步预取：后台线程完成迁移，避免阻塞当前读。

指标：

- 首次读取耗时
- 第二次读取耗时
- 预取命中率
- 远端带宽占用

### 4. 热点提升

远端文件被频繁读取后，可以自动提升到本地层。该策略适合多轮训练或推理反复访问同一批 prompt/token 数据的场景。

可设计策略：

- read count 阈值
- last access 时间窗口
- 按文件大小限制提升
- 本地空间不足时与 LRU/LFU 淘汰联动

指标：

- 提升前后平均读取延迟
- 本地空间占用
- 热点文件命中率

### 5. 多远端后端选择

真实环境可能有多个 NVMe-oF Namespace。TokenFS 可以根据不同策略选择远端后端：

- round-robin
- 最大剩余空间
- 最低历史读延迟
- GPU 到远端 Target 的网络亲和性

指标：

- 多远端负载均衡程度
- 单远端瓶颈是否缓解
- 吞吐和延迟变化

### 6. 元数据和物理文件一致性检查

FUSE 进程崩溃、机器重启或远端断开时，可能出现元数据和物理文件不一致。后续可增强 `tokenfsctl check`：

- DB 有记录但物理文件不存在。
- 物理文件存在但 DB 无记录。
- checksum 不一致。
- CREATING 状态长期残留。

指标：

- 故障注入后的恢复正确率
- 恢复耗时
- 孤儿文件数量

### 7. NVMe-oF 真实环境优化

接入真实 NVMe-oF 后，可以比较：

- directory-sim 远端
- NVMe/TCP 远端
- NVMe/RDMA 远端，若实验室提供
- SPDK Target，若后期具备条件

指标：

- 4 KiB 随机读写延迟
- 1 MiB 顺序读写吞吐
- CPU 使用率
- P99 延迟
- Token workload 端到端耗时

## 实验设计

### Baseline

1. 直接读写本地目录。
2. 直接读写远端挂载目录，包括目录模拟和 NVMe-oF 挂载两种形态。
3. TokenFS 本地层读写。
4. TokenFS 远端溢写读写。
5. TokenFS 预分配顺序 shard 写入。

当前已经加入双 VM NVMe-oF 基线脚本：

```text
scripts/nvmeof_perf_test.sh
```

它在真实 Linux NVMe/TCP Host/Target 协议路径上对比：

```text
direct-local
direct-nvmeof
tokenfs-local
tokenfs-remote-spill
```

输出：

```text
reports/nvmeof-perf/latest/report.md
reports/nvmeof-perf/latest/report.html
reports/nvmeof-perf/latest/summary.csv
reports/nvmeof-perf/latest/metrics.txt
```

双 VM 结果可用于证明协议接入和相对开销趋势，但由于后端是 loop 文件和虚拟网络，最终论文定量结论仍应基于真实 NVMe SSD、高速网络和实验室 GPU 服务器重新采集。

### Workload

1. 小 token shard：16 MiB。
2. 大 token shard：96 MiB 或更大。
3. 多 GPU namespace：`/gpu0`、`/gpu1`。
4. 顺序写入、顺序读取。
5. 后续加入随机读取和重复访问热点集。

### 当前已有指标

TokenFS 已经记录：

- `read_ops`
- `read_bytes`
- `read_local_ops`
- `read_remote_ops`
- `write_ops`
- `write_bytes`
- `write_local_ops`
- `write_remote_ops`
- `spill_count`
- `spill_bytes`
- `remote_place_count`
- `fallocate_ops`
- `fallocate_bytes`
- `read_latency_us_total`
- `write_latency_us_total`

这些指标可以通过：

```bash
./scripts/tokenfsctl.py metrics
```

查看。

## 论文可能标题

可以考虑：

```text
TokenFS: GPU-Aware Tiered File System for Large-Scale LLM Token Data over NVMe-oF
```

中文方向：

```text
面向大模型 Token 数据的 GPU 感知 NVMe-oF 分层文件系统
```

## 下一阶段里程碑

1. 接入真实 NVMe-oF Target，完成 `connect_nvme.sh --dry-run` 到真实连接的切换。
2. 增加真实远端读写性能报告。
3. 增加热点提升和预取策略。
4. 增加 `tokenfsctl check` 一致性检查。
5. 采集端到端 token workload 指标。
6. 将实验结果整理为论文图表。
