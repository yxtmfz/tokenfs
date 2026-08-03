# 替代来源与前缀有效需求感知的代价驱动型 KV Cache 替换策略

## 1. 本文解决的问题

本地 SSD 空间不足时，系统不能直接删除最久没有访问的缓存。一个很久没访问的公共前缀可能会让后续多个请求避免昂贵 prefill；一个刚访问过的大后缀也可能因为可快速重算而不值得保留。替换策略真正要回答的是：

```text
删除节点 n 上缓存 k 的本地副本后，未来窗口内所有请求的服务代价会增加多少？
```

因此本策略不使用人工加权的 `Frequency + Recency + Sharedness + RecomputeCost - Size` 总分，而是把未来需求和来源代价统一到毫秒单位。

## 2. 输入和输出

输入包括历史访问事件、前缀依赖、当前副本布局、远端权威副本状态、缓存大小、重算代价、本地/peer/远端带宽和延迟、容量预算、后台带宽、pin、读取状态和前台 SLO 状态。

输出不是简单 keep/evict，而是候选动作：

| 动作 | 含义 | 执行前提 |
|---|---|---|
| `KEEP` | 保留当前副本 | 删除损失较高或安全约束不允许删除 |
| `EVICT_LOCAL` | 删除本地副本 | 删除后仍有可靠来源，且损失足够低 |
| `DEMOTE` | 从本地降级到远端权威副本 | 远端权威副本已完成且校验有效 |
| `DROP_RECOMPUTABLE` | 丢弃可重算缓存 | 重算代价低且无持久保存必要 |
| `PIN` | 暂时禁止删除 | 唯一可靠来源、正在读取或业务显式 pin |
| `PREFETCH` | 后台预取 | 前台 SLO 安全且收益显著 |

## 3. 未来需求估计

当前默认使用 `GammaPoissonDemandEstimator`，保留 `EWMADemandEstimator` 作为简单基线，`OracleDemandEstimator` 只用于模拟实验。公式详见 [formal_cost_model.md](formal_cost_model.md)。

核心规则：

```text
创建副本看需求下界 N_lower
删除副本看需求上界 N_upper
```

这样做的直觉是：创建副本要保守，避免偶然突发导致大量复制；删除副本也要保守，避免数据不足时误删未来可能需要的缓存。

## 4. 前缀有效需求

公共前缀的价值不是后代数量，而是真正会经过该前缀的数据路径需求：

```text
N_effective(k,m,H) =
    Σ_{q: k in P(q)} N(q,m,H)
```

实现规则：

1. 同一 `request_id` 对同一缓存块最多计数一次；
2. 子请求确实使用父前缀时，父前缀获得一次有效需求；
3. 同一请求不能因为包含多个后代块而重复累计父前缀；
4. 后代缓存可以独立使用时，不虚构父级依赖。

代码位于 `aura_kv/demand.py` 的 `EffectivePrefixDemandTracker`。

## 5. 来源代价

节点 `m` 从来源 `s` 获取缓存 `k` 的预计完成时间：

```text
C(m <- s,k) =
    QueueDelay(s)
  + FixedAccessLatency(s)
  + TransferTime(m,s,k)
  + DeserializeCost(k,s)
  + FormatConversionCost(k,s)
  + HostToDeviceTransferCost(k,m)
```

来源包括当前节点本地 SSD、peer READY 副本、NVMe-oF 远端权威副本和模型重算。当前不存在的测量项可以配置为 0，但文档和代码都保留字段，真实环境到位后可接入 metrics。

代码位于 `aura_kv/cost_model.py`。

## 6. 鲁棒删除损失

当前布局为 `X`，删除节点 `n` 上缓存 `k`：

```text
X_remove = X \ {(k,n)}

EvictionLoss(k,n,H) =
    Σ_m N_effective_upper(k,m,H)
    * max(C_X_remove(k,m) - C_X(k,m), 0)
```

如果删除后没有远端权威副本、没有兼容 peer 副本且不可重算，则 `EvictionLoss = infinity` 并禁止删除。

单位空间删除损失：

```text
EvictionLossDensity = EvictionLoss / Size(k)
```

