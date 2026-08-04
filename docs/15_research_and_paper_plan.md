# 15 研究与论文计划

本文给出当前项目适合继续推进的研究路线。

## 1. 暂定题目

```text
面向多 GPU 大模型 KV Cache 的本地与 NVMe-oF 远端自适应分层缓存系统
```

也可以使用：

```text
GPU-Aware TierFS: 基于 NVMe-oF 的多 GPU KV Cache 自适应分层文件系统
```

## 2. 研究问题

大模型推理中的 KV Cache 具有以下特征：

- 数据体积大。
- 本地访问快但容量有限。
- 远端 NVMe-oF 容量大但存在网络代价。
- 某些 prompt prefix 或 KV Cache 可能跨请求、跨 GPU 共享。
- 错误的本地淘汰会导致远端读取或重计算代价增加。
- 盲目复制会占用本地空间和后台带宽。

研究目标是设计一个能同时处理本地替换和共享副本放置的分层缓存系统。

## 3. 当前保留的研究重点

### 3.1 代价驱动型本地缓存管理

核心问题：

```text
本地 SSD 空间有限，哪些 KV Cache 值得留在本地？
```

关键点：

- 不只看 LRU/LFU。
- 结合未来需求、重算代价、远端访问代价、数据大小和替代来源。
- 使用 `EvictionLoss` 做删除损失估计。

### 3.2 多 GPU 共享热点副本放置

核心问题：

```text
远端主副本存在时，哪些共享热点值得复制到哪些 GPU 节点本地？
```

关键点：

- 不默认所有 GPU 都共享。
- 只有公共前缀、KV Cache 共享或任务迁移出现时才触发。
- 使用时间窗口和趋势判断热点访问方。
- 使用 `ReplicaGain` 判断复制收益。
- 使用冷却时间、最短驻留时间和副本上限避免抖动。

## 4. 工程贡献

当前仓库已经具备：

- 可挂载 FUSE 原型。
- 本地/远端分层目录后端。
- SQLite 元数据和恢复检查。
- NVMe-oF 接入脚本。
- AURA-KV 策略模拟器。
- 多 baseline 和多场景模拟。
- 统一文档和结果入口。

## 5. 实验设计

### 5.1 Baseline

至少比较：

- RemoteOnly
- ProducerLocal
- NodeLRU
- NodeLFU
- SizeAwareLRU
- StaticNReplica
- AffinityOnly
- SourceAwareReplacement
- IndependentControllers
- AURA-KV
- OracleDemand

### 5.2 场景

至少覆盖：

- 私有缓存。
- 同节点共享。
- 跨节点共享。
- 热点迁移。
- 高重算成本。
- 远端拥塞。
- 需求估计误差。
- 租户隔离。

### 5.3 指标

- 本地命中率。
- 远端读取字节量。
- peer 读取字节量。
- 重计算时间。
- 本地重复副本占用。
- 副本创建/删除抖动。
- 迁移字节量。
- TTFT P50/P95/P99。
- SLO 违反率。

## 6. 真实环境阶段

真实 IP/NQN 到位后：

```text
1. 跑通 NVMe/TCP 连接
2. 测直接本地 SSD 和直接 NVMe-oF SSD
3. 跑 TokenFS baseline
4. 跑 AURA-KV 策略开关组合
5. 采集真实 P50/P95/P99 和带宽
6. 接入 vLLM/SGLang trace
```

## 7. 谨慎边界

当前不能直接声称：

- 真实 NVMe-oF 性能提升已经成立。
- 真实 GPU 推理 TTFT 已下降。
- 该方法一定优于所有现有系统。

当前可以说：

- 已实现可运行原型。
- 已把本地淘汰和共享副本放置统一到代价模型。
- 已具备无真实 IP 条件下的模拟验证和有真实 IP 条件下的接入路径。
