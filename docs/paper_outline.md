# AURA-KV 论文大纲草案

## Abstract

说明大模型推理 KV Cache 对分层存储的需求，提出 AURA-KV 作为候选研究原型，联合考虑替代来源感知替换和共享拓扑感知副本放置。

## Introduction

论证链：

```text
KV Cache 容量压力增大
本地 SSD 延迟低但容量有限
NVMe-oF 远端 SSD 容量大但访问更慢
前缀/KV Cache 共享存在但并非所有任务都共享
简单 LRU/LFU 或固定副本策略无法同时处理价值、替代来源、共享拓扑和预算
```

## Motivation

通过模拟和后续真实微基准展示：

```text
远端读取长尾影响 P99
高重算成本前缀被 LRU 误淘汰
固定副本浪费重复空间
ProducerLocal 在跨节点共享时远端流量高
独立替换和独立副本控制可能冲突
```

## Problem Definition

把问题定义为多动作在线决策：

```text
KEEP / PROMOTE / REPLICATE / DEMOTE / EVICT_LOCAL / DROP_RECOMPUTABLE / PIN / PREFETCH
```

约束包括容量、重复预算、SLO、后台带宽、安全域和一致性。

## System Design

介绍：

```text
FUSE 统一命名空间
远端权威副本
节点本地缓存副本
访问图
预测器
替代来源解析器
共享状态分类器
联合控制器
决策日志
```

## Candidate Innovation 1

替代来源感知的学习型 KV Cache 多动作替换。

## Candidate Innovation 2

动态共享拓扑感知的预算化 KV Cache 副本放置。

## Joint Controller

强调两个模块不是独立 if-else：替换策略需要知道全局副本和替代来源，副本放置需要使用预测、冷却概率和重计算代价。

## Implementation

介绍 TokenFS 原型、SQLite、FUSE、模拟后端、MountedNVMeOFBackend 预留方式和 trace-driven simulator。

## Evaluation

比较 baseline：

```text
RemoteOnly
ProducerLocal
NodeLRU
NodeLFU
StaticNReplica
AffinityOnly
AIReplacementOnly
AlternativeAwareNoLearning
AURA-KV
```

指标包括本地命中率、远端读取、重复空间、P99、SLO 违约率和 churn。

## Related Work

分类讨论：

```text
KV Cache 管理
Prefix Cache
分层存储
NVMe-oF 存储系统
分布式缓存替换
副本放置
```

## Limitations

当前没有真实 GPU/NVMe-oF 环境；模拟结果不能作为真实性能结论；学习模型尚未证明优于解析式策略；新颖性仍需系统检索。

## Conclusion

总结 AURA-KV 的候选贡献和后续真实环境验证计划。

## 谨慎声明

AURA-KV 的新颖性主张仍需通过系统性论文、专利和开源系统检索验证，当前实现属于候选研究原型，不得直接宣称全球首创。

