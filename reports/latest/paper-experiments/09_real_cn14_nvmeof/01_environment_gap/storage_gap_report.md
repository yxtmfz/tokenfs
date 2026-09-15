# NVMe-oF 本地/远端环境差距诊断

- 配置文件：`/home/wjxt/projects/tokenfs/config/tokenfs.cn14.yaml`
- 本地目录：`/home/wjxt/aura-kv/local/gpu0`
- 远端目录：`/srv/tokenfs/remote0`
- 远端挂载证据：`/dev/nvme3n1 ext4 /srv/tokenfs/remote0`
- 测试数据量：`1024 MiB`

| 层级 | 写吞吐 MiB/s | 读吞吐 MiB/s |
|---|---:|---:|
| local | 149.37 | 164.27 |
| remote | 78.65 | 110.45 |

- 本地/远端读吞吐比：`1.487x`
- 本地/远端写吞吐比：`1.899x`

结论：当前环境已经存在可观的本地/远端读性能差距，AURA 的本地缓存、预取和跨 GPU 副本策略有条件转化为端到端速度收益。
