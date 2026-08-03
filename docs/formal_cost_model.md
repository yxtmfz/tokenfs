# AURA-KV 正式代价模型

本文定义当前代码采用的统一数学模型。AURA-KV 默认使用 Gamma-Poisson 与 EWMA 这类在线统计估计器估计未来需求。

## 1. 未来需求估计

### 公式

对缓存 `k`、请求节点 `m` 和当前时间 `t`，历史访问按时间区间 `b` 聚合：

```text
c(k,m,b) = 区间 b 内节点 m 对缓存 k 的有效访问次数

w_b(t) = exp(-(t - t_b) / tau)

C_w(k,m,t) = Σ_b w_b(t) * c(k,m,b)

E_w(k,m,t) = Σ_b w_b(t) * Delta_b
```

采用 rate parameterization 的 Gamma-Poisson 模型：

```text
lambda(k,m) ~ Gamma(a0, b0)

a(k,m,t) = a0 + C_w(k,m,t)
b(k,m,t) = b0 + E_w(k,m,t)

mu_N(k,m,H) = H * a(k,m,t) / b(k,m,t)

sigma_N^2(k,m,H) =
    H * a(k,m,t) / b(k,m,t)
    + H^2 * a(k,m,t) / b(k,m,t)^2
```

当前不依赖外部统计库，使用单侧 Cantelli 界：

```text
kappa_delta = sqrt((1 - delta) / delta)

N_lower(k,m,H) = max(mu_N - kappa_delta * sigma_N, 0)
N_upper(k,m,H) = mu_N + kappa_delta * sigma_N
```

创建副本使用 `N_lower`，删除副本使用 `N_upper`。

### 考虑的因素

该公式覆盖访问频率、近期性、观察窗口长度、数据不足时的不确定性，以及不同节点的需求分布。共享度不作为人工权重加入，而是自然体现在不同节点的 `N(k,m,H)` 中。

### 变量说明

| 符号 | 含义 | 单位 | 数据来源 | 更新频率 | 代码字段 |
|---|---|---:|---|---|---|
| `k` | 缓存对象 | 无 | `CacheObject.identity.cache_key` | 创建时 | `cache_key` |
| `m` | 请求节点 | 无 | `AccessEvent.node_id` | 每次访问 | `node_id` |
| `b` | 时间区间 | 无 | 访问统计桶 | 每次访问 | `bucket_seconds` |
| `c(k,m,b)` | 有效访问次数 | 次 | `EffectivePrefixDemandTracker` | 每次访问 | `_events` |
| `t_b` | 区间代表时间 | 秒 | bucket 中点 | 控制周期 | `bucket_time` |
| `tau` | 时间衰减常数 | 秒 | 配置 | 配置加载 | `tau_seconds` |
| `Delta_b` | 区间长度 | 秒 | 配置 | 配置加载 | `bucket_seconds` |
| `a0,b0` | Gamma 先验参数 | 次、秒 | 配置 | 配置加载 | `a0`, `b0` |
| `H` | 预测窗口 | 秒 | 配置 | 控制周期 | `demand_horizon_seconds` |
| `delta` | 保守界风险参数 | 无 | 配置 | 配置加载 | `delta` |

### 计算逻辑

`C_w` 用指数衰减把近期访问看得更重；`E_w` 表示在同样衰减尺度下观察了多久。`a/b` 是访问率的后验均值，乘以未来窗口 `H` 得到未来访问次数均值。方差越大，说明不确定性越大；创建副本时使用下界，避免因偶然突发而复制；删除副本时使用上界，避免误删未来可能很热的数据。

### 数值案例

假设 `a0=1`、`b0=600s`、`H=600s`。某节点最近有效访问折扣次数 `C_w=5`，折扣观察时间 `E_w=300s`：

```text
a = 1 + 5 = 6
b = 600 + 300 = 900
mu_N = 600 * 6 / 900 = 4 次
```

若计算得到 `sigma_N=3`，`delta=0.1`，则 `kappa=3`：

```text
N_lower = max(4 - 3 * 3, 0) = 0
N_upper = 4 + 3 * 3 = 13
```

这表示数据很不确定：不应积极创建副本，但删除时必须假设未来最多可能有约 13 次访问。

### 硬约束和执行规则

容量、重复预算、后台带宽、唯一可靠副本、tenant 隔离、pin、正在读取、副本状态和前台 SLO 不进入需求公式，由 `LayoutConstraints` 和 `SafetyGuard` 管理。

### 适用假设

访问在短期内可以用到达率近似；历史窗口能代表未来窗口；时间衰减常数与 workload 阶段变化速度大致匹配。

### 局限性

突发批量访问、任务切换、真实推理调度变化和指标延迟会导致估计误差。OracleDemand 只允许在模拟器中读取真实未来访问，不能用于真实系统。

### 代码和测试

