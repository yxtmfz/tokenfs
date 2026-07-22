# TokenFS Token Workload Report

This workload simulates large ML token shard files with preallocation and sequential I/O.

| operation | gpu | size MiB | preallocate | seconds | MiB/s | path |
|---|---:|---:|---:|---:|---:|---|
| write | 0 | 8 | 1 | 0.078901 | 101.39 | `/mnt/tokenfs/gpu0/dataset-a/shard-000000.tokens` |
| write | 0 | 8 | 1 | 0.095935 | 83.39 | `/mnt/tokenfs/gpu0/dataset-a/shard-000001.tokens` |
| write | 0 | 8 | 1 | 0.096161 | 83.19 | `/mnt/tokenfs/gpu0/dataset-a/shard-000002.tokens` |
| write | 0 | 80 | 1 | 0.642806 | 124.45 | `/mnt/tokenfs/gpu0/dataset-a/shard-900000.tokens` |
| write | 1 | 8 | 1 | 0.358145 | 22.34 | `/mnt/tokenfs/gpu1/dataset-a/shard-000000.tokens` |
| read | 0 | 8.00 |  | 0.201557 | 39.69 | `/mnt/tokenfs/gpu0/dataset-a/shard-000000.tokens` |
| read | 0 | 8.00 |  | 0.061201 | 130.72 | `/mnt/tokenfs/gpu0/dataset-a/shard-000001.tokens` |
| read | 0 | 8.00 |  | 0.037943 | 210.84 | `/mnt/tokenfs/gpu0/dataset-a/shard-000002.tokens` |
| read | 0 | 80.00 |  | 0.359705 | 222.40 | `/mnt/tokenfs/gpu0/dataset-a/shard-900000.tokens` |
| read | 1 | 8.00 |  | 0.037585 | 212.85 | `/mnt/tokenfs/gpu1/dataset-a/shard-000000.tokens` |
