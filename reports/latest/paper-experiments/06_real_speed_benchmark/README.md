# 真实 TokenFS 速度实验

该目录只保留论文级真实速度实验的说明，不再保留旧的 `baseline/promote/prefetch/full` 功能开关结果。

真实速度实验必须在 Linux/FUSE 环境运行，并要求远端后端已经通过 NVMe-oF 直连挂载：

```bash
TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/real_speed_benchmark.sh
```

脚本会按论文消融分类执行：

| 策略 | 含义 |
|---|---|
| `RemoteOnly` | 全部从远端容量层读取 |
| `LocalFirst` | 本地优先，本地不足时溢写远端，不主动淘汰 |
| `LRU-Local` | 本地不足时淘汰最久未访问数据 |
| `LFU-Local` | 本地不足时淘汰访问次数最少数据 |
| `AURA-Joint` | 价值感知、GPU 亲和、容量约束和后台动作联合决策 |

生成后主要看：

| 文件 | 作用 |
|---|---|
| `real_speed_summary.csv` | 真实 wall-clock 时间、吞吐、平均读写延迟和动作计数 |
| `real_speed_report.md` | 中文解释报告 |
| `figures/` | 真实总耗时、加速比、有效吞吐柱状图 |
| `nvmeof_mount_evidence.txt` | NVMe-oF 挂载证据 |

默认情况下，如果 `nvme_target_ip` 是 `127.0.0.1` 或 `localhost`，脚本会停止，因为这代表数据路径经过 SSH tunnel 或端口转发。隧道模式只适合功能验证，不适合作为直连 NVMe-oF 性能写入论文。