该密度只用于快速筛选候选副本，最终执行前仍需构造候选布局并重新计算完整变化。

### 数值案例

Node0 的本地副本读取代价为 2 ms。删除后，Node0 只能从远端读，代价为 20 ms。未来需求上界为 12 次：

```text
EvictionLoss = 12 * max(20 - 2, 0) = 216 ms
```

若缓存大小 64 MiB：

```text
EvictionLossDensity = 216 / 64 = 3.375 ms/MiB
```

## 7. 硬约束

以下因素不进入人工加权总分，而作为硬约束：

```text
节点本地容量
全局重复容量
节点重复容量
后台带宽
单周期迁移量
tenant 和 sharing_domain 隔离
唯一可靠副本保护
pin 和正在读取状态
副本状态合法性
前台 SLO 门控
最小驻留时间
```

## 8. 伪代码

```text
OnControlCycle:
    update effective demand statistics
    update source cost metrics
    for each READY replica (k,n):
        if hard constraints say delete is unsafe:
            mark KEEP or PIN
            continue
        loss = EvictionLoss(k,n,H)
        if loss is infinity:
            mark PIN
        else if node capacity pressure is high and loss is low:
            create EVICT_LOCAL candidate
    sort candidates by EvictionLossDensity
    for top candidates:
        construct candidate layout
        recompute RobustBenefit
        execute only if all constraints pass
```

## 9. 示例

### 私有低重算缓存

缓存 20 GiB，未来需求上界接近 0，重算只需 20 ms，远端也有权威副本。删除后最优来源变化小，`EvictionLoss` 低，适合作为淘汰候选。

### 跨节点公共前缀

缓存 100 MiB，多个节点都依赖该前缀，未来需求上界高。即使最近访问间隔较长，删除会让多个节点退回远端或重算，`EvictionLoss` 高，应保留或 pin。

### 热但有近邻副本

某缓存在 Node0 很热，但 Node1 已有 READY peer 副本且 peer 访问代价接近本地。删除 Node0 本地副本后最优来源只小幅变差，删除损失可能低于另一个无替代来源的冷缓存。

## 10. 测试和实验

测试覆盖：

```text
Byte/Byte/s 到 ms 转换
最优来源单调性
删除来源不会降低最优来源代价
EvictionLoss 非负
无可靠来源禁止删除
前缀需求去重
租约到期不自动删除
不确定性增大时删除更保守
```

实验 baseline 包括 LRU、LFU、SizeAwareLRU、WeightedScoreBaseline、EWMAReplacement、SourceAwareReplacement、PrefixSourceAwareReplacement 和 AURA-KV。

## 11. 容易误解的地方

1. EWMA 和 Gamma-Poisson 是在线统计估计器，输出未来需求上下界。
2. 共享度不是单独权重，跨节点共享通过不同节点上的有效需求体现。
3. 缓存大小不是简单惩罚项，而通过传输时间、容量约束和单位空间收益体现。
4. 删除密度只能筛选候选，不能替代完整布局差分验证。

## 12. 实现状态

| 功能 | 状态 | 对应代码 | 对应测试 | 未完成原因 | 后续计划 |
|---|---|---|---|---|---|
| Gamma-Poisson 需求估计 | Implemented | `aura_kv/demand.py` | `tests/aura_kv_unit_test.py` | 无 | 接入真实 trace |
| EWMA 需求估计 | Implemented | `aura_kv/demand.py` | unit | 无 | 保留 baseline |
| OracleDemand | Implemented for simulator | `aura_kv/demand.py` | simulator | 只能用于模拟 | 严禁真实路径使用 |
| 前缀有效需求去重 | Implemented | `EffectivePrefixDemandTracker` | unit | 当前依赖 parent_cache_key | 接入真实 KV 路径 |
| 来源代价模型 | Implemented | `aura_kv/cost_model.py` | unit | 真实 metrics 未接入 | 接入 NVMe-oF 指标 |
| EvictionLoss | Implemented | `aura_kv/layout.py` | unit | SWAP 仍简化 | 增加完整 swap planner |
| SafetyGuard | Partial | `aura_kv/optimization.py` | unit | 未接入并发执行器 | 加 decision_log |
