# TokenFS Token Workload 报告

实验命名空间：`real-AURA-Joint-1789124677-58952`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。

| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-cross-gpu | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.049517 | 161.56 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.088072 | 90.83 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.085986 | 93.04 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.084372 | 94.82 |  |
| cache_control | before-cold-local-read | -1 | -1 | 0.00 | 0.026314 | 0.00 | Linux page cache dropped before storage-tier measurement |
| read | cold-local-read | 0 | 0 | 8.00 | 0.013541 | 590.80 | Linux page cache dropped before each logical read |
| write | capacity-pressure-append-existing | 0 | 0 | 8.00 | 0.161258 | 49.61 | append existing local cache to force eviction |
| cache_control | before-remote-hot-first-read | -1 | -1 | 0.00 | 0.024436 | 0.00 | Linux page cache dropped before storage-tier measurement |
| read | remote-hot-first-read | 0 | 0 | 8.00 | 0.049441 | 161.81 | Linux page cache dropped before each logical read |
| read | remote-hot-second-read-promote | 0 | 0 | 8.00 | 0.037997 | 210.54 | Linux page cache dropped before each logical read |
| cache_control | before-hot-rehit-after-promote | -1 | -1 | 0.00 | 0.058471 | 0.00 | Linux page cache dropped before storage-tier measurement |
| read | hot-rehit-after-promote | 0 | 0 | 1024.00 | 1.530894 | 668.89 | batched 128 repeated reads in one loader process; Linux page cache dropped before each logical read |
| cache_control | before-sequential-next-read-after-prefetch | -1 | -1 | 0.00 | 0.041208 | 0.00 | Linux page cache dropped before storage-tier measurement |
| read | sequential-next-read-after-prefetch | 0 | 0 | 8.00 | 0.018842 | 424.58 | Linux page cache dropped before each logical read |
| cache_control | before-sequential-rehit-after-prefetch | -1 | -1 | 0.00 | 0.023255 | 0.00 | Linux page cache dropped before storage-tier measurement |
| read | sequential-rehit-after-prefetch | 0 | 0 | 512.00 | 0.755674 | 677.54 | batched 64 repeated reads in one loader process; Linux page cache dropped before each logical read |
| cache_control | before-cross-gpu-first-read | -1 | -1 | 0.00 | 0.017693 | 0.00 | Linux page cache dropped before storage-tier measurement |
| read | cross-gpu-first-read-create-replica | 0 | 1 | 8.00 | 0.035060 | 228.18 | Linux page cache dropped before each logical read |
| cache_control | before-cross-gpu-rehit-after-replica | -1 | -1 | 0.00 | 0.046566 | 0.00 | Linux page cache dropped before storage-tier measurement |
| read | cross-gpu-rehit-after-replica | 0 | 1 | 504.00 | 0.912242 | 552.49 | batched 63 repeated reads in one loader process; Linux page cache dropped before each logical read |
