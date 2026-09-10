# TokenFS Token Workload 报告

实验命名空间：`real-AURA-Joint-1789008737-51739`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。

| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-cross-gpu | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.116928 | 68.42 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.141008 | 56.73 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.142865 | 56.00 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.145467 | 55.00 |  |
| read | cold-local-read | 0 | 0 | 8.00 | 0.793152 | 10.09 |  |
| write | capacity-pressure-append-existing | 0 | 0 | 8.00 | 0.144707 | 55.28 | append existing local cache to force eviction |
| read | remote-hot-first-read | 0 | 0 | 8.00 | 0.210449 | 38.01 |  |
| read | remote-hot-second-read-promote | 0 | 0 | 8.00 | 0.177626 | 45.04 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.158754 | 50.39 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.182733 | 43.78 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.132549 | 60.36 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128677 | 62.17 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.123889 | 64.57 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119470 | 66.96 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.121354 | 65.92 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119612 | 66.88 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.118727 | 67.38 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117223 | 68.25 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119796 | 66.78 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119882 | 66.73 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128865 | 62.08 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128976 | 62.03 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.129750 | 61.66 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128981 | 62.02 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.125773 | 63.61 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.120380 | 66.46 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.118645 | 67.43 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.118399 | 67.57 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119546 | 66.92 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.118890 | 67.29 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119586 | 66.90 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117221 | 68.25 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.122913 | 65.09 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117578 | 68.04 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.114963 | 69.59 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116894 | 68.44 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128168 | 62.42 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.121360 | 65.92 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119429 | 66.99 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.211056 | 37.90 |  |
| read | sequential-next-read-after-prefetch | 0 | 0 | 8.00 | 0.158506 | 50.47 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.129355 | 61.85 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.129026 | 62.00 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.126852 | 63.07 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.122912 | 65.09 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.122304 | 65.41 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.123055 | 65.01 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.133443 | 59.95 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.131692 | 60.75 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.133364 | 59.99 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.129345 | 61.85 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.128604 | 62.21 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.129454 | 61.80 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.128704 | 62.16 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.140312 | 57.02 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.130057 | 61.51 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.127890 | 62.55 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.130018 | 61.53 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.130411 | 61.34 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.128697 | 62.16 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.127544 | 62.72 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.124552 | 64.23 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.122540 | 65.28 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.121676 | 65.75 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.116247 | 68.82 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.177131 | 45.16 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.162162 | 49.33 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.130299 | 61.40 |  |
| read | cross-gpu-rehit-after-replica | 0 | 1 | 8.00 | 0.132052 | 60.58 |  |
