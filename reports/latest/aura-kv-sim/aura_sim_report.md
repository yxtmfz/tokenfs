# AURA-KV Trace Simulator Report

**SIMULATED RESULT**: 当前结果来自 trace-driven simulator，不代表真实 NVMe-oF 硬件性能。

| 场景 | 策略 | 本地命中率 | 远端读取 MiB | 重复副本 MiB | Churn | P99 ms | SLO 违约率 |
|---|---|---:|---:|---:|---:|---:|---:|
| private | RemoteOnly | 0.000 | 1440.0 | 0.0 | 0 | 8.881 | 0.000 |
| private | ProducerLocal | 1.000 | 0.0 | 48.0 | 4 | 0.129 | 0.000 |
| private | NodeLRU | 0.967 | 48.0 | 48.0 | 4 | 1.087 | 0.000 |
| private | NodeLFU | 0.967 | 48.0 | 48.0 | 4 | 1.087 | 0.000 |
| private | StaticNReplica | 1.000 | 0.0 | 96.0 | 8 | 0.129 | 0.000 |
| private | AffinityOnly | 0.933 | 96.0 | 48.0 | 4 | 1.206 | 0.000 |
| private | AIReplacementOnly | 0.967 | 48.0 | 48.0 | 4 | 1.087 | 0.000 |
| private | AlternativeAwareNoLearning | 1.000 | 0.0 | 48.0 | 4 | 0.129 | 0.000 |
| private | AURA-KV | 0.967 | 48.0 | 48.0 | 4 | 1.087 | 0.000 |
| node_shared | RemoteOnly | 0.000 | 2160.0 | 0.0 | 0 | 8.881 | 0.000 |
| node_shared | ProducerLocal | 1.000 | 0.0 | 36.0 | 2 | 0.129 | 0.000 |
| node_shared | NodeLRU | 0.983 | 36.0 | 36.0 | 2 | 0.841 | 0.000 |
| node_shared | NodeLFU | 0.983 | 36.0 | 36.0 | 2 | 0.841 | 0.000 |
| node_shared | StaticNReplica | 1.000 | 0.0 | 72.0 | 4 | 0.129 | 0.000 |
| node_shared | AffinityOnly | 0.967 | 72.0 | 36.0 | 2 | 1.087 | 0.000 |
| node_shared | AIReplacementOnly | 0.983 | 36.0 | 36.0 | 2 | 0.841 | 0.000 |
| node_shared | AlternativeAwareNoLearning | 1.000 | 0.0 | 36.0 | 2 | 0.129 | 0.000 |
| node_shared | AURA-KV | 1.000 | 0.0 | 36.0 | 2 | 0.129 | 0.000 |
| cluster_shared | RemoteOnly | 0.000 | 3840.0 | 0.0 | 0 | 8.881 | 0.000 |
| cluster_shared | ProducerLocal | 0.500 | 1920.0 | 24.0 | 1 | 7.855 | 0.006 |
| cluster_shared | NodeLRU | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| cluster_shared | NodeLFU | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| cluster_shared | StaticNReplica | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| cluster_shared | AffinityOnly | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| cluster_shared | AIReplacementOnly | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| cluster_shared | AlternativeAwareNoLearning | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| cluster_shared | AURA-KV | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| hotspot_shift | RemoteOnly | 0.000 | 3840.0 | 0.0 | 0 | 8.881 | 0.000 |
| hotspot_shift | ProducerLocal | 0.500 | 1920.0 | 24.0 | 1 | 8.838 | 0.000 |
| hotspot_shift | NodeLRU | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| hotspot_shift | NodeLFU | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| hotspot_shift | StaticNReplica | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| hotspot_shift | AffinityOnly | 0.581 | 1608.0 | 48.0 | 2 | 7.417 | 0.000 |
| hotspot_shift | AIReplacementOnly | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| hotspot_shift | AlternativeAwareNoLearning | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| hotspot_shift | AURA-KV | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| high_recompute | RemoteOnly | 0.000 | 3840.0 | 0.0 | 0 | 8.881 | 0.000 |
| high_recompute | ProducerLocal | 0.500 | 1920.0 | 64.0 | 2 | 7.855 | 0.000 |
| high_recompute | NodeLRU | 0.967 | 128.0 | 128.0 | 4 | 1.087 | 0.000 |
| high_recompute | NodeLFU | 0.967 | 128.0 | 128.0 | 4 | 1.087 | 0.000 |
| high_recompute | StaticNReplica | 1.000 | 0.0 | 128.0 | 4 | 0.129 | 0.000 |
| high_recompute | AffinityOnly | 0.967 | 128.0 | 128.0 | 4 | 1.087 | 0.000 |
| high_recompute | AIReplacementOnly | 0.967 | 128.0 | 128.0 | 4 | 1.087 | 0.000 |
| high_recompute | AlternativeAwareNoLearning | 0.500 | 0.0 | 64.0 | 2 | 3.948 | 0.000 |
| high_recompute | AURA-KV | 0.950 | 192.0 | 128.0 | 4 | 1.087 | 0.000 |
| remote_congestion | RemoteOnly | 0.000 | 3600.0 | 0.0 | 0 | 22.202 | 0.067 |
| remote_congestion | ProducerLocal | 0.500 | 1800.0 | 24.0 | 1 | 24.507 | 0.027 |
| remote_congestion | NodeLRU | 0.987 | 48.0 | 48.0 | 2 | 0.841 | 0.000 |
| remote_congestion | NodeLFU | 0.987 | 48.0 | 48.0 | 2 | 0.841 | 0.000 |
| remote_congestion | StaticNReplica | 1.000 | 0.0 | 48.0 | 2 | 0.130 | 0.000 |
| remote_congestion | AffinityOnly | 0.987 | 48.0 | 48.0 | 2 | 0.841 | 0.000 |
| remote_congestion | AIReplacementOnly | 0.987 | 48.0 | 48.0 | 2 | 0.841 | 0.000 |
| remote_congestion | AlternativeAwareNoLearning | 1.000 | 0.0 | 48.0 | 2 | 0.130 | 0.000 |
| remote_congestion | AURA-KV | 1.000 | 0.0 | 48.0 | 2 | 0.130 | 0.000 |
| prediction_error | RemoteOnly | 0.000 | 3000.0 | 0.0 | 0 | 8.881 | 0.000 |
| prediction_error | ProducerLocal | 0.607 | 1180.0 | 20.0 | 1 | 9.067 | 0.007 |
| prediction_error | NodeLRU | 0.987 | 40.0 | 40.0 | 2 | 0.841 | 0.000 |
| prediction_error | NodeLFU | 0.987 | 40.0 | 40.0 | 2 | 0.841 | 0.000 |
| prediction_error | StaticNReplica | 1.000 | 0.0 | 40.0 | 2 | 0.130 | 0.000 |
| prediction_error | AffinityOnly | 0.600 | 1200.0 | 20.0 | 1 | 1.614 | 0.007 |
| prediction_error | AIReplacementOnly | 0.987 | 40.0 | 40.0 | 2 | 0.841 | 0.000 |
| prediction_error | AlternativeAwareNoLearning | 1.000 | 0.0 | 40.0 | 2 | 0.130 | 0.000 |
| prediction_error | AURA-KV | 1.000 | 0.0 | 40.0 | 2 | 0.130 | 0.000 |
| tenant_isolation | RemoteOnly | 0.000 | 1920.0 | 0.0 | 0 | 8.881 | 0.000 |
| tenant_isolation | ProducerLocal | 1.000 | 0.0 | 32.0 | 2 | 0.129 | 0.000 |
| tenant_isolation | NodeLRU | 0.983 | 32.0 | 32.0 | 2 | 0.841 | 0.000 |
| tenant_isolation | NodeLFU | 0.983 | 32.0 | 32.0 | 2 | 0.841 | 0.000 |
| tenant_isolation | StaticNReplica | 1.000 | 0.0 | 64.0 | 4 | 0.129 | 0.000 |
| tenant_isolation | AffinityOnly | 0.967 | 64.0 | 32.0 | 2 | 1.087 | 0.000 |
| tenant_isolation | AIReplacementOnly | 0.983 | 32.0 | 32.0 | 2 | 0.841 | 0.000 |
| tenant_isolation | AlternativeAwareNoLearning | 1.000 | 0.0 | 32.0 | 2 | 0.129 | 0.000 |
| tenant_isolation | AURA-KV | 1.000 | 0.0 | 32.0 | 2 | 0.129 | 0.000 |

## AURA-KV 汇总

- 平均本地命中率: 0.990
- 平均 P99: 0.369 ms
- 平均重复副本空间: 53.5 MiB

这些数字用于检查策略是否按预期运作，真实论文结果仍需在导师提供的 NVMe-oF/GPU 环境中重新采集。
