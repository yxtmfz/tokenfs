# AURA-KV 联合优化控制器

两个候选创新不能做成互不交互的模块。AURA-KV 当前原型采用统一策略入口 `AuraKVPolicy`，在一次访问决策中同时读取：

```text
预测访问需求
共享状态
替代来源
本地容量压力
全局重复副本预算
节点重复副本预算
churn 惩罚
```

## 决策信息流

```text
AccessPredictor
  -> future_hits_by_node
  -> cold_probability
  -> confidence

SharednessClassifier
  -> PROVISIONAL_PRIVATE / GPU_PRIVATE / NODE_SHARED / CLUSTER_SHARED

AlternativeSourceResolver
  -> SAME_NODE_REPLICA / PEER_NODE_REPLICA / REMOTE_NVME_OF / RECOMPUTE / NONE

ResourcePrices
  -> lambda_capacity
  -> lambda_duplicate
  -> lambda_slo

AuraKVPolicy
  -> KEEP / PROMOTE / REPLICATE / PIN / DEFER
```

当前实现位于：

```text
aura_kv/policies.py
```

## 影子价格

资源越紧张，价格越高：

```text
lambda_capacity[node] += eta * (used_ratio - target)
lambda_duplicate += eta * (duplicate_ratio - target)
lambda_slo += eta * (observed_p99 - target_p99)
```

当前实现是基础版，用于让副本创建不依赖固定 N。后续真实实验需要继续验证稳定性和参数敏感性。

## 安全回退

当预测置信度不足时，系统不让 AI 直接删除文件，而是降低预测权重并依赖解析式替代来源、预算和安全规则。

当替代来源为 `NONE` 时，策略输出 `PIN`，禁止删除。

