# AURA-KV 研究问题定义

## 1. 本文解决的问题

本文回答：AURA-KV 到底研究什么、不研究什么、如何评价它是否有效。它不是论文结果，而是后续开题、实验设计和实现工作的统一问题定义。

## 2. 现实背景

大模型推理服务越来越依赖长上下文、系统提示词、工具调用模板、知识库前缀和多轮 Agent 历史。KV Cache 可以避免重复 prefill，但它会占用大量存储。单靠 GPU 显存保存不现实，单靠远端 SSD 又会带来延迟和网络长尾，因此需要本地 SSD 和远端 NVMe-oF SSD 的分层管理。

## 3. 现有方案为什么不够

```text
RemoteOnly: 容量大但 P99 容易受远端长尾影响
ProducerLocal: 跨节点共享时其他节点仍频繁访问远端
NodeLRU/NodeLFU: 不理解重算成本、前缀依赖和替代来源
StaticNReplica: 固定 N 份无法适应共享强度和容量压力
AffinityOnly: 只知道谁访问多，不知道是否值得复制
AIReplacementOnly: 预测冷热但不知道删掉后从哪里恢复
```

## 4. 两个候选创新各自负责什么

候选创新一负责本地容量紧张时的多动作替换：保留、提升、降级、删除、预取或 pin。它重点看缓存价值、重算代价、前缀依赖和替代来源。

候选创新二负责共享缓存的副本放置：先判断是否能共享，再看访问图和预算，决定在哪些计算节点建立本地副本。

二者必须联合，因为“删除一个副本”会改变创新点二看到的全局副本图，“创建一个副本”也会改变创新点一看到的本地容量压力。

## 5. 系统假设

```text
KV Cache、Prompt Token 或 Token Shard 可抽象为不可变对象
远端 SSD 保存权威副本或可恢复副本
本地 SSD 保存热点加速副本
访问事件能够记录 node_id、gpu_id、cache_key 和字节数
不同 sharing_domain 不能共享
没有真实 NVMe-oF 时可使用模拟后端验证算法流程
```

## 6. 非目标

```text
不从零实现完整底层块文件系统
不直接修改 GPU 显存管理
不声称替代 vLLM/SGLang 内部 KV Cache
不在无真实环境时给出硬件性能结论
不声称全球首次
```

## 7. 正式问题定义

给定缓存对象集合 K、计算节点集合 N、访问请求流 R、每个节点本地容量 Cn、全局重复预算 D 和前台 P99 SLO，系统在线选择动作：

```text
KEEP / PROMOTE / REPLICATE / DEMOTE / EVICT_LOCAL / DROP_RECOMPUTABLE / PIN / PREFETCH
```

目标是在满足容量、预算、隔离和安全约束下，减少：

```text
前台 P99/TTFT
远端读取字节
重算开销
重复空间
后台干扰
副本 churn
```

## 8. 评价指标

```text
local_cache_hit_rate
remote_read_bytes
recomputed_ms
duplicate_bytes
replica_count
replica_churn
migration_bytes
ttft_p50_ms / ttft_p95_ms / ttft_p99_ms
slo_violation_rate
decision_count
```

效率指标：

```text
Cache Benefit Density = latency_saved_ms / time_averaged_local_cache_bytes
Replication Efficiency = avoided_remote_read_bytes / duplicate_bytes
Recompute Saving Density = avoided_recompute_ms / local_cache_bytes
```

## 9. 拟研究贡献

谨慎表述为：

```text
候选贡献一：替代来源与前缀结构感知的多动作替换
候选贡献二：动态共享拓扑感知的预算化副本放置
候选贡献三：二者的联合在线控制和可复现实验框架
```

这些贡献是否足够新颖，必须通过论文、专利和开源系统检索验证。

## 10. 实验验证关系

当前 simulator 已支持 8 个场景和 9 个 baseline，能验证机制是否运行。真实论文结果必须在导师提供真实 IP、NQN、GPU 拓扑和 NVMe-oF Target 后重新采集。

## 11. 实现状态

| 功能 | 状态 | 对应代码 | 对应测试 | 未完成原因 | 后续计划 |
|---|---|---|---|---|---|
| 问题抽象 | Implemented | `aura_kv/core.py` | unit/sim | 无 | 与真实 trace 对齐 |
| 9 个 baseline | Implemented | `aura_kv/simulator.py`, `aura_kv/policies.py` | `scripts/aura_kv_test.sh` | 无 | 增加 ablation |
| 8 个场景 | Implemented | `generate_trace()` | simulator | 无 | 增加崩溃恢复 trace |
| 真实 TTFT 指标 | Planned | 无 | 无 | 缺真实推理环境 | 接入 vLLM/SGLang |
