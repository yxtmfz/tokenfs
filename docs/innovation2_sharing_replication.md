# 候选创新二：动态共享拓扑感知的预算化 KV Cache 副本放置

暂定英文名：

```text
Dynamic Sharing-Topology-Aware Budgeted Replication
```

这个方向不再简单称为“GPU 亲和力”。GPU 只是访问来源之一，真正要研究的是：

```text
缓存对象和计算节点之间的动态共享拓扑
```

## 为什么有必要

如果每个 GPU 的任务完全不同，就不需要额外共享副本机制。此时谁产生谁管理，系统应退化成私有本地缓存管理。

但老师提到的前缀共享和 KV Cache 共享是存在的。例如多个请求复用：

```text
系统提示词
知识库前缀
Agent 模板
长文档前缀
```

这些共享数据不应该简单按“生产者 GPU”固定在某个本地 SSD，也不应该无脑复制到所有 GPU。本研究点要解决的是：在共享真的出现时，有限地、预算化地创建本地副本。

## 当前实现逻辑

AURA-KV 建立简化访问图：

```text
CacheObjects <-> ComputeNodes
```

每个缓存根据访问分布分类为：

```text
PROVISIONAL_PRIVATE
GPU_PRIVATE
NODE_SHARED
CLUSTER_SHARED
FORCED_PRIVATE
```

分类指标包括：

```text
最小访问样本数
主导节点比例 dominance
标准化共享熵 sharedness_entropy
跨节点访问次数
sharing_domain 是否允许共享
```

副本创建不是固定 N 份，而是看：

```text
预测访问收益
替代来源代价
重计算代价
本地容量价格
全局重复副本价格
节点重复副本预算
churn 惩罚
```

## 关键约束

同一计算节点上的多个 GPU 如果共享同一块本地 SSD，只保存一份节点级副本，不为 GPU0/GPU1 重复保存同一物理文件。

不同 sharing_domain 的缓存，即使内容类似，也禁止共享。

