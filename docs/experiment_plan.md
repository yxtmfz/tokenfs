# AURA-KV 实验计划

## 当前可运行实验

运行：

```bash
python3 scripts/aura_kv_sim.py
```

输出：

```text
reports/latest/aura-kv-sim/aura_sim_report.md
reports/latest/aura-kv-sim/aura_sim_results.csv
reports/latest/aura-kv-sim/aura_sim_results.json
```

所有输出都会标注：

```text
SIMULATED RESULT
```

## 已实现 baseline

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

## 已实现场景

```text
private
node_shared
cluster_shared
hotspot_shift
high_recompute
remote_congestion
prediction_error
tenant_isolation
```

## 当前指标

```text
local_cache_hit_rate
remote_read_bytes
peer_read_bytes
recomputed_ms
duplicate_bytes
replica_count
replica_churn
migration_bytes
ttft_p50_ms
ttft_p95_ms
ttft_p99_ms
slo_violation_rate
decision_count
```

## 真实环境到位后

需要替换：

```text
remote_mount_path
NVMe-oF Target IP
NQN
设备名
真实本地 SSD 路径
真实节点/GPU 拓扑
真实 local/remote/peer 延迟采样
```

然后重新运行 FUSE workload 和 AURA-KV trace replay，不复用模拟结果作为真实硬件结论。

