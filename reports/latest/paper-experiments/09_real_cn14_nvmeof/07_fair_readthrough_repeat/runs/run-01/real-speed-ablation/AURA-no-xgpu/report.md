# TokenFS Token Workload 报告

实验命名空间：`real-AURA-no-xgpu-1789559086-1156010`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。

| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| seed_remote | remote-canonical-hot | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-hot | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-cross-gpu | 0 | 0 | 64.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.223859 | 52.29 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.756703 | 36.43 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.820230 | 35.16 |  |
| write | cold-local-cache-fill | 0 | 0 | 64.00 | 1.802619 | 35.50 |  |
| cache_control | before-cold-local-read | -1 | -1 | 0.00 | 0.006652 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cold-local-read | 0 | 0 | 64.00 | 0.560809 | 114.12 | Linux page cache dropped before each logical read |
| write | capacity-pressure-append-existing | 0 | 0 | 8.00 | 0.968304 | 8.26 | append existing local cache to force eviction |
| cache_control | before-remote-hot-first-read | -1 | -1 | 0.00 | 0.006316 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | remote-hot-first-read | 0 | 0 | 64.00 | 0.756706 | 84.58 | Linux page cache dropped before each logical read |
| read | remote-hot-second-read-promote | 0 | 0 | 64.00 | 0.428119 | 149.49 | Linux page cache dropped before each logical read |
| cache_control | before-hot-rehit-after-promote | -1 | -1 | 0.00 | 0.007109 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | hot-rehit-after-promote | 0 | 0 | 8192.00 | 29.679617 | 276.01 | batched 128 repeated reads in one loader process; Linux page cache dropped before each logical read |
| cache_control | before-sequential-next-read-after-prefetch | -1 | -1 | 0.00 | 0.006642 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | sequential-next-read-after-prefetch | 0 | 0 | 64.00 | 0.066079 | 968.54 | Linux page cache dropped before each logical read |
| cache_control | before-sequential-rehit-after-prefetch | -1 | -1 | 0.00 | 0.006148 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | sequential-rehit-after-prefetch | 0 | 0 | 4096.00 | 9.647259 | 424.58 | batched 64 repeated reads in one loader process; Linux page cache dropped before each logical read |
| cache_control | before-cross-gpu-first-read | -1 | -1 | 0.00 | 0.007037 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cross-gpu-first-read-create-replica | 0 | 1 | 64.00 | 0.132269 | 483.86 | Linux page cache dropped before each logical read |
| cache_control | before-cross-gpu-rehit-after-replica | -1 | -1 | 0.00 | 0.006662 | 0.00 | requested Linux page cache drop but sudo non-interactive permission was unavailable |
| read | cross-gpu-rehit-after-replica | 0 | 1 | 4032.00 | 11.666132 | 345.62 | batched 63 repeated reads in one loader process; Linux page cache dropped before each logical read |
