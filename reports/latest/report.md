# TokenFS Token Workload 报告

该 workload 模拟机器学习 token shard：顺序预分配写入、GPU 本地配额填满、远端连续 shard 溢写、重复读取热点 shard，以及读取下一片连续 shard。

| 操作 | 分组 | GPU | 数据量 MiB | 预分配 | 耗时 s | 带宽 MiB/s | 路径 |
|---|---|---:|---:|---:|---:|---:|---|
| write | normal-local-fill | 0 | 16 | 1 | 0.232934 | 68.69 | `/mnt/tokenfs/gpu0/dataset-a/shard-000000.tokens` |
| write | normal-local-fill | 0 | 16 | 1 | 0.292277 | 54.74 | `/mnt/tokenfs/gpu0/dataset-a/shard-000001.tokens` |
| write | normal-local-fill | 0 | 16 | 1 | 0.288402 | 55.48 | `/mnt/tokenfs/gpu0/dataset-a/shard-000002.tokens` |
| write | normal-local-fill | 0 | 16 | 1 | 0.284331 | 56.27 | `/mnt/tokenfs/gpu0/dataset-a/shard-000003.tokens` |
| write | overflow-sequential | 0 | 16 | 1 | 0.277306 | 57.70 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| write | overflow-sequential | 0 | 16 | 1 | 0.293451 | 54.52 | `/mnt/tokenfs/gpu0/dataset-a/shard-000101.tokens` |
| write | large-remote-spill | 0 | 96 | 1 | 1.149555 | 83.51 | `/mnt/tokenfs/gpu0/dataset-a/shard-900000.tokens` |
| write | gpu1-isolation | 1 | 16 | 1 | 0.664263 | 24.09 | `/mnt/tokenfs/gpu1/dataset-a/shard-000000.tokens` |
| read | local-hot-read | 0 | 16.00 |  | 0.226526 | 70.63 | `/mnt/tokenfs/gpu0/dataset-a/shard-000000.tokens` |
| read | remote-first-read | 0 | 16.00 |  | 0.130478 | 122.63 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| read | remote-second-read | 0 | 16.00 |  | 0.130932 | 122.20 | `/mnt/tokenfs/gpu0/dataset-a/shard-000100.tokens` |
| read | sequential-next-read | 0 | 16.00 |  | 0.169124 | 94.61 | `/mnt/tokenfs/gpu0/dataset-a/shard-000101.tokens` |
| read | large-remote-spill-read | 0 | 96.00 |  | 0.815721 | 117.69 | `/mnt/tokenfs/gpu0/dataset-a/shard-900000.tokens` |
| read | gpu1-isolation-read | 1 | 16.00 |  | 0.131137 | 122.01 | `/mnt/tokenfs/gpu1/dataset-a/shard-000000.tokens` |
