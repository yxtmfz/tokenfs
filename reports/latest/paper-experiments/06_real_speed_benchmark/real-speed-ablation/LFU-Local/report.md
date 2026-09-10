# TokenFS Token Workload 报告

实验命名空间：`real-LFU-Local-1789008724-51739`。该 workload 不再只是端到端读写压测，而是显式构造 AURA-KV 论文场景：远端已有 canonical KV Cache，本地 GPU 缓存被冷数据占满，随后通过扩展已有本地文件、热点重复访问、连续 shard 访问和跨 GPU 共享访问触发淘汰、提升、预取与跨 GPU 副本。每次运行使用独立命名空间，避免旧远端文件污染结果，也不会删除已有远端数据。

| 操作 | 阶段 | 文件所属 GPU | 调用 GPU | 数据量 MiB | 耗时 s | 带宽 MiB/s | 说明 |
|---|---|---:|---:|---:|---:|---:|---|
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-hot | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| seed_remote | remote-canonical-cross-gpu | 0 | 0 | 8.00 | 0.000000 | 0.00 | pre-existing remote canonical cache |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.113177 | 70.69 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.133285 | 60.02 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.130750 | 61.19 |  |
| write | cold-local-cache-fill | 0 | 0 | 8.00 | 0.132020 | 60.60 |  |
| read | cold-local-read | 0 | 0 | 8.00 | 0.393421 | 20.33 |  |
| write | capacity-pressure-append-existing | 0 | 0 | 8.00 | 0.119716 | 66.83 | append existing local cache to force eviction |
| read | remote-hot-first-read | 0 | 0 | 8.00 | 0.171017 | 46.78 |  |
| read | remote-hot-second-read-promote | 0 | 0 | 8.00 | 0.117043 | 68.35 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.165179 | 48.43 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.120901 | 66.17 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128697 | 62.16 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.120101 | 66.61 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.121029 | 66.10 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.129354 | 61.85 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.127103 | 62.94 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.129011 | 62.01 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.127533 | 62.73 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.127748 | 62.62 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.123679 | 64.68 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.152073 | 52.61 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.294109 | 27.20 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.153746 | 52.03 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.155474 | 51.46 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.150520 | 53.15 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.125309 | 63.84 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.127690 | 62.65 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.125024 | 63.99 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119206 | 67.11 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119323 | 67.04 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.124264 | 64.38 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.125533 | 63.73 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.122505 | 65.30 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.119611 | 66.88 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.123595 | 64.73 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.126230 | 63.38 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.121645 | 65.77 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.123326 | 64.87 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.131169 | 60.99 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.187632 | 42.64 |  |
| read | hot-rehit-after-promote | 0 | 0 | 8.00 | 0.128044 | 62.48 |  |
| read | sequential-next-read-after-prefetch | 0 | 0 | 8.00 | 0.196052 | 40.81 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.123524 | 64.76 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.128422 | 62.29 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.121408 | 65.89 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.121487 | 65.85 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.237074 | 33.74 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.127680 | 62.66 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.120659 | 66.30 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.121014 | 66.11 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.129513 | 61.77 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.126757 | 63.11 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.125716 | 63.64 |  |
| read | sequential-rehit-after-prefetch | 0 | 0 | 8.00 | 0.155597 | 51.42 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.135779 | 58.92 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.179735 | 44.51 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.125219 | 63.89 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.122008 | 65.57 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.202043 | 39.60 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.129278 | 61.88 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.120625 | 66.32 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.120786 | 66.23 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.119807 | 66.77 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.127482 | 62.75 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.130549 | 61.28 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.122767 | 65.16 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.123188 | 64.94 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.129184 | 61.93 |  |
| read | cross-gpu-shared-read | 0 | 1 | 8.00 | 0.122382 | 65.37 |  |
| read | cross-gpu-rehit-after-replica | 0 | 1 | 8.00 | 0.122488 | 65.31 |  |
