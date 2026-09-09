# TokenFS Token Workload 报告

该 workload 模拟机器学习 token shard：顺序预分配写入、GPU 本地配额填满、远端连续 shard 溢写、重复读取热点 shard，以及读取下一片连续 shard。

| 操作 | 分组 | GPU | 数据量 MiB | 预分配 | 耗时 s | 带宽 MiB/s | 路径 |
|---|---|---:|---:|---:|---:|---:|---|
| write | normal-local-fill | 0 | 8 | 1 | 0.118155 | 67.71 | `/mnt/tokenfs/gpu0/dataset-a/shard-000000.tokens` |
| write | normal-local-fill | 0 | 8 | 1 | 0.168470 | 47.49 | `/mnt/tokenfs/gpu0/dataset-a/shard-000001.tokens` |
| write | normal-local-fill | 0 | 8 | 1 | 0.153475 | 52.13 | `/mnt/tokenfs/gpu0/dataset-a/shard-000002.tokens` |
| write | normal-local-fill | 0 | 8 | 1 | 0.148645 | 53.82 | `/mnt/tokenfs/gpu0/dataset-a/shard-000003.tokens` |
| write | overflow-sequential | 0 | 8 | 1 | 0.188941 | 42.34 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| write | overflow-sequential | 0 | 8 | 1 | 0.160517 | 49.84 | `/mnt/tokenfs/gpu0/dataset-a/shard-000101.tokens` |
| write | large-remote-spill | 0 | 40 | 1 | 0.572367 | 69.89 | `/mnt/tokenfs/gpu0/dataset-a/shard-900000.tokens` |
| write | gpu1-isolation | 1 | 8 | 1 | 0.234981 | 34.05 | `/mnt/tokenfs/gpu1/dataset-a/shard-000000.tokens` |
| read | local-hot-read | 0 | 8.00 |  | 0.134298 | 59.57 | `/mnt/tokenfs/gpu0/dataset-a/shard-000000.tokens` |
| read | remote-first-read | 0 | 8.00 |  | 0.100690 | 79.45 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| read | remote-second-read | 0 | 8.00 |  | 0.101436 | 78.87 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| read | sequential-next-read | 0 | 8.00 |  | 0.156206 | 51.21 | `/mnt/tokenfs/gpu0/dataset-a/shard-000101.tokens` |
| read | large-remote-spill-read | 0 | 40.00 |  | 0.522180 | 76.60 | `/mnt/tokenfs/gpu0/dataset-a/shard-900000.tokens` |
| read | gpu1-isolation-read | 1 | 8.00 |  | 0.106898 | 74.84 | `/mnt/tokenfs/gpu1/dataset-a/shard-000000.tokens` |
