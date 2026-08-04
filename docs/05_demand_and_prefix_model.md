# 05. 需求估计与前缀有效需求

本文解释需求模型的直观含义。正式公式、变量表和数值案例集中在 [06_cost_model.md](06_cost_model.md)。

## 1. 为什么需要需求估计

缓存是否值得留在本地，取决于未来会不会被访问。系统不能知道未来，只能根据历史访问做在线统计估计。AURA-KV 默认使用：

- `GammaPoissonDemandEstimator`：带不确定性上下界的默认估计器；
- `EWMADemandEstimator`：指数衰减基线；
- `OracleDemandEstimator`：只在模拟器中使用未来 trace，不能用于真实系统。

这些都是在线统计估计器，不依赖训练集、模型文件或机器学习框架。

## 2. 创建和删除为什么用不同边界

创建副本会消耗本地空间和后台带宽，所以要保守：

```text
创建副本使用需求下界 N_lower
```

删除副本可能误删热点，所以也要保守：

```text
删除副本使用需求上界 N_upper
```

直观理解：

- 好处不要估太高；
- 坏处要估得更严重；
- 数据不足时少复制、少删除。

## 3. 前缀有效需求

公共前缀的价值不能只看后代数量。只有真实请求路径依赖该父前缀时，父前缀才获得有效需求。

实现规则：

1. 同一 `request_id` 对同一 cache key 最多计数一次。
2. 子缓存依赖父前缀时，父前缀获得一次有效需求。
3. 如果子缓存可以独立使用，不能虚构父级依赖。
4. 前缀需求分别输出 mean、lower、upper。

代码位置：

```text
aura_kv/demand.py
  EffectivePrefixDemandTracker
  GammaPoissonDemandEstimator
  EWMADemandEstimator
  OracleDemandEstimator
```

测试位置：

```text
tests/aura_kv_unit_test.py
  test_prefix_demand_deduplicates_request_id
  test_gamma_poisson_detects_node_demand_and_uncertainty_bounds
```

## 4. 与 GPU 亲和统计的关系

TokenFS C++ 主程序还维护工程层 GPU 访问统计：

```text
gpu_access
gpu_access_events
dominant_gpu_id
recent_dominant_gpu_id
affinity_state
```

这些统计用于真实 FUSE 原型中的跨 GPU 本地副本；AURA-KV Python 层使用 `AccessEvent.node_id` 和 `gpu_id` 做模拟。两者概念一致，但当前尚未完全接成同一套后台控制器。

