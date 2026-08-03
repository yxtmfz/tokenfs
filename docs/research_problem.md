# AURA-KV 研究问题定义

## 联合在线决策

在远端 NVMe-oF SSD 保存权威副本、各计算节点只有有限本地 SSD 的条件下，AURA-KV 将每个 KV Cache 块的管理建模为在线动作选择问题。

可选动作包括：

```text
KEEP
PROMOTE
REPLICATE
DEMOTE
EVICT_LOCAL
DROP_RECOMPUTABLE
PIN
PREFETCH
DEFER
```

系统优化目标包括：

```text
降低前台 P99/TTFT
减少远端读取流量
减少重计算开销
减少无价值重复副本
控制副本 churn
避免后台迁移干扰前台
```

约束包括：

```text
节点本地容量
全局重复副本预算
节点重复副本预算
前台 P99 SLO
后台迁移带宽
共享安全域和租户隔离
迁移一致性
```

## 当前可验证范围

当前没有真实 NVMe-oF 硬件，因此仓库中的 AURA-KV 实验结果只用于验证策略机制：

```text
SIMULATED RESULT
```

它可以说明：

```text
策略是否能运行
各 baseline 是否走同一批 trace
共享状态是否被正确分类
替代来源是否影响副本选择
预算是否影响副本创建
```

它不能说明：

```text
真实 NVMe-oF 延迟是多少
真实 GPU 推理 TTFT 下降多少
真实论文指标是否成立
```

