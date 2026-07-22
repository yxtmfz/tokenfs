# TokenFS 双 VM NVMe-oF 性能基线报告

本报告使用两台 Ubuntu VM 运行真实 Linux NVMe/TCP Host/Target 链路。远端后端挂载点为 /srv/tokenfs/remote0，Target 为 192.168.64.3:4420。结果可用于验证协议接入和相对开销，最终论文性能数据仍应在真实 SSD 与实验室网络上重新采集。

## 测试说明

- `direct-local-read`：直接读 GPU 本地后端目录，作为本地存储读取基线。
- `direct-local-write`：直接写 GPU 本地后端目录，作为本地存储写入基线。
- `direct-remote-read`：直接读远端后端目录，开发模式下是目录模拟，NVMe-oF 模式下是远端挂载目录。
- `direct-remote-write`：直接写远端后端目录，开发模式下是目录模拟，NVMe-oF 模式下是远端挂载目录。
- `tokenfs-local-read`：通过 TokenFS/FUSE 读取本地层文件。
- `tokenfs-local-write`：通过 TokenFS/FUSE 写入小文件，预期保留在 GPU 本地层。
- `tokenfs-remote-read`：通过 TokenFS/FUSE 读取远端层文件。
- `tokenfs-remote-spill-write`：通过 TokenFS/FUSE 写入超过本地配额的文件，触发远端溢写。

## 结果表

| 用例 | 操作 | 数据量 MiB | 耗时 s | 带宽 MiB/s | IOPS | 平均延迟 us | P95 us | P99 us |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `direct-local-read` | read | 32.0 | 0.017 | 1882.35 | 1882.35 | 420.46 | 626.69 | 1253.38 |
| `direct-local-write` | write | 32.0 | 0.009 | 3555.56 | 3555.56 | 254.61 | 296.96 | 305.15 |
| `direct-remote-read` | read | 32.0 | 0.099 | 323.23 | 323.23 | 2979.78 | 4112.38 | 5537.79 |
| `direct-remote-write` | write | 32.0 | 0.008 | 4000.0 | 4000.0 | 245.8 | 296.96 | 362.5 |
| `tokenfs-local-read` | read | 32.0 | 0.488 | 65.57 | 65.57 | 15178.47 | 17432.58 | 19529.73 |
| `tokenfs-local-write` | write | 32.0 | 0.17 | 188.24 | 188.24 | 5166.45 | 6389.76 | 6586.37 |
| `tokenfs-remote-read` | read | 96.0 | 0.662 | 145.02 | 145.02 | 4042.85 | 4358.14 | 5275.65 |
| `tokenfs-remote-spill-write` | write | 96.0 | 0.219 | 438.36 | 438.36 | 2240.35 | 4685.82 | 5013.5 |

## 带宽可视化

```text
direct-local-read              █████████████░░░░░░░░░░░░░░░ 1882.35 MiB/s
direct-local-write             █████████████████████████░░░ 3555.56 MiB/s
direct-remote-read             ██░░░░░░░░░░░░░░░░░░░░░░░░░░ 323.23 MiB/s
direct-remote-write            ████████████████████████████ 4000.0 MiB/s
tokenfs-local-read             ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 65.57 MiB/s
tokenfs-local-write            █░░░░░░░░░░░░░░░░░░░░░░░░░░░ 188.24 MiB/s
tokenfs-remote-read            █░░░░░░░░░░░░░░░░░░░░░░░░░░░ 145.02 MiB/s
tokenfs-remote-spill-write     ███░░░░░░░░░░░░░░░░░░░░░░░░░ 438.36 MiB/s
```

## 如何解读

这组测试主要用于观察：

- FUSE 路径相比直接目录访问的额外开销。
- 本地优先写入是否能正常保留在本地层。
- 超过配额后是否能触发远端溢写。
- 远端后端从目录模拟切换到 NVMe-oF 后的相对开销。

如果本报告来自双 VM NVMe-oF 环境，它可以证明真实 NVMe/TCP 协议路径已经接入，但由于底层仍是虚拟磁盘和虚拟网络，最终论文性能数据仍应在真实 SSD 与实验室网络上重新采集。
