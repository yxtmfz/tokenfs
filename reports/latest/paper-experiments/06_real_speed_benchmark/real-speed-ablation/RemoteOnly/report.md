# TokenFS Token Workload 报告

实验命名空间：`real-RemoteOnly-1789008686-51739`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。

| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-cross-gpu | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.136874 | 58.45 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.154943 | 51.63 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.156387 | 51.16 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.150728 | 53.08 |  |
| read | cold-local-read | 0 | 0 | 8.00 | 0.402244 | 19.89 |  |
| write | capacity-pressure-append-existing | 0 | 0 | 8.00 | 0.105710 | 75.68 | append existing local cache to force eviction |
| read | remote-hot-first-read | 0 | 0 | 8.00 | 0.253453 | 31.56 |  |
| read | remote-hot-second-read-promote | 0 | 0 | 8.00 | 0.132227 | 60.50 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.166570 | 48.03 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.125530 | 63.73 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.129776 | 61.64 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119901 | 66.72 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116442 | 68.70 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128181 | 62.41 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.143204 | 55.86 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.134164 | 59.63 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.131976 | 60.62 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.135765 | 58.93 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128547 | 62.23 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.135397 | 59.09 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.133331 | 60.00 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.137648 | 58.12 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.124517 | 64.25 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.127517 | 62.74 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.135217 | 59.16 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.120395 | 66.45 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.130486 | 61.31 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.178547 | 44.81 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.140209 | 57.06 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.133926 | 59.73 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128738 | 62.14 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.125017 | 63.99 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.129480 | 61.79 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.135509 | 59.04 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.136323 | 58.68 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.136216 | 58.73 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128274 | 62.37 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.126887 | 63.05 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.127831 | 62.58 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128143 | 62.43 |  |
| read | sequential-next-read-after-prefetch | 0 | 0 | 8.00 | 0.163529 | 48.92 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.124580 | 64.22 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.127445 | 62.77 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.122115 | 65.51 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.122515 | 65.30 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.120766 | 66.24 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.117619 | 68.02 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.118218 | 67.67 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.119471 | 66.96 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.118077 | 67.75 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.121363 | 65.92 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.119150 | 67.14 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.117422 | 68.13 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.118546 | 67.48 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.118690 | 67.40 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.115409 | 69.32 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.154954 | 51.63 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.166776 | 47.97 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.150245 | 53.25 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.151407 | 52.84 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.149236 | 53.61 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.131386 | 60.89 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.120901 | 66.17 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.117841 | 67.89 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.119102 | 67.17 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.128241 | 62.38 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.144034 | 55.54 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.253853 | 31.51 |  |
| read | cross-gpu-rehit-after-replica | 0 | 1 | 8.00 | 0.131731 | 60.73 |  |
