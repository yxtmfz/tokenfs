# TokenFS Token Workload 报告

该 workload 模拟机器学习 token shard：顺序预分配写入、GPU 本地配额填满、远端连续 shard 溢写、重复读取热点 shard，以及读取下一片连续 shard。

| 操作 | 分组 | GPU | 数据量 MiB | 预分配 | 耗时 s | 带宽 MiB/s | 路径 |
|---|---|---:|---:|---:|---:|---:|---|
| write | normal-local-fill | 0 | 8 | 1 | 0.161745 | 49.46 | `/mnt/tokenfs/gpu0/dataset-a/shard-000000.tokens` |
| write | normal-local-fill | 0 | 8 | 1 | 0.135177 | 59.18 | `/mnt/tokenfs/gpu0/dataset-a/shard-000001.tokens` |
| write | normal-local-fill | 0 | 8 | 1 | 0.133450 | 59.95 | `/mnt/tokenfs/gpu0/dataset-a/shard-000002.tokens` |
| write | normal-local-fill | 0 | 8 | 1 | 0.130297 | 61.40 | `/mnt/tokenfs/gpu0/dataset-a/shard-000003.tokens` |
| write | overflow-sequential | 0 | 8 | 1 | 0.148204 | 53.98 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| write | overflow-sequential | 0 | 8 | 1 | 0.147011 | 54.42 | `/mnt/tokenfs/gpu0/dataset-a/shard-000101.tokens` |
| write | large-remote-spill | 0 | 40 | 1 | 0.548666 | 72.90 | `/mnt/tokenfs/gpu0/dataset-a/shard-900000.tokens` |
| write | gpu1-isolation | 1 | 8 | 1 | 0.203867 | 39.24 | `/mnt/tokenfs/gpu1/dataset-a/shard-000000.tokens` |
| read | local-hot-read | 0 | 8.00 |  | 0.128584 | 62.22 | `/mnt/tokenfs/gpu0/dataset-a/shard-000000.tokens` |
| read | remote-first-read | 0 | 8.00 |  | 0.102677 | 77.91 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| read | remote-second-read | 0 | 8.00 |  | 0.102818 | 77.81 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| read | sequential-next-read | 0 | 8.00 |  | 0.146132 | 54.75 | `/mnt/tokenfs/gpu0/dataset-a/shard-000101.tokens` |
| read | large-remote-spill-read | 0 | 40.00 |  | 0.522007 | 76.63 | `/mnt/tokenfs/gpu0/dataset-a/shard-900000.tokens` |
| read | gpu1-isolation-read | 1 | 8.00 |  | 0.105889 | 75.55 | `/mnt/tokenfs/gpu1/dataset-a/shard-000000.tokens` |
