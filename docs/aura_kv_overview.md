# AURA-KV 研究原型总览

```text
AURA-KV
Adaptive Unified Replacement and Affinity-aware KV Cache Management
```

中文暂定名：

```text
面向 NVMe-oF 分层存储的自适应 KV Cache 联合替换与共享副本管理系统
```

AURA-KV 的目标是在 TokenFS 已有 FUSE 原型上，补齐论文实验所需的研究控制层。当前实现仍是候选研究原型，不声称已经具备论文结论，也不声称全球首次。

## 背景

目标环境中，远端 NVMe-oF SSD 保存大容量权威数据，本地 SSD 保存热点 KV Cache 副本。不同 GPU 的任务大多可能不同，但前缀共享、系统提示词共享、Agent 模板共享和长文档前缀共享确实存在。

系统要回答的问题不是“本地满了删最旧文件”，而是：

```text
哪些缓存值得留在本地？
删除某个本地副本后还能从哪里恢复？
共享缓存应复制到哪些计算节点？
副本数量如何受容量预算和预测收益约束？
后台复制如何不干扰前台推理？
```

## 当前落地范围

当前仓库新增了独立的 `aura_kv/` 研究实验框架：

| 模块 | 状态 | 说明 |
|---|---|---|
| CacheIdentity | 已实现 | 包含 sharing_domain、模型、token 前缀、tenant 等共享安全键 |
| EWMAAccessPredictor | 已实现 | 无需训练的解析式预测器，作为安全回退 |
| SharednessClassifier | 已实现 | 使用样本数、主导比例、共享熵和跨节点访问判断共享状态 |
| AlternativeSourceResolver | 已实现 | 判断 SAME_NODE、PEER_NODE、REMOTE、RECOMPUTE、NONE |
| ResourcePrices | 已实现基础版 | 维护容量、副本预算和 SLO 的影子价格 |
| AURA-KV Policy | 已实现原型 | 联合预测、替代来源、共享状态、预算和副本收益选择动作 |
| Trace Simulator | 已实现 | 可在无真实 IP 环境下运行可重复模拟 |
| 9 个 baseline | 已实现 | RemoteOnly、ProducerLocal、LRU、LFU、StaticNReplica 等 |

## 与现有 TokenFS 的关系

```text
TokenFS FUSE 主程序：负责真实挂载、读写、元数据和本地/远端目录后端
AURA-KV simulator：负责研究策略验证、基线对比和论文实验框架
```

这样做的好处是：当前没有真实 NVMe-oF IP 时，也可以先验证联合决策逻辑；未来有真实环境后，再把 AURA-KV 策略逐步接入 FUSE 主路径。

## 谨慎声明

AURA-KV 的新颖性主张仍需通过系统性论文、专利和开源系统检索验证。当前实现属于候选研究原型，不得直接宣称全球首创。

