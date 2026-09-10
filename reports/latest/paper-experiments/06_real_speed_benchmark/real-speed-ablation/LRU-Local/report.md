# TokenFS Token Workload 报告

实验命名空间：`real-LRU-Local-1789008711-51739`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。

| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-cross-gpu | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.119859 | 66.75 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.138644 | 57.70 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.145522 | 54.97 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.173166 | 46.20 |  |
| read | cold-local-read | 0 | 0 | 8.00 | 0.559362 | 14.30 |  |
| write | capacity-pressure-append-existing | 0 | 0 | 8.00 | 0.143351 | 55.81 | append existing local cache to force eviction |
| read | remote-hot-first-read | 0 | 0 | 8.00 | 0.179156 | 44.65 |  |
| read | remote-hot-second-read-promote | 0 | 0 | 8.00 | 0.121299 | 65.95 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.178470 | 44.83 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.131486 | 60.84 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.136620 | 58.56 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.139240 | 57.45 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.143236 | 55.85 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.127944 | 62.53 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.125260 | 63.87 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.125256 | 63.87 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.120531 | 66.37 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116332 | 68.77 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.118908 | 67.28 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116986 | 68.38 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.121294 | 65.96 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.127733 | 62.63 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.123787 | 64.63 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.120170 | 66.57 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116010 | 68.96 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.118549 | 67.48 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117655 | 68.00 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116125 | 68.89 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117267 | 68.22 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.123618 | 64.72 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116878 | 68.45 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117102 | 68.32 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.116731 | 68.53 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119115 | 67.16 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119663 | 66.85 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119498 | 66.95 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.118419 | 67.56 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117003 | 68.37 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.220144 | 36.34 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.117989 | 67.80 |  |
| read | sequential-next-read-after-prefetch | 0 | 0 | 8.00 | 0.189625 | 42.19 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.130244 | 61.42 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.127004 | 62.99 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.121674 | 65.75 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.127508 | 62.74 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.125198 | 63.90 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.129469 | 61.79 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.128391 | 62.31 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.123540 | 64.76 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.116932 | 68.42 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.115970 | 68.98 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.119131 | 67.15 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.117842 | 67.89 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.118952 | 67.25 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.118733 | 67.38 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.126602 | 63.19 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.124519 | 64.25 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.124157 | 64.43 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.123222 | 64.92 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.124831 | 64.09 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.122887 | 65.10 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.119335 | 67.04 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.116034 | 68.95 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.121177 | 66.02 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.155466 | 51.46 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.126912 | 63.04 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.149469 | 53.52 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.116572 | 68.63 |  |
| read | cross-gpu-rehit-after-replica | 0 | 1 | 8.00 | 0.115833 | 69.07 |  |
