# 13 测试与实验

本文说明当前能运行的测试、能证明什么，以及真实硬件到位后如何复测。

## 1. 测试分层

```text
Python 单元测试：验证 AURA-KV 模型和策略逻辑
FUSE 功能测试：验证 TokenFS 文件系统操作
策略专项测试：验证提升、预取、淘汰、副本生命周期
NVMe-oF 脚本测试：验证真实或双 VM NVMe/TCP 连接
模拟实验：对比不同 baseline 和场景
```

## 2. 推荐本地测试顺序

```bash
python3 -m unittest tests.aura_kv_unit_test
./scripts/aura_kv_test.sh
./scripts/smoke_test.sh
./scripts/integration_test.sh
./scripts/v2_integration_test.sh
./scripts/advanced_policy_test.sh
./scripts/eviction_test.sh
./scripts/promote_test.sh
./scripts/prefetch_test.sh
./scripts/consistency_test.sh
```

FUSE 脚本需要 Linux 环境和 FUSE 权限。macOS 主机上主要运行 Python 层测试。

## 3. 模拟实验

```bash
python3 scripts/aura_kv_sim.py --output reports/latest/aura-kv-sim
```

当前模拟器支持场景：

```text
private
node_shared
cluster_shared
hotspot_shift
high_recompute
remote_congestion
demand_estimation_error
tenant_isolation
```

当前策略或 baseline：

```text
RemoteOnly
ProducerLocal
NodeLRU
NodeLFU
SizeAwareLRU
WeightedScoreBaseline
EWMAReplacement
SourceAwareReplacement
PrefixSourceAwareReplacement
StaticNReplica
AffinityOnly
IndependentControllers
AURA-KV
OracleDemand
ExhaustiveOptimal
```

输出文件：

```text
reports/latest/aura-kv-sim/aura_sim_report.md
reports/latest/aura-kv-sim/aura_sim_results.csv
reports/latest/aura-kv-sim/aura_sim_results.json
```

模拟结果必须标注 `SIMULATED RESULT`。

## 4. 指标

| 指标 | 含义 |
|---|---|
| `local_cache_hit_rate` | 读取命中本地副本比例 |
| `remote_read_bytes` | 从远端读取的数据量 |
| `peer_read_bytes` | 从 peer 副本读取的数据量 |
| `recomputed_ms` | 重计算代价 |
| `duplicate_bytes` | 本地重复副本占用 |
| `replica_count` | 副本数量 |
| `replica_churn` | 副本创建/删除抖动 |
| `migration_bytes` | 后台迁移数据量 |
| `ttft_p50/p95/p99_ms` | 模拟 TTFT 分位数 |
| `slo_violation_rate` | 模拟 SLO 违反率 |

## 5. 当前能证明什么

当前目录模拟和 trace-driven simulator 能证明：

- 文件系统路径和元数据路径可运行。
- 策略公式能产生可解释的决策。
- 不同 baseline 可以在同一场景中对比。
- 本地淘汰、远端溢写、热点提升、预取和副本统计逻辑可观测。

当前不能证明：

- 真实 NVMe-oF 延迟和带宽。
- 真实 GPU 推理收益。
- 真实网络拥塞下的 P99。
- 多 GPU 真实并发读写上限。

## 6. 真实环境复测计划

拿到真实环境后需要补齐：

```text
SSD Target IP
NVMe/TCP 端口
Subsystem NQN
Host NQN / ACL
Namespace 是否独占
远端挂载点
GPU 服务器数量和 GPU 拓扑
```

推荐命令：

```bash
./scripts/check_environment.sh
sudo ./scripts/connect_nvme.sh --config config/tokenfs.dev.yaml --backend remote0 --chown-current
./scripts/nvmeof_two_vm_test.sh
./scripts/nvmeof_perf_test.sh
./scripts/strategy_matrix_test.sh
```

最终论文实验建议包含：

- 本地 SSD 直接读写。
- NVMe-oF 远端直接读写。
- TokenFS baseline。
- TokenFS + 代价驱动替换。
- TokenFS + 共享副本放置。
- AURA-KV full。

## 7. 结果入口

统一结果文件：

```text
reports/latest/final-report.md
```

以后新增结果优先更新这个文件，只有机器可读数据继续放在 `reports/latest/aura-kv-sim/`。
