# TokenFS 性能测试报告

本报告由 `scripts/perf_test.sh` 自动生成，当前结果基于开发虚拟机和目录模拟远端后端。

## 测试说明

- `direct-local-write`：直接写本地后端目录，作为本地目录基线。
- `direct-remote-write`：直接写远端模拟目录，作为远端目录基线。
- `tokenfs-local-write`：通过 FUSE 写小文件，预期留在本地层。
- `tokenfs-remote-spill-write`：通过 FUSE 写超过本地配额的大文件，触发远端溢写。
- `tokenfs-local-read` / `tokenfs-remote-read`：通过 FUSE 读取本地层和远端层文件。

## 结果表

| 用例 | 操作 | 数据量 MiB | 耗时 s | 带宽 MiB/s | IOPS |
|---|---:|---:|---:|---:|---:|
| `direct-local-write` | write | 32.0 | 0.009 | 3555.56 | 3555.56 |
| `direct-remote-write` | write | 32.0 | 0.009 | 3555.56 | 3555.56 |
| `tokenfs-local-read` | read | 32.0 | 0.068 | 470.59 | 470.59 |
| `tokenfs-local-write` | write | 32.0 | 0.039 | 820.51 | 820.51 |
| `tokenfs-remote-read` | read | 80.0 | 0.025 | 3200.0 | 3200.0 |
| `tokenfs-remote-spill-write` | write | 80.0 | 0.096 | 833.33 | 833.33 |

## 带宽可视化

```text
direct-local-write             ████████████████████████████ 3555.56 MiB/s
direct-remote-write            ████████████████████████████ 3555.56 MiB/s
tokenfs-local-read             ████░░░░░░░░░░░░░░░░░░░░░░░░ 470.59 MiB/s
tokenfs-local-write            ██████░░░░░░░░░░░░░░░░░░░░░░ 820.51 MiB/s
tokenfs-remote-read            █████████████████████████░░░ 3200.0 MiB/s
tokenfs-remote-spill-write     ███████░░░░░░░░░░░░░░░░░░░░░ 833.33 MiB/s
```

## 如何解读

当前测试使用目录模拟远端，并不代表真实 NVMe-oF 网络性能。它主要用于观察：

- FUSE 路径相比直接目录访问的额外开销。
- 本地优先写入是否能正常保留在本地层。
- 超过配额后是否能触发远端溢写。
- 读写路径在虚拟机开发环境中的相对表现。

接入真实 NVMe-oF 后，应重新运行同一脚本，并将远端模拟目录替换为 `/srv/tokenfs/remote0`。
