# 01. 项目总览

AURA-KV / TokenFS 是一个面向多 GPU 大模型推理缓存的分层存储原型。它把计算节点本地 SSD 作为低延迟缓存层，把 NVMe-oF 远端 SSD 作为大容量权威层，通过 FUSE 暴露统一文件命名空间，并通过 AURA-KV 策略层研究缓存替换和共享副本放置。

当前项目由两部分组成：

| 部分 | 作用 | 当前状态 |
|---|---|---|
| TokenFS | 可挂载 FUSE 文件系统，管理本地目录、远端目录、SQLite 元数据、GPU 访问统计和跨 GPU 本地副本 | Implemented/Partial |
| AURA-KV | Python 研究层，包含需求估计、来源代价、布局收益、baseline 和 trace-driven simulator | Implemented/Partial |

## 1. 项目不是做什么

它不是从零实现一个新的块文件系统，不替代 ext4/XFS，不直接管理 SSD LBA，也不直接改 vLLM 或 SGLang 内部显存 KV Cache。当前重点是显存外 KV Cache、Prompt Token 和 Token Shard 在本地 SSD 与远端 NVMe-oF SSD 之间如何放置。

## 2. 关键思路

本地 SSD 速度快但容量有限，远端 NVMe-oF SSD 容量大但有网络开销。因此系统要持续回答三个问题：

```text
本地空间不够时，删哪个副本最不亏？
某个远端缓存变热时，要不要复制到某个节点本地？
一次删除、复制或替换动作会不会整体改善未来服务代价？
```

正式模型统一使用毫秒作为代价单位。容量、重复副本空间、后台带宽、租户隔离、唯一可靠副本和前台 SLO 都作为硬约束，不混进人工权重总分。

## 3. 两个研究方向

1. 替代来源与前缀有效需求感知的代价驱动型 KV Cache 替换策略。核心是 `EvictionLoss`，用于判断删除某个本地副本后未来会多付出多少访问代价。
2. 动态共享拓扑感知的预算化 KV Cache 副本放置。核心是 `ReplicaGain`，用于判断新增一个本地副本后未来能节省多少访问代价。

二者由联合控制器统一处理，避免一个模块刚删除副本，另一个模块又复制回来。

## 4. 当前可运行能力

- FUSE 文件系统原型可构建、挂载和读写。
- 开发环境远端层可以用普通目录模拟。
- TokenFS 能记录 SQLite 元数据、checksum、指标、GPU 访问统计和本地副本。
- AURA-KV simulator 能跑 8 个场景和 15 个策略/baseline。
- 真实 NVMe-oF 已有连接脚本和 dry-run，但真实性能需要实验室提供 IP、NQN 和设备。

完整状态见 [14_implementation_status.md](14_implementation_status.md)。

