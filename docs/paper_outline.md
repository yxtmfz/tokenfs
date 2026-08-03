# AURA-KV 论文大纲草案

## 1. Abstract

要证明：多 GPU KV Cache 分层存储需要联合考虑替换和共享副本放置。图表不放在摘要，但摘要应给出问题、方法和谨慎结论。当前还不能写真实性能提升百分比，必须等真实实验。

审稿人可能质疑：是否只是缓存策略组合。回应方向：强调替代来源、共享拓扑、预算和联合控制的系统问题，并用消融证明各部分必要性。

## 2. Introduction

论证链：

```text
长上下文和 Agent 推理增加 KV Cache 压力
本地 SSD 低延迟但容量有限
远端 NVMe-oF 容量大但有网络长尾
共享前缀存在但并非所有数据共享
简单替换或固定副本策略不够
AURA-KV 提出候选联合方案
```

需要图：系统动机图和简单 baseline 对比图。

当前证据：模拟器和 FUSE 原型。真实性能结论待补。

## 3. Motivation

要证明几个痛点：

```text
RemoteOnly 远端流量高
ProducerLocal 跨节点共享差
LRU 可能误删高重算前缀
StaticNReplica 可能浪费空间
独立模块可能互相冲突
```

实验：motivation benchmark，先用模拟，后用真实 NVMe-oF。

## 4. Problem Definition

定义 K、N、动作集合、容量和预算约束、SLO 目标。需要把公式和变量解释清楚，不追求复杂证明。

## 5. System Design

使用架构图说明：

```text
FUSE/统一接口
元数据
访问预测
共享拓扑
替代来源
联合控制器
I/O 调度
本地/远端存储
```

审稿人可能问为什么不用现成缓存系统。回应：现有系统通常不同时处理替代来源、前缀依赖、共享拓扑和 NVMe-oF 分层约束。

## 6. Candidate Innovation 1

写替代来源与前缀结构感知的多动作替换。图：替代来源流程图、前缀树示例。

当前证据：`AlternativeAwareNoLearning` 和 `AURA-KV` baseline 已可模拟。学习模型尚未训练，论文中不能过度强调“AI”效果。

## 7. Candidate Innovation 2

写动态共享拓扑感知的预算化副本放置。图：CacheNodeGraph、私有/共享状态机、副本租约状态机。

当前证据：simulator 有 node_shared、cluster_shared、hotspot_shift、tenant_isolation 场景。

## 8. Joint Controller

这是核心章节。要证明两个创新点不是独立 if-else。图：控制周期时序图、冲突矩阵、资源影子价格变化图。

当前证据：`AuraKVPolicy` 是简化联合策略；完整事务控制器尚未实现，论文前必须补足或诚实限制。

## 9. Implementation

说明 TokenFS FUSE 原型、SQLite、目录后端、NVMe-oF 脚本、AURA-KV simulator。不要把 Planned 写成 Implemented。

## 10. Evaluation

baseline：

```text
RemoteOnly / ProducerLocal / NodeLRU / NodeLFU / StaticNReplica
AffinityOnly / AIReplacementOnly / AlternativeAwareNoLearning / AURA-KV
```

指标：

```text
P99/TTFT
local hit rate
remote bytes
duplicate bytes
churn
recompute_ms
decision overhead
```

真实实验前，所有结果必须标注 simulated。

## 11. Related Work

分类：

```text
LLM KV Cache / Prefix Cache
分布式缓存替换
副本放置
分层存储
NVMe-oF 存储系统
vLLM/SGLang/LMCache 等系统
```

需要系统检索后才能写新颖性边界。

## 12. Limitations

必须承认：

```text
真实硬件未到位
学习模型尚未证明优于 EWMA
当前联合控制器是原型
FUSE 路径性能可能不是最终部署形态
NVMe/RDMA 和 SPDK 尚未评估
```

## 13. Conclusion

总结候选贡献和后续验证路线，不写过强结论。

## 14. 实现状态

| 章节材料 | 状态 | 证据 | 缺口 |
|---|---|---|---|
| Background | Partial | README/docs | 需要补相关工作 |
| System Design | Partial | docs + code | 需要图表打磨 |
| Innovation 1 | Partial | simulator | 需要真实 trace/训练模型 |
| Innovation 2 | Partial | simulator | 需要更多消融 |
| Joint Controller | Partial | `AuraKVPolicy` | 缺事务和后台执行器 |
| Evaluation | Partial | simulated report | 缺真实 NVMe-oF/GPU |
