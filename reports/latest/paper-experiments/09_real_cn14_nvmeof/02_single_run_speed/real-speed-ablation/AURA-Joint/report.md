# TokenFS Token Workload 报告

实验命名空间：`real-AURA-Joint-1789485174-998497`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。

| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| seed_remote | remote-canonical-hot | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-hot | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-cross-gpu | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.338148 | 47.83 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.642455 | 38.97 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.705493 | 37.53 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.859871 | 34.41 |  |
| cache_control | before-cold-local-read | -1 | -1 | 0.00 | 0.006724 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cold-local-read | 0 | 0 | 64.00 | 0.579056 | 110.52 |  |
| write | capacity-pressure-append-existing | 0 | 0 | 8.00 | 0.721415 | 11.09 | append existing local cache to force eviction |
| cache_control | before-remote-hot-first-read | -1 | -1 | 0.00 | 0.006290 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | remote-hot-first-read | 0 | 0 | 64.00 | 1.047834 | 61.08 |  |
| read | remote-hot-second-read-promote | 0 | 0 | 64.00 | 0.626705 | 102.12 |  |
| cache_control | before-hot-rehit-after-promote | -1 | -1 | 0.00 | 0.006136 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | hot-rehit-after-promote | 0 | 0 | 8192.00 | 32.811512 | 249.67 | batched 128 repeated reads in one loader process |
| cache_control | before-sequential-next-read-after-prefetch | -1 | -1 | 0.00 | 0.007061 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | sequential-next-read-after-prefetch | 0 | 0 | 64.00 | 0.114364 | 559.62 |  |
| cache_control | before-sequential-rehit-after-prefetch | -1 | -1 | 0.00 | 0.006209 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | sequential-rehit-after-prefetch | 0 | 0 | 4096.00 | 11.582314 | 353.64 | batched 64 repeated reads in one loader process |
| cache_control | before-cross-gpu-first-read | -1 | -1 | 0.00 | 0.006671 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cross-gpu-first-read-create-replica | 0 | 1 | 64.00 | 0.147048 | 435.23 |  |
| cache_control | before-cross-gpu-rehit-after-replica | -1 | -1 | 0.00 | 0.006222 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cross-gpu-rehit-after-replica | 0 | 1 | 4032.00 | 12.511815 | 322.26 | batched 63 repeated reads in one loader process |
