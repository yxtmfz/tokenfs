# TokenFS Token Workload 报告

实验命名空间：`real-LFU-Local-1789485464-998919`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。

| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| seed_remote | remote-canonical-hot | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-hot | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-cross-gpu | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.355311 | 47.22 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.659594 | 38.56 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.802649 | 35.50 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.682274 | 38.04 |  |
| cache_control | before-cold-local-read | -1 | -1 | 0.00 | 0.006925 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cold-local-read | 0 | 0 | 64.00 | 0.675567 | 94.74 |  |
| write | capacity-pressure-append-existing | 0 | 0 | 8.00 | 0.675650 | 11.84 | append existing local cache to force eviction |
| cache_control | before-remote-hot-first-read | -1 | -1 | 0.00 | 0.006570 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | remote-hot-first-read | 0 | 0 | 64.00 | 0.632928 | 101.12 |  |
| read | remote-hot-second-read-promote | 0 | 0 | 64.00 | 0.465688 | 137.43 |  |
| cache_control | before-hot-rehit-after-promote | -1 | -1 | 0.00 | 0.006756 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | hot-rehit-after-promote | 0 | 0 | 8192.00 | 30.973228 | 264.49 | batched 128 repeated reads in one loader process |
| cache_control | before-sequential-next-read-after-prefetch | -1 | -1 | 0.00 | 0.007297 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | sequential-next-read-after-prefetch | 0 | 0 | 64.00 | 0.097260 | 658.03 |  |
| cache_control | before-sequential-rehit-after-prefetch | -1 | -1 | 0.00 | 0.005441 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | sequential-rehit-after-prefetch | 0 | 0 | 4096.00 | 10.293046 | 397.94 | batched 64 repeated reads in one loader process |
| cache_control | before-cross-gpu-first-read | -1 | -1 | 0.00 | 0.006416 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cross-gpu-first-read-create-replica | 0 | 1 | 64.00 | 0.138353 | 462.59 |  |
| cache_control | before-cross-gpu-rehit-after-replica | -1 | -1 | 0.00 | 0.006436 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cross-gpu-rehit-after-replica | 0 | 1 | 4032.00 | 10.768977 | 374.41 | batched 63 repeated reads in one loader process |