代码：`aura_kv/demand.py` 中的 `GammaPoissonDemandEstimator`、`EWMADemandEstimator`、`OracleDemandEstimator`。  
测试：`tests/aura_kv_unit_test.py` 中的需求边界、前缀去重和不确定性测试。

## 2. 前缀有效需求

### 公式

请求类别 `q` 实际需要的缓存块或前缀路径为 `P(q)`：

```text
N_effective(k,m,H) =
    Σ_{q: k in P(q)} N(q,m,H)
```

实现中，`request_id` 对同一缓存块最多计数一次。子缓存访问父前缀时，父前缀获得一次有效需求；如果子缓存能独立使用，不虚构父级依赖。

### 考虑的因素

该公式覆盖公共前缀、后代请求、同节点多 GPU 共享和跨节点共享，但不会简单用 `descendant_count` 作为价值。

### 变量说明

| 符号 | 含义 | 单位 | 数据来源 | 更新频率 | 代码字段 |
|---|---|---:|---|---|---|
| `q` | 请求类别或请求实例 | 无 | trace/workload | 每次访问 | `request_id` |
| `P(q)` | 请求实际需要的缓存路径 | 缓存 key 集合 | 数据路径 | 每次访问 | `cache_key`, `parent_cache_key` |
| `N(q,m,H)` | 请求未来需求 | 次 | DemandEstimator | 控制周期 | `DemandEstimate` |

### 数值案例

请求 `req-1` 读取 `child-A`，且数据路径需要 `parent-P`。系统对 `child-A` 和 `parent-P` 各计一次有效需求；如果同一个请求又访问 `child-B`，但仍使用同一个 `parent-P`，父前缀不会重复计数。

### 代码和测试

代码：`EffectivePrefixDemandTracker.observe()`。  
测试：`test_prefix_demand_deduplicates_request_id`。

## 3. 来源获取代价

### 公式

节点 `m` 从来源 `s` 获取缓存 `k` 的预计完成时间：

```text
C(m <- s,k) =
    QueueDelay(s)
  + FixedAccessLatency(s)
  + TransferTime(m,s,k)
  + DeserializeCost(k,s)
  + FormatConversionCost(k,s)
  + HostToDeviceTransferCost(k,m)

TransferTime(m,s,k) =
    Size(k) / EffectiveBandwidth(m,s)
```

`TransferTime` 以秒计算后乘以 1000 转成毫秒。

### 考虑的因素

该公式覆盖本地 SSD、peer READY 副本、NVMe-oF 远端权威副本和重计算来源；还预留队列、反序列化、格式转换和 Host 到 GPU 传输成本。

### 变量说明

| 符号 | 含义 | 单位 | 数据来源 | 更新频率 | 代码字段 |
|---|---|---:|---|---|---|
| `Size(k)` | 缓存大小 | Byte | 元数据 | 创建/更新 | `size_bytes` |
| `EffectiveBandwidth` | 有效带宽 | Byte/s | 配置或 metrics | 控制周期 | `*_bandwidth_bytes_per_s` |
| `QueueDelay` | 来源排队时间 | ms | metrics | 控制周期 | `*_queue_delay_ms` |
| `FixedAccessLatency` | 固定访问延迟 | ms | 配置/metrics | 控制周期 | `*_fixed_latency_ms` |
| `DeserializeCost` | 反序列化成本 | ms | 配置/测量 | 控制周期 | `deserialize_cost_per_mib_ms` |
| `FormatConversionCost` | 格式转换成本 | ms | 配置/测量 | 控制周期 | `format_conversion_cost_per_mib_ms` |
| `HostToDeviceTransferCost` | 主机到 GPU 传输成本 | ms | 配置/测量 | 控制周期 | `host_to_device_bandwidth_bytes_per_s` |

### 数值案例

缓存大小为 64 MiB，远端带宽为 1024 MiB/s，固定远端延迟 1.2 ms：

```text
TransferTime = 64 / 1024 s = 0.0625 s = 62.5 ms
C = 1.2 + 62.5 = 63.7 ms
```

若本地带宽为 3500 MiB/s、固定延迟 0.08 ms：

```text
C_local = 0.08 + 64/3500*1000 = 18.37 ms
```

### 硬约束和执行规则

来源必须 cache key、模型、tokenizer、LoRA、KV 格式和 sharing_domain 兼容；副本状态必须为 READY；checksum 和 version 必须有效；来源必须可达。

### 局限性

当前代码没有真实 NVMe-oF 队列深度和 TCP 重传指标，相关项默认配置为 0 或保守值，真实环境到位后由 metrics 更新。

### 代码和测试

代码：`aura_kv/cost_model.py`。  
测试：`test_transfer_units_are_bytes_per_second_to_ms`、`test_best_source_is_not_higher_than_available_sources`、`test_add_ready_source_does_not_increase_best_cost`。

## 4. 统一服务代价

### 公式

布局 `X` 和窗口 `H` 下：

