# TokenFS Token Workload 报告

实验命名空间：`real-LocalFirst-1789485679-999281`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。

| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| seed_remote | remote-canonical-hot | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-hot | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-cross-gpu | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.304019 | 49.08 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.716950 | 37.28 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.699742 | 37.65 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.705107 | 37.53 |  |
| cache_control | before-cold-local-read | -1 | -1 | 0.00 | 0.006602 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cold-local-read | 0 | 0 | 64.00 | 0.679089 | 94.24 |  |
| write | capacity-pressure-append-existing | 0 | 0 | 8.00 | 0.664282 | 12.04 | append existing local cache to force eviction |
| cache_control | before-remote-hot-first-read | -1 | -1 | 0.00 | 0.006236 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | remote-hot-first-read | 0 | 0 | 64.00 | 0.640540 | 99.92 |  |
| read | remote-hot-second-read-promote | 0 | 0 | 64.00 | 0.462801 | 138.29 |  |
| cache_control | before-hot-rehit-after-promote | -1 | -1 | 0.00 | 0.006197 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | hot-rehit-after-promote | 0 | 0 | 8192.00 | 32.054463 | 255.57 | batched 128 repeated reads in one loader process |
| cache_control | before-sequential-next-read-after-prefetch | -1 | -1 | 0.00 | 0.006508 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | sequential-next-read-after-prefetch | 0 | 0 | 64.00 | 0.111336 | 574.84 |  |
| cache_control | before-sequential-rehit-after-prefetch | -1 | -1 | 0.00 | 0.006121 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | sequential-rehit-after-prefetch | 0 | 0 | 4096.00 | 10.857861 | 377.24 | batched 64 repeated reads in one loader process |
| cache_control | before-cross-gpu-first-read | -1 | -1 | 0.00 | 0.006712 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cross-gpu-first-read-create-replica | 0 | 1 | 64.00 | 0.132598 | 482.66 |  |
| cache_control | before-cross-gpu-rehit-after-replica | -1 | -1 | 0.00 | 0.006084 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cross-gpu-rehit-after-replica | 0 | 1 | 4032.00 | 11.249587 | 358.41 | batched 63 repeated reads in one loader process |
