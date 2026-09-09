# TokenFS Token Workload 报告

该 workload 模拟机器学习 token shard：顺序预分配写入、GPU 本地配额填满、远端连续 shard 溢写、重复读取热点 shard，以及读取下一片连续 shard。

| 操作 | 分组 | GPU | 数据量 MiB | 预分配 | 耗时 s | 带宽 MiB/s | 路径 |
|---|---|---:|---:|---:|---:|---:|---|
| write | normal-local-fill | 0 | 8 | 1 | 0.121717 | 65.73 | `/mnt/tokenfs/gpu0/dataset-a/shard-000000.tokens` |
| write | normal-local-fill | 0 | 8 | 1 | 0.141086 | 56.70 | `/mnt/tokenfs/gpu0/dataset-a/shard-000001.tokens` |
| write | normal-local-fill | 0 | 8 | 1 | 0.137025 | 58.38 | `/mnt/tokenfs/gpu0/dataset-a/shard-000002.tokens` |
| write | normal-local-fill | 0 | 8 | 1 | 0.142173 | 56.27 | `/mnt/tokenfs/gpu0/dataset-a/shard-000003.tokens` |
| write | overflow-sequential | 0 | 8 | 1 | 0.162043 | 49.37 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| write | overflow-sequential | 0 | 8 | 1 | 0.210683 | 37.97 | `/mnt/tokenfs/gpu0/dataset-a/shard-000101.tokens` |
| write | large-remote-spill | 0 | 40 | 1 | 0.591087 | 67.67 | `/mnt/tokenfs/gpu0/dataset-a/shard-900000.tokens` |
| write | gpu1-isolation | 1 | 8 | 1 | 0.227987 | 35.09 | `/mnt/tokenfs/gpu1/dataset-a/shard-000000.tokens` |
| read | local-hot-read | 0 | 8.00 |  | 0.135584 | 59.00 | `/mnt/tokenfs/gpu0/dataset-a/shard-000000.tokens` |
| read | remote-first-read | 0 | 8.00 |  | 0.104586 | 76.49 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| read | remote-second-read | 0 | 8.00 |  | 0.100961 | 79.24 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| read | sequential-next-read | 0 | 8.00 |  | 0.140508 | 56.94 | `/mnt/tokenfs/gpu0/dataset-a/shard-000101.tokens` |
| read | large-remote-spill-read | 0 | 40.00 |  | 0.516613 | 77.43 | `/mnt/tokenfs/gpu0/dataset-a/shard-900000.tokens` |
| read | gpu1-isolation-read | 1 | 8.00 |  | 0.104754 | 76.37 | `/mnt/tokenfs/gpu1/dataset-a/shard-000000.tokens` |
