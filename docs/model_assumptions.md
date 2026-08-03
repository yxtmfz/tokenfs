# AURA-KV 模型假设

本文列出当前代价驱动方案成立时需要的系统假设。它们不是实验结论，而是算法设计边界。

## 1. 数据对象假设

KV Cache 被抽象成不可变缓存对象。写入完成后，远端权威副本或可重算路径至少存在一个。若对象仍在写入、校验失败、版本不一致或 checksum 未通过，则不能作为 READY 来源。

## 2. 共享安全假设

只有 `CacheIdentity.share_safe_key` 完全一致时才允许共享。该键包含 sharing_domain、tenant、model、tokenizer、LoRA、KV dtype、位置编码、并行配置和 schema version。不同租户或 sharing_domain 的对象即使 token 前缀相同，也不能互相作为来源。

## 3. 访问需求假设

短时间窗口内访问到达率可以用在线统计估计近似。Gamma-Poisson 和 EWMA 都不需要训练数据，不依赖机器学习框架。OracleDemand 只在模拟器里使用未来 trace，用作上界参考。

## 4. 代价测量假设

来源代价可拆成固定延迟、排队、传输、反序列化、格式转换和 Host 到 GPU 传输。当前没有真实 NVMe-oF 环境时，远端延迟和带宽来自配置或模拟器；真实 IP/NQN 到位后应由 fio、Token workload 和系统 metrics 重新采集。

## 5. 控制器假设

前台读取不等待后台复制。控制器只决定后续布局，不阻塞正在进行的请求。后台动作必须经过容量、重复预算、带宽、并发、SLO、pin、READY 状态和唯一可靠来源检查。

## 6. 实验假设

当前 simulator 结果必须标记 `SIMULATED RESULT`。它可验证公式方向、性质和 baseline 框架，但不能代表真实 NVMe-oF 或真实 GPU 集群性能。
