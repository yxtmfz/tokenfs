# 候选创新一：替代来源感知的学习型 KV Cache 多动作替换

暂定英文名：

```text
Alternative-Source-Aware Learned Replacement
```

## 核心区别

传统 LRU/LFU 主要回答：

```text
这个缓存未来还会不会被访问？
```

AURA-KV 进一步回答：

```text
如果删掉当前本地副本，未来请求还能从哪里获得它？
这个替代来源相比本地命中会多付出多少代价？
```

替代来源包括：

```text
SAME_NODE_REPLICA
PEER_NODE_REPLICA
REMOTE_NVME_OF
RECOMPUTE
NONE
```

`NONE` 表示没有安全替代来源，安全规则层必须阻止删除。

## 三层决策

```text
轻量预测器：预测未来访问、冷却概率和置信度
在线优化器：结合容量、预算、SLO 和替代来源选择动作
安全规则层：阻止不安全删除，预测失败时回退到解析式策略
```

当前代码中：

```text
aura_kv/prediction.py      EWMAAccessPredictor
aura_kv/policies.py        AlternativeSourceResolver、AlternativeAwareNoLearning、AURA-KV
aura_kv/simulator.py       trace-driven 验证
```

## 当前实现的价值函数

当前 AURA-KV 策略使用简化可解释收益：

```text
benefit =
    predicted_hits * alternative_source_penalty
  + recompute_saving
  + prefix_dependency_benefit
  - capacity_shadow_price
  - duplicate_shadow_price
  - churn_penalty
```

这不是最终论文公式，只是当前可运行原型。真实环境到位后需要通过 trace、消融实验和参数敏感性分析继续校准。

