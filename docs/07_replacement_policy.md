# 07 本地缓存替换策略

本地 SSD 是低延迟层，但容量有限。替换策略决定“本地满了删谁”，也决定新写入、热点提升和预取能不能真正落地。

## 1. 策略目标

TokenFS/AURA-KV 不把本地 SSD 当作永久存储，而是把它当作 GPU 节点附近的高价值缓存层。远端 NVMe-oF SSD 是容量层和共享主副本层。

替换策略的目标是：

```text
尽量让未来代价高、复用概率高、重算代价高的数据留在本地；
把冷数据、低价值数据、可从远端安全恢复的数据移出本地。
```

## 2. 当前工程路径

TokenFS 主路径已经实现：

- 本地配额。
- 本地优先写入。
- 本地不足时溢写远端。
- 远端热点提升到本地。
- 顺序 shard 预取到本地。
- 本地缓存 GC。
- 价值感知本地淘汰。

相关代码：

- `src/main.cpp`
- `SpillIfNeeded`
- `EvictLocalFile`
- `PromoteToLocal`
- `PrefetchToLocal`
- `scripts/eviction_test.sh`
- `scripts/promote_test.sh`
- `scripts/prefetch_test.sh`

## 3. 为什么不用单纯 LRU

LRU 只看“最近有没有访问”。但 KV Cache 场景里，最近访问不等于未来价值：

| 情况 | LRU 的问题 |
|---|---|
| 长 prompt KV Cache 近期没访问，但一旦访问重算很贵 | 可能被误删 |
| 小文件频繁访问，但远端读很便宜 | 可能被过度保护 |
| 共享前缀被多个 GPU 间歇性访问 | 只看单节点最近访问会低估价值 |
| 本地缓存无远端主副本 | 不能直接删除 |

因此当前策略使用成本模型中的 `EvictionLoss`。公式见 [06_cost_model.md](06_cost_model.md)。

## 4. 删除候选

一个本地副本只有满足以下条件才进入删除候选：

```text
远端已有主副本
或者 peer 有 READY 副本
或者对象可重算
```

如果没有替代来源，删除会导致数据不可恢复，控制器必须拒绝。

## 5. 评分维度

当前工程实现把以下信息纳入本地缓存价值：

| 维度 | 含义 |
|---|---|
| 复用概率 | 未来还会不会访问 |
| 最近热度 | 是否刚刚变热 |
| 重算代价 | 如果没有缓存，重新生成有多贵 |
| 远端访问代价 | 从 NVMe-oF 远端读取有多慢 |
| GPU 亲和 | 是否主要由某个 GPU 使用 |
| 共享收益 | 是否服务多个请求或共享前缀 |
| 文件大小 | 占用多少本地空间 |

直观形式：

```text
本地保留价值 =
    未来需求 * 替代来源变慢幅度 * 重算/远端代价权重 * 亲和权重
    / 文件大小
```

正式公式见 [06_cost_model.md](06_cost_model.md)。

## 6. 动作结果

淘汰并不一定代表删除整个文件：

| 当前状态 | 淘汰动作 |
|---|---|
| `REMOTE_WITH_LOCAL_CACHE` | 删除本地缓存，保留远端主副本 |
| `LOCAL_ONLY` 且可迁移 | 先迁移到远端，再删除本地 |
| `LOCAL_ONLY` 且不可恢复 | 不允许淘汰 |
| 多个本地副本 | 删除低价值节点上的本地副本 |

## 7. 当前状态

Implemented：

- TokenFS 本地配额和溢写。
- 本地缓存提升、预取和 GC。
- AURA-KV 策略层 `NodeLRU`、`NodeLFU`、`SizeAwareLRU`、`SourceAwareReplacementPolicy`、`AuraKVPolicy`。
- `EvictionLoss` 原型和单元测试。

Partial：

- TokenFS 主路径和 AURA-KV Python 控制层尚未完全闭环。
- 真实 NVMe-oF P99、网络队列和 GPU 等待时间尚未接入评分。

Planned：

- 真实 trace 输入。
- 在线 shadow price 调参。
- 与 vLLM/SGLang 的 KV Cache 生命周期对接。
