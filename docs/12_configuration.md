# 12 配置说明

本文说明当前仓库主要配置文件和脚本入口。

## 1. TokenFS 配置

文件：

```text
config/tokenfs.dev.yaml
```

主要区域：

| 区域 | 作用 |
|---|---|
| `filesystem` | 挂载点、SQLite 路径、日志、临时文件后缀 |
| `policy` | 本地水位、提升、预取、淘汰、亲和和 QoS 参数 |
| `gpus` | 每个 GPU 的逻辑根、本地目录和配额 |
| `backends` | 远端目录或 NVMe-oF 挂载后端 |

## 2. GPU 配额示例

```yaml
gpus:
  - gpu_id: 0
    logical_root: /gpu0
    local_root: /var/lib/tokenfs/local/gpu0
    local_quota_mib: 64
    remote_backend: remote0
```

含义：

```text
/mnt/tokenfs/gpu0 下的文件属于 GPU0 命名空间；
本地缓存目录是 /var/lib/tokenfs/local/gpu0；
本地逻辑配额是 64 MiB；
本地不足时使用 remote0。
```

## 3. 策略参数

常见参数：

| 参数 | 含义 |
|---|---|
| `local_high_watermark` | 超过高水位后触发淘汰 |
| `local_low_watermark` | 淘汰目标水位 |
| `promote_on_read` | 远端热点读后是否提升本地 |
| `prefetch_on_sequential_read` | 连续 shard 是否预取下一片 |
| `cross_gpu_local_cache` | 是否允许跨 GPU 本地缓存副本 |
| `affinity_short_window_seconds` | 短窗口热度统计 |
| `affinity_long_window_seconds` | 长窗口趋势统计 |
| `replica_cooldown_seconds` | 副本调整冷却时间 |
| `min_replica_residence_seconds` | 最短驻留时间 |

## 4. AURA-KV 配置

文件：

```text
config/aura_kv.example.yaml
```

用于 Python 模拟层，包含：

- 需求估计窗口。
- 本地、peer、远端、重计算代价。
- 共享分类阈值。
- 容量和副本预算。
- SLO、后台带宽和控制周期。
- 模拟器场景参数。

## 5. 常用脚本

| 脚本 | 作用 |
|---|---|
| `reset_dev_state.sh` | 重置开发目录和元数据 |
| `start_tokenfs.sh` | 启动 FUSE |
| `stop_tokenfs.sh` | 停止 FUSE |
| `smoke_test.sh` | 基础冒烟测试 |
| `integration_test.sh` | 集成测试 |
| `tokenfsctl.py` | 状态、文件、指标、亲和、副本、检查 |
| `aura_kv_test.sh` | AURA-KV 单元和模拟测试 |
| `aura_kv_sim.py` | 生成模拟实验结果 |

## 6. 查看状态

```bash
./scripts/tokenfsctl.py status
./scripts/tokenfsctl.py files
./scripts/tokenfsctl.py replicas
./scripts/tokenfsctl.py affinity
./scripts/tokenfsctl.py metrics
```

## 7. 当前状态

Implemented：

- 开发配置可直接运行目录模拟后端。
- NVMe-oF 字段已配置化。
- 管理工具可读取 SQLite 状态。

Partial：

- 配置热加载未实现。
- 多节点统一配置分发未实现。
