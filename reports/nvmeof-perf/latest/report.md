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

| 用例 | 操作 | 块大小 | 数据量 MiB | 耗时 s | 带宽 MiB/s | IOPS | 平均延迟 us | P95 us | P99 us |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `direct-local-read` | read | 1m | 32.0 | 0.017 | 1882.35 | 1882.35 | 420.46 | 626.69 | 1253.38 |
| `direct-local-write` | write | 1m | 32.0 | 0.009 | 3555.56 | 3555.56 | 254.61 | 296.96 | 305.15 |
| `direct-remote-read` | read | 1m | 32.0 | 0.099 | 323.23 | 323.23 | 2979.78 | 4112.38 | 5537.79 |
| `direct-remote-write` | write | 1m | 32.0 | 0.008 | 4000.0 | 4000.0 | 245.8 | 296.96 | 362.5 |
| `tokenfs-local-read` | read | 1m | 32.0 | 0.488 | 65.57 | 65.57 | 15178.47 | 17432.58 | 19529.73 |
| `tokenfs-local-write` | write | 1m | 32.0 | 0.17 | 188.24 | 188.24 | 5166.45 | 6389.76 | 6586.37 |
| `tokenfs-remote-read` | read | 1m | 96.0 | 0.662 | 145.02 | 145.02 | 4042.85 | 4358.14 | 5275.65 |
| `tokenfs-remote-spill-write` | write | 1m | 96.0 | 0.219 | 438.36 | 438.36 | 2240.35 | 4685.82 | 5013.5 |

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

## 耗时可视化

```text
direct-local-read              █░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0.017 s
direct-local-write             ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0.009 s
direct-remote-read             ████░░░░░░░░░░░░░░░░░░░░░░░░ 0.099 s
direct-remote-write            ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0.008 s
tokenfs-local-read             █████████████████████░░░░░░░ 0.488 s
tokenfs-local-write            ███████░░░░░░░░░░░░░░░░░░░░░ 0.17 s
tokenfs-remote-read            ████████████████████████████ 0.662 s
tokenfs-remote-spill-write     █████████░░░░░░░░░░░░░░░░░░░ 0.219 s
```

## P99 延迟可视化

```text
direct-local-read              ██░░░░░░░░░░░░░░░░░░░░░░░░░░ 1253.38 us
direct-local-write             ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 305.15 us
direct-remote-read             ████████░░░░░░░░░░░░░░░░░░░░ 5537.79 us
direct-remote-write            █░░░░░░░░░░░░░░░░░░░░░░░░░░░ 362.5 us
tokenfs-local-read             ████████████████████████████ 19529.73 us
tokenfs-local-write            █████████░░░░░░░░░░░░░░░░░░░ 6586.37 us
tokenfs-remote-read            ████████░░░░░░░░░░░░░░░░░░░░ 5275.65 us
tokenfs-remote-spill-write     ███████░░░░░░░░░░░░░░░░░░░░░ 5013.5 us
```

## 自动解读

- 直接远端读取的平均延迟约为直接本地读取的 7.1 倍，带宽约为本地的 17.2%。这说明远端路径即使能跑出带宽，也会多出网络和 Target 处理延迟。
- TokenFS 本地读带宽低于直接本地读，当前约有 28.7 倍差距，主要反映 FUSE、元数据维护和用户态转发开销。
- TokenFS 远端读相比直接远端读约慢 2.2 倍，后续热点提升和顺序预取就是为了减少重复远端读取。
- 远端溢写写入不是单纯写文件，还包含配额判断、必要时迁移和元数据提交，因此要和直接目录写分开解读。
- 直接远端写入看起来不慢甚至更快时，不要直接理解成远端 SSD 比本地快。当前基线使用较大的顺序块且可能经过页缓存，写入完成可能先落入内核缓存；论文实验需要增加 direct=1、更大数据量和 fsync/掉电语义测试。
- 本组测试块大小是 1 MiB，因此 IOPS 与 MiB/s 数值接近。后续若改成 4 KiB 随机读写，IOPS 更适合衡量小块访问能力。

## 如何解读

- 带宽说明一次大块连续读写能跑多快。
- 耗时说明完成这次测试总共花了多久。
- 延迟说明单个 I/O 请求要等多久，远端路径通常更吃亏。
- IOPS 表示每秒完成多少次 I/O；当块大小是 1 MiB 时，IOPS 和 MiB/s 数值会接近。

如果本报告来自双 VM NVMe-oF 环境，它可以证明真实 NVMe/TCP 协议路径已经接入，但由于底层仍是虚拟磁盘和虚拟网络，最终论文性能数据仍应在真实 SSD 与实验室网络上重新采集。