```text
J(X,H,N) =
    Σ_k Σ_m N_effective(k,m,H) * C_X(k,m)
```

单位是毫秒，表示未来窗口内 KV Cache 获取的累计服务代价。它是在线布局决策的代理目标，不直接等同真实 TTFT P99。

### 数值案例

缓存 A 在 Node0 未来需求 10 次，当前最优来源 2 ms；在 Node1 未来需求 5 次，当前最优来源 8 ms：

```text
J_A = 10 * 2 + 5 * 8 = 60 ms
```

### 代码和测试

代码：`LayoutCostEvaluator` 调用 `DemandEstimator` 与 `SourceCostModel`。  
测试：`test_small_layout_enumeration_computes_best_j`。

## 5. 鲁棒删除损失

### 公式

删除节点 `n` 上缓存 `k` 的副本：

```text
X_remove = X \ {(k,n)}

EvictionLoss(k,n,H) =
    Σ_m N_effective_upper(k,m,H)
    * max(C_X_remove(k,m) - C_X(k,m), 0)
```

若删除后没有远端权威副本、没有兼容 peer 副本且不可重算，则 `EvictionLoss = infinity` 并禁止删除。

单位空间删除损失：

```text
EvictionLossDensity = EvictionLoss / Size(k)
```

密度只用于候选筛选，最终执行前必须构造候选布局重新计算。

### 考虑的因素

该公式通过需求上界和最优来源变化覆盖访问频率、近期性、未来不确定性、公共前缀有效需求、多节点访问位置、本地/peer/远端/重算来源、缓存大小、排队、带宽和 Host 到 GPU 传输。

### 数值案例

删除 Node0 本地副本后，Node0 从 2 ms 本地读变成 20 ms 远端读；需求上界 12 次：

```text
EvictionLoss = 12 * max(20 - 2, 0) = 216 ms
```

如果缓存 64 MiB：

```text
EvictionLossDensity = 216 / 64 = 3.375 ms/MiB
```

### 代码和测试

代码：`LayoutCostEvaluator.eviction_loss()`。  
测试：`test_eviction_loss_and_replica_gain_are_non_negative`、`test_delete_without_reliable_source_is_blocked`。

## 6. 鲁棒副本收益

### 公式

新增节点 `n` 上缓存 `k` 的副本：

```text
X_add = X ∪ {(k,n)}

D_ready(k,n) =
    CopyQueueDelay(n)
  + SourceReadTime(k)
  + Size(k) / AvailableBackgroundBandwidth(n)
  + VerificationTime(k,n)
  + MetadataCommitTime(k,n)

H_remaining = max(H - D_ready(k,n), 0)

ReplicaGain(k,n,H) =
    Σ_m N_effective_lower(k,m,H_remaining)
    * max(C_X(k,m) - C_X_add(k,m), 0)
```

如果 `D_ready >= H`，则 `ReplicaGain = 0`。

### 考虑的因素

该公式通过需求下界、复制完成时间和来源变化覆盖节点未来需求、跨节点共享范围、本地/peer/远端速度、缓存大小、后台带宽、剩余收益窗口和不确定性。

### 数值案例

缓存复制完成需要 100 秒，预测窗口 600 秒，剩余窗口 500 秒。Node1 需求下界 20 次，新增副本让来源从 30 ms 变为 5 ms：

```text
ReplicaGain = 20 * max(30 - 5, 0) = 500 ms
```

若缓存为 100 MiB：

```text
ReplicaGainDensity = 5 ms/MiB
```

### 代码和测试

代码：`LayoutCostEvaluator.replica_gain()`。  
测试：`test_zero_future_demand_or_ready_after_horizon_has_zero_replica_gain`。

## 7. 布局差分收益

### 公式

任意候选动作 `A` 构造候选布局 `X_A(t)`：

```text
DeltaC_A(k,m,t) = C_X(k,m) - C_X_A(t)(k,m)
```

保守布局收益：

```text
RobustBenefit(A;X,H) =
Σ_k Σ_m ∫_0^H [
    lambda_lower(k,m,t) * max(DeltaC_A(k,m,t), 0)
  - lambda_upper(k,m,t) * max(-DeltaC_A(k,m,t), 0)
] dt
```

离散实现按统计窗口分段求和。普通动作只有满足：

```text
RobustBenefit > MinimumLayoutImprovementMs
```

才执行。SWAP 必须构造完整候选布局，不能只算 `ReplicaGain - ΣEvictionLoss`。

### 代码和测试

代码：`LayoutCostEvaluator.robust_benefit_for_add()`、`robust_benefit_for_remove()`。  
测试：`test_no_layout_change_has_zero_robust_benefit`。

## 8. 硬约束

以下不进入人工加权分数，而由约束检查管理：

```text
节点本地 SSD 容量
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

代码：`aura_kv/optimization.py` 中的 `LayoutConstraints` 与 `SafetyGuard`。  
测试：容量预算、租约和删除保护相关单元测试。
