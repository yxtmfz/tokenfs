# TokenFS 优化路线

本文档记录 TokenFS 后续可以继续展开的工程优化和论文实验点。核心目标不是把所有功能一次做满，而是围绕“大规模机器学习 Token 数据在 GPU 本地 SSD 与 NVMe-oF 远端 SSD 之间如何放置、迁移、预取和观测”形成可验证的研究路线。

## 1. 测试与可视化优化

### 多维性能报告

当前已经支持从 fio JSON 自动生成：

- `summary.csv`
- `report.md`
- `report.html`

报告应同时展示：

- 带宽 MiB/s：大块顺序读写能力。
- 耗时 s：端到端完成一次 workload 的时间。
- IOPS：每秒 I/O 次数。
- 平均延迟、P95、P99：请求等待时间和尾延迟。

论文中不能只看带宽，因为远端 NVMe-oF 即使带宽高，也可能有更高单次访问延迟。

### 测试矩阵扩展

建议加入：

| 测试类型 | 块大小 | 目的 |
|---|---:|---|
| 顺序读写 | 1 MiB | 测大文件 token shard 吞吐 |
| 随机读写 | 4 KiB | 测小块 IOPS 和延迟 |
| 随机读写 | 16 KiB | 模拟小 token block |
| 混合读写 | 64 KiB | 模拟训练过程中的交错访问 |
| 重复读取热点集 | 1 MiB | 测热点提升和预取效果 |

## 2. 本地层优化

### 热点提升

当前已经实现基础版本：

```text
远端文件 read_count 达到阈值
    ↓
检查 GPU 本地配额
    ↓
复制到本地
    ↓
更新 SQLite 元数据 tier=local
```

后续可优化：

- 按时间窗口统计热度，而不是总 read_count。
- 为不同 GPU 分别维护热点排行榜。
- 设置最大提升文件大小，避免单个超大 shard 挤占本地空间。
- 引入提升冷却时间，避免频繁来回迁移。

### 本地淘汰

目前如果本地配额不足，热点提升或预取会跳过。后续可以加入淘汰策略：

- LRU：淘汰最近最少访问的本地文件。
- LFU：淘汰访问次数最低的本地文件。
- Size-aware：优先淘汰大而冷的文件。
- Cost-aware：综合远端读取耗时、文件大小和访问频率。

论文实验可以对比：

```text
无淘汰
LRU 淘汰
LFU 淘汰
Cost-aware 淘汰
```

## 3. 预取优化

### 顺序 shard 预取

当前已经实现基础版本：

```text
读取 shard-000001.tokens
    ↓
识别下一片 shard-000002.tokens
    ↓
后台预取到 GPU 本地目录
```

后续可优化：

- 预取窗口：一次预取后续 N 个 shard。
- 自适应窗口：连续命中时扩大窗口，未命中时缩小窗口。
- 预取限速：限制后台预取带宽，避免抢占训练任务 I/O。
- 预取取消：如果训练任务转向其他数据集，取消无用预取。
- GPU 感知预取：不同 GPU 的预取队列相互隔离。

### 预取命中率指标

可以加入：

- `prefetch_hit_count`
- `prefetch_miss_count`
- `prefetch_waste_bytes`
- `prefetch_wait_saved_us`

这些指标比单纯带宽更适合证明预取策略的价值。

## 4. NVMe-oF 路径优化

### 连接配置化

当前已经支持用配置和环境变量连接 NVMe/TCP。后续可以增加：

- 多 Target 配置。
- 多 Namespace 配置。
- Host NQN ACL 检查。
- 连接健康检查。
- 断线自动重连。

### 多远端后端选择

真实环境可能有多个远端 SSD Target。可以设计：

- round-robin：轮询放置。
- capacity-aware：选择剩余空间最多的后端。
- latency-aware：选择历史延迟最低的后端。
- gpu-affinity：选择离 GPU Host 网络路径最近的后端。

论文实验可以观察负载均衡和尾延迟变化。

## 5. 数据布局优化

### 连续写入

Token shard 适合大块顺序写入。当前已支持 `fallocate`，后续可以进一步：

- 写入前预分配完整 shard。
- 固定 shard 大小，例如 256 MiB、512 MiB、1 GiB。
- 对齐写入大小，例如 1 MiB 或 4 MiB。
- 减少小文件数量，用 manifest 管理多个 shard。

### 文件格式感知

可以为 token 文件维护额外元数据：

- model id
- tokenizer version
- token dtype
- token count
- shard index
- dataset id
- prompt prefix hash

这样后续可以做更智能的放置和预取。

## 6. 一致性和可靠性优化

### 元数据一致性检查

增加：

```bash
./scripts/tokenfsctl.py check
```

检查：

- DB 有记录但物理文件不存在。
- 物理文件存在但 DB 没记录。
- checksum 不一致。
- `CREATING` 长期残留。
- local/remote 两边出现同一逻辑文件。

### 故障注入

建议加入：

- FUSE 进程写入中被杀死。
- NVMe-oF Target 断开。
- 预取过程中断电。
- 远端文件迁移一半失败。
- SQLite 元数据提交前后崩溃。

实验指标：

- 已提交文件是否仍可读。
- 未提交文件是否不会被误认为有效。
- 恢复耗时。
- 孤儿文件数量。

## 7. 论文可形成的核心对比

建议最终形成至少四组对比：

```text
Baseline 1：直接本地 SSD
Baseline 2：直接 NVMe-oF 远端 SSD
Baseline 3：TokenFS 本地优先 + 远端溢写
Ours 1：TokenFS + 热点提升
Ours 2：TokenFS + 顺序预取
Ours 3：TokenFS + 淘汰 + 预取联合策略
```

关键指标：

- token workload 端到端耗时。
- GPU 等待数据时间。
- 本地读命中率。
- 远端读取字节数。
- P99 读取延迟。
- 预取命中率。
- 本地空间利用率。

这条路线可以把 TokenFS 从“能跑的系统原型”推进成“有明确研究问题和实验支撑的论文系统”。
