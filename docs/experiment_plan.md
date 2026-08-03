# AURA-KV 实验计划

## 1. 本文解决的问题

本文说明如何验证 AURA-KV 的研究主张。当前分为模拟实验和未来真实硬件实验。模拟实验只能验证逻辑和趋势，真实 NVMe-oF/GPU 环境到位后才能写论文性能结论。

## 2. 研究问题

| RQ | 问题 | 假设 |
|---|---|---|
| RQ1 | AURA-KV 是否比 RemoteOnly 降低远端读取和 P99？ | 本地副本会提高命中率 |
| RQ2 | 是否优于 LRU/LFU？ | 替代来源和重算代价能避免误淘汰 |
| RQ3 | 是否优于固定 N 副本？ | 预算化副本能减少重复空间 |
| RQ4 | 几乎无共享时额外开销是否低？ | 共享分类会退化为私有策略 |
| RQ5 | 热点迁移时 churn 是否受控？ | 租约、防抖和价格能减少震荡 |
| RQ6 | 预测错误时是否安全？ | SafetyGuard 和替代来源可避免数据丢失 |
| RQ7 | 高重算前缀是否更容易保留？ | prefix/recompute benefit 会提高价值 |
| RQ8 | 联合控制是否优于独立模块？ | 联合决策能减少冲突 |

## 3. 实验变量

自变量：

```text
策略 baseline
本地容量比例
共享比例
远端 P99
重算成本
需求估计误差
重复副本预算
```

因变量：

```text
local_cache_hit_rate
remote_read_bytes
duplicate_bytes
replica_churn
ttft_p99_ms
slo_violation_rate
recomputed_ms
decision_count
```

控制变量：

```text
随机种子
请求总数
缓存大小分布
节点/GPU 数量
模型和 token schema
```

## 4. 工作负载和基线

当前 simulator 已实现：

```text
private / node_shared / cluster_shared / hotspot_shift
high_recompute / remote_congestion / demand_estimation_error / tenant_isolation
```

baseline：

```text
RemoteOnly / ProducerLocal / NodeLRU / NodeLFU / SizeAwareLRU
WeightedScoreBaseline / EWMAReplacement / SourceAwareReplacement
PrefixSourceAwareReplacement / StaticNReplica / AffinityOnly
IndependentControllers / AURA-KV / OracleDemand / ExhaustiveOptimal
```

## 5. 预期图表

```text
图 1: 不同策略 P99 对比
图 2: 相同容量下本地命中率
图 3: 远端读取字节
图 4: 重复副本空间
图 5: 热点迁移时 churn
图 6: 需求估计误差敏感性
图 7: 消融实验柱状图
```

## 6. 结果如何解释

如果 AURA-KV P99 低但 duplicate_bytes 极高，说明它只是用更多空间换性能，不一定是好策略。若命中率高但 churn 高，说明副本策略不稳定。若 private 场景开销明显高于 ProducerLocal，说明共享检测太激进。

会否定当前设计的结果：

```text
AURA-KV 在多数场景不优于 SourceAwareReplacement
共享场景下重复空间显著高但 P99 无改善
需求估计误差导致大量错误复制
tenant_isolation 出现跨域命中
真实 NVMe-oF 下后台复制严重恶化前台 P99
```

## 7. 当前运行方式

```bash
./scripts/aura_kv_test.sh
python3 scripts/aura_kv_sim.py --output reports/latest/aura-kv-sim
```

输出标记 `SIMULATED RESULT`。

## 8. 实现状态

| 功能 | 状态 | 对应代码 | 对应测试 | 未完成原因 | 后续计划 |
|---|---|---|---|---|---|
| 8 个模拟场景 | Implemented | `aura_kv/simulator.py` | `aura_kv_test.sh` | 无 | 增加崩溃场景 |
| 15 个 baseline/策略 | Implemented | `aura_kv/policies.py` | simulator | 无 | 增加 ablation |
| CSV/JSON/MD 输出 | Implemented | `write_results()` | simulator | 无 | 增加画图脚本 |
| 真实硬件实验 | Planned | NVMe-oF scripts | 无 | 缺真实 IP/NQN | 环境到位后执行 |
