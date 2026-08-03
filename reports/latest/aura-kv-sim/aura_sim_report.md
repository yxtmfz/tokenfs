# AURA-KV Trace Simulator Report

**SIMULATED RESULT**: 当前结果来自 trace-driven simulator，不代表真实 NVMe-oF 硬件性能。

| 场景 | 策略 | 本地命中率 | 远端读取 MiB | 重复副本 MiB | Churn | P99 ms | SLO 违约率 |
|---|---|---:|---:|---:|---:|---:|---:|
| private | RemoteOnly | 0.000 | 1440.0 | 0.0 | 0 | 8.881 | 0.000 |
| private | ProducerLocal | 1.000 | 0.0 | 48.0 | 4 | 0.129 | 0.000 |
| private | NodeLRU | 0.967 | 48.0 | 48.0 | 4 | 1.087 | 0.000 |
| private | NodeLFU | 0.967 | 48.0 | 48.0 | 4 | 1.087 | 0.000 |
| private | SizeAwareLRU | 0.967 | 48.0 | 48.0 | 4 | 1.087 | 0.000 |
| private | WeightedScoreBaseline | 1.000 | 0.0 | 48.0 | 4 | 0.129 | 0.000 |
| private | EWMAReplacement | 0.833 | 240.0 | 48.0 | 4 | 1.576 | 0.000 |
| private | SourceAwareReplacement | 1.000 | 0.0 | 48.0 | 4 | 0.129 | 0.000 |
| private | PrefixSourceAwareReplacement | 1.000 | 0.0 | 48.0 | 4 | 0.129 | 0.000 |
| private | StaticNReplica | 1.000 | 0.0 | 96.0 | 8 | 0.129 | 0.000 |
| private | AffinityOnly | 0.933 | 96.0 | 48.0 | 4 | 1.206 | 0.000 |
| private | IndependentControllers | 0.900 | 144.0 | 48.0 | 4 | 1.576 | 0.000 |
| private | AURA-KV | 0.000 | 0.0 | 0.0 | 0 | 8.000 | 0.000 |
| private | OracleDemand | 1.000 | 0.0 | 48.0 | 4 | 0.129 | 0.000 |
| private | ExhaustiveOptimal | 1.000 | 0.0 | 48.0 | 4 | 0.129 | 0.000 |
| node_shared | RemoteOnly | 0.000 | 2160.0 | 0.0 | 0 | 8.881 | 0.000 |
| node_shared | ProducerLocal | 1.000 | 0.0 | 36.0 | 2 | 0.129 | 0.000 |
| node_shared | NodeLRU | 0.983 | 36.0 | 36.0 | 2 | 0.841 | 0.000 |
| node_shared | NodeLFU | 0.983 | 36.0 | 36.0 | 2 | 0.841 | 0.000 |
| node_shared | SizeAwareLRU | 0.983 | 36.0 | 36.0 | 2 | 0.841 | 0.000 |
| node_shared | WeightedScoreBaseline | 1.000 | 0.0 | 36.0 | 2 | 0.129 | 0.000 |
| node_shared | EWMAReplacement | 0.917 | 180.0 | 36.0 | 2 | 1.475 | 0.000 |
| node_shared | SourceAwareReplacement | 1.000 | 0.0 | 36.0 | 2 | 0.129 | 0.000 |
| node_shared | PrefixSourceAwareReplacement | 1.000 | 0.0 | 36.0 | 2 | 0.129 | 0.000 |
| node_shared | StaticNReplica | 1.000 | 0.0 | 72.0 | 4 | 0.129 | 0.000 |
| node_shared | AffinityOnly | 0.967 | 72.0 | 36.0 | 2 | 1.087 | 0.000 |
| node_shared | IndependentControllers | 0.950 | 108.0 | 36.0 | 2 | 1.144 | 0.000 |
| node_shared | AURA-KV | 0.700 | 648.0 | 36.0 | 2 | 5.461 | 0.000 |
| node_shared | OracleDemand | 1.000 | 0.0 | 36.0 | 2 | 0.129 | 0.000 |
| node_shared | ExhaustiveOptimal | 1.000 | 0.0 | 36.0 | 2 | 0.129 | 0.000 |
| cluster_shared | RemoteOnly | 0.000 | 3840.0 | 0.0 | 0 | 8.881 | 0.000 |
| cluster_shared | ProducerLocal | 0.500 | 1920.0 | 24.0 | 1 | 7.855 | 0.006 |
| cluster_shared | NodeLRU | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| cluster_shared | NodeLFU | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| cluster_shared | SizeAwareLRU | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| cluster_shared | WeightedScoreBaseline | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| cluster_shared | EWMAReplacement | 0.938 | 240.0 | 48.0 | 2 | 1.206 | 0.000 |
| cluster_shared | SourceAwareReplacement | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| cluster_shared | PrefixSourceAwareReplacement | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| cluster_shared | StaticNReplica | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| cluster_shared | AffinityOnly | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| cluster_shared | IndependentControllers | 0.975 | 96.0 | 48.0 | 2 | 0.907 | 0.000 |
| cluster_shared | AURA-KV | 0.775 | 864.0 | 48.0 | 2 | 1.576 | 0.000 |
| cluster_shared | OracleDemand | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| cluster_shared | ExhaustiveOptimal | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| hotspot_shift | RemoteOnly | 0.000 | 3840.0 | 0.0 | 0 | 8.881 | 0.000 |
| hotspot_shift | ProducerLocal | 0.500 | 1920.0 | 24.0 | 1 | 8.838 | 0.000 |
| hotspot_shift | NodeLRU | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| hotspot_shift | NodeLFU | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| hotspot_shift | SizeAwareLRU | 0.988 | 48.0 | 48.0 | 2 | 0.130 | 0.000 |
| hotspot_shift | WeightedScoreBaseline | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| hotspot_shift | EWMAReplacement | 0.938 | 240.0 | 48.0 | 2 | 1.206 | 0.000 |
| hotspot_shift | SourceAwareReplacement | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| hotspot_shift | PrefixSourceAwareReplacement | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| hotspot_shift | StaticNReplica | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| hotspot_shift | AffinityOnly | 0.581 | 1608.0 | 48.0 | 2 | 7.417 | 0.000 |
| hotspot_shift | IndependentControllers | 0.950 | 192.0 | 48.0 | 2 | 1.108 | 0.000 |
| hotspot_shift | AURA-KV | 0.769 | 888.0 | 48.0 | 2 | 5.461 | 0.000 |
| hotspot_shift | OracleDemand | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| hotspot_shift | ExhaustiveOptimal | 1.000 | 0.0 | 48.0 | 2 | 0.129 | 0.000 |
| high_recompute | RemoteOnly | 0.000 | 3840.0 | 0.0 | 0 | 8.881 | 0.000 |
| high_recompute | ProducerLocal | 0.500 | 1920.0 | 64.0 | 2 | 7.855 | 0.000 |
| high_recompute | NodeLRU | 0.967 | 128.0 | 128.0 | 4 | 1.087 | 0.000 |
| high_recompute | NodeLFU | 0.967 | 128.0 | 128.0 | 4 | 1.087 | 0.000 |
| high_recompute | SizeAwareLRU | 0.967 | 128.0 | 128.0 | 4 | 1.087 | 0.000 |
| high_recompute | WeightedScoreBaseline | 1.000 | 0.0 | 128.0 | 4 | 0.129 | 0.000 |
| high_recompute | EWMAReplacement | 0.833 | 640.0 | 128.0 | 4 | 1.576 | 0.000 |
| high_recompute | SourceAwareReplacement | 0.500 | 0.0 | 64.0 | 2 | 3.948 | 0.000 |
| high_recompute | PrefixSourceAwareReplacement | 0.500 | 0.0 | 64.0 | 2 | 3.948 | 0.000 |
| high_recompute | StaticNReplica | 1.000 | 0.0 | 128.0 | 4 | 0.129 | 0.000 |
| high_recompute | AffinityOnly | 0.967 | 128.0 | 128.0 | 4 | 1.087 | 0.000 |
| high_recompute | IndependentControllers | 0.933 | 256.0 | 128.0 | 4 | 1.475 | 0.000 |
| high_recompute | AURA-KV | 0.367 | 1152.0 | 64.0 | 2 | 8.000 | 0.000 |
| high_recompute | OracleDemand | 1.000 | 0.0 | 128.0 | 4 | 0.129 | 0.000 |
| high_recompute | ExhaustiveOptimal | 1.000 | 0.0 | 128.0 | 4 | 0.129 | 0.000 |
| remote_congestion | RemoteOnly | 0.000 | 3600.0 | 0.0 | 0 | 22.202 | 0.067 |
| remote_congestion | ProducerLocal | 0.500 | 1800.0 | 24.0 | 1 | 24.507 | 0.027 |
| remote_congestion | NodeLRU | 0.987 | 48.0 | 48.0 | 2 | 0.841 | 0.000 |
| remote_congestion | NodeLFU | 0.987 | 48.0 | 48.0 | 2 | 0.841 | 0.000 |
| remote_congestion | SizeAwareLRU | 0.987 | 48.0 | 48.0 | 2 | 0.841 | 0.000 |
| remote_congestion | WeightedScoreBaseline | 1.000 | 0.0 | 48.0 | 2 | 0.130 | 0.000 |
| remote_congestion | EWMAReplacement | 0.933 | 240.0 | 48.0 | 2 | 1.475 | 0.000 |
| remote_congestion | SourceAwareReplacement | 1.000 | 0.0 | 48.0 | 2 | 0.130 | 0.000 |
| remote_congestion | PrefixSourceAwareReplacement | 1.000 | 0.0 | 48.0 | 2 | 0.130 | 0.000 |
| remote_congestion | StaticNReplica | 1.000 | 0.0 | 48.0 | 2 | 0.130 | 0.000 |
| remote_congestion | AffinityOnly | 0.987 | 48.0 | 48.0 | 2 | 0.841 | 0.000 |
| remote_congestion | IndependentControllers | 0.973 | 96.0 | 48.0 | 2 | 1.087 | 0.000 |
| remote_congestion | AURA-KV | 0.000 | 3600.0 | 0.0 | 0 | 22.202 | 0.067 |
| remote_congestion | OracleDemand | 1.000 | 0.0 | 48.0 | 2 | 0.130 | 0.000 |
| remote_congestion | ExhaustiveOptimal | 1.000 | 0.0 | 48.0 | 2 | 0.130 | 0.000 |
| demand_estimation_error | RemoteOnly | 0.000 | 3000.0 | 0.0 | 0 | 8.881 | 0.000 |
| demand_estimation_error | ProducerLocal | 0.607 | 1180.0 | 20.0 | 1 | 9.067 | 0.007 |
| demand_estimation_error | NodeLRU | 0.987 | 40.0 | 40.0 | 2 | 0.841 | 0.000 |
| demand_estimation_error | NodeLFU | 0.987 | 40.0 | 40.0 | 2 | 0.841 | 0.000 |
| demand_estimation_error | SizeAwareLRU | 0.987 | 40.0 | 40.0 | 2 | 0.841 | 0.000 |
| demand_estimation_error | WeightedScoreBaseline | 1.000 | 0.0 | 40.0 | 2 | 0.130 | 0.000 |
| demand_estimation_error | EWMAReplacement | 0.933 | 200.0 | 40.0 | 2 | 1.466 | 0.000 |
| demand_estimation_error | SourceAwareReplacement | 1.000 | 0.0 | 40.0 | 2 | 0.130 | 0.000 |
| demand_estimation_error | PrefixSourceAwareReplacement | 1.000 | 0.0 | 40.0 | 2 | 0.130 | 0.000 |
| demand_estimation_error | StaticNReplica | 1.000 | 0.0 | 40.0 | 2 | 0.130 | 0.000 |
| demand_estimation_error | AffinityOnly | 0.600 | 1200.0 | 20.0 | 1 | 1.614 | 0.007 |
| demand_estimation_error | IndependentControllers | 0.953 | 140.0 | 40.0 | 2 | 1.523 | 0.000 |
| demand_estimation_error | AURA-KV | 0.753 | 740.0 | 40.0 | 2 | 5.461 | 0.000 |
| demand_estimation_error | OracleDemand | 1.000 | 0.0 | 40.0 | 2 | 0.130 | 0.000 |
| demand_estimation_error | ExhaustiveOptimal | 1.000 | 0.0 | 40.0 | 2 | 0.130 | 0.000 |
| tenant_isolation | RemoteOnly | 0.000 | 1920.0 | 0.0 | 0 | 8.881 | 0.000 |
| tenant_isolation | ProducerLocal | 1.000 | 0.0 | 32.0 | 2 | 0.129 | 0.000 |
| tenant_isolation | NodeLRU | 0.983 | 32.0 | 32.0 | 2 | 0.841 | 0.000 |
| tenant_isolation | NodeLFU | 0.983 | 32.0 | 32.0 | 2 | 0.841 | 0.000 |
| tenant_isolation | SizeAwareLRU | 0.983 | 32.0 | 32.0 | 2 | 0.841 | 0.000 |
| tenant_isolation | WeightedScoreBaseline | 1.000 | 0.0 | 32.0 | 2 | 0.129 | 0.000 |
| tenant_isolation | EWMAReplacement | 0.917 | 160.0 | 32.0 | 2 | 1.475 | 0.000 |
| tenant_isolation | SourceAwareReplacement | 1.000 | 0.0 | 32.0 | 2 | 0.129 | 0.000 |
| tenant_isolation | PrefixSourceAwareReplacement | 1.000 | 0.0 | 32.0 | 2 | 0.129 | 0.000 |
| tenant_isolation | StaticNReplica | 1.000 | 0.0 | 64.0 | 4 | 0.129 | 0.000 |
| tenant_isolation | AffinityOnly | 0.967 | 64.0 | 32.0 | 2 | 1.087 | 0.000 |
| tenant_isolation | IndependentControllers | 0.950 | 96.0 | 32.0 | 2 | 1.144 | 0.000 |
| tenant_isolation | AURA-KV | 0.700 | 576.0 | 32.0 | 2 | 5.461 | 0.000 |
| tenant_isolation | OracleDemand | 1.000 | 0.0 | 32.0 | 2 | 0.129 | 0.000 |
| tenant_isolation | ExhaustiveOptimal | 1.000 | 0.0 | 32.0 | 2 | 0.129 | 0.000 |

## AURA-KV 汇总

- 平均本地命中率: 0.508
- 平均 P99: 7.703 ms
- 平均重复副本空间: 33.5 MiB

这些数字用于检查策略是否按预期运作，真实论文结果仍需在导师提供的 NVMe-oF/GPU 环境中重新采集。
