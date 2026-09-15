# NVMe-oF 本地/远端环境差距诊断

- 配置文件：`config/tokenfs.nvmeof.yaml`
- 本地目录：`/var/lib/tokenfs/local/gpu0`
- 远端目录：`/srv/tokenfs/remote0`
- 远端挂载证据：`/dev/nvme0n1 ext4 /srv/tokenfs/remote0`
- 测试数据量：`512 MiB`

| 层级 | 写吞吐 MiB/s | 读吞吐 MiB/s |
|---|---:|---:|
| local | 129.4 | 1259.06 |
| remote | 131.75 | 269.02 |

- 本地/远端读吞吐比：`4.680x`
- 本地/远端写吞吐比：`0.982x`

结论：当前环境已经存在可观的本地/远端读性能差距，AURA 的本地缓存、预取和跨 GPU 副本策略有条件转化为端到端速度收益。
