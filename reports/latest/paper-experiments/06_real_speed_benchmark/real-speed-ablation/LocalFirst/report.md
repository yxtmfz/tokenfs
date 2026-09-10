# TokenFS Token Workload 报告

实验命名空间：`real-LocalFirst-1789008699-51739`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。

| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-cross-gpu | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.119713 | 66.83 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.140144 | 57.08 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.141078 | 56.71 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.138194 | 57.89 |  |
| read | cold-local-read | 0 | 0 | 8.00 | 0.407099 | 19.65 |  |
| write | capacity-pressure-append-existing | 0 | 0 | 8.00 | 0.156271 | 51.19 | append existing local cache to force eviction |
| read | remote-hot-first-read | 0 | 0 | 8.00 | 0.178273 | 44.87 |  |
| read | remote-hot-second-read-promote | 0 | 0 | 8.00 | 0.119266 | 67.08 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.157224 | 50.88 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.114820 | 69.67 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117343 | 68.18 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116661 | 68.57 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115298 | 69.39 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115312 | 69.38 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.114791 | 69.69 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116724 | 68.54 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115823 | 69.07 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116259 | 68.81 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116514 | 68.66 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116248 | 68.82 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116172 | 68.86 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117783 | 67.92 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115366 | 69.34 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115340 | 69.36 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115712 | 69.14 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115310 | 69.38 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117881 | 67.87 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.112672 | 71.00 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116417 | 68.72 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116594 | 68.61 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116398 | 68.73 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115926 | 69.01 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116605 | 68.61 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116093 | 68.91 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116246 | 68.82 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115918 | 69.01 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115110 | 69.50 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117741 | 67.95 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.115546 | 69.24 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117063 | 68.34 |  |
| read | sequential-next-read-after-prefetch | 0 | 0 | 8.00 | 0.153480 | 52.12 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.117974 | 67.81 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.117808 | 67.91 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.171562 | 46.63 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.135587 | 59.00 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.121713 | 65.73 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.119788 | 66.78 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.117646 | 68.00 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.119276 | 67.07 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.189694 | 42.17 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.222774 | 35.91 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.117663 | 67.99 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.112561 | 71.07 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.115817 | 69.07 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.119100 | 67.17 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.128375 | 62.32 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.127688 | 62.65 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.134577 | 59.45 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.124265 | 64.38 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.116821 | 68.48 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.129702 | 61.68 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.145306 | 55.06 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.168379 | 47.51 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.159654 | 50.11 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.128875 | 62.08 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.127981 | 62.51 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.125199 | 63.90 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.121331 | 65.94 |  |
| read | cross-gpu-rehit-after-replica | 0 | 1 | 8.00 | 0.116457 | 68.69 |  |
