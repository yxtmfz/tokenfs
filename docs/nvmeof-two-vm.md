# 双虚拟机 NVMe-oF 实验说明

本文档用于在没有实验室真实 SSD Target 的情况下，先用两台 Ubuntu 虚拟机跑通真正的 NVMe/TCP 协议链路。

## 节点角色

```text
tokenfs-dev
  作为 GPU Host / TokenFS 客户端
  运行 FUSE、TokenFS、nvme-tcp Host

tokenfs-target
  作为远端 SSD 服务器模拟节点
  运行 Linux nvmet / nvmet-tcp Target
  使用 loop 文件模拟一块远端块设备
```

这不是简单的普通目录模拟。Host 端会通过 `nvme discover` 和 `nvme connect` 连接 Target，Linux 会生成真实的 `/dev/nvmeXnY` 远端块设备，再挂载到 `/srv/tokenfs/remote0` 供 TokenFS 使用。

## 实验价值

这个实验可以验证：

- TokenFS 的远端后端接口已经可以接入 NVMe-oF。
- Host/Target 的 NQN、IP、端口、发现、连接、挂载流程可以跑通。
- 本地配额不足时，TokenFS 可以把文件溢写到 NVMe-oF 挂载目录。
- SQLite 元数据能记录 `tier=remote` 和真实远端挂载路径。
- 之后拿到真实 SSD Target 时，主要替换 IP、NQN 和设备信息。

这个实验暂时不能代表真实 SSD 性能，因为底层仍是虚拟机磁盘和虚拟网络。它更适合证明协议接入、部署流程和功能正确性。

## Target VM 操作

在 `tokenfs-target` 上安装基础工具：

```bash
sudo apt update
sudo apt install -y git nvme-cli
```

获取代码：

```bash
git clone https://github.com/yxtmfz/tokenfs.git
cd tokenfs
```

启动 NVMe/TCP Target：

```bash
sudo ./scripts/setup_nvme_target.sh \
  --target-ip 0.0.0.0 \
  --port 4420 \
  --subnqn nqn.2026-07.local.tokenfs:remote0 \
  --image /var/lib/tokenfs/nvmeof-target/remote0.img \
  --size 20G
```

Target 启动后保持运行即可。

如需清理 Target：

```bash
sudo ./scripts/cleanup_nvme_target.sh \
  --subnqn nqn.2026-07.local.tokenfs:remote0 \
  --image /var/lib/tokenfs/nvmeof-target/remote0.img
```

如果明确要删除模拟盘镜像，可以额外加：

```bash
--remove-image
```

## Client VM 操作

在 `tokenfs-dev` 上确认可以访问 Target IP。当前示例中 Target IP 是：

```text
192.168.64.3
```

运行双 VM 测试：

```bash
cd ~/projects/tokenfs
git pull

TOKENFS_NVME_TARGET_IP=192.168.64.3 \
  ./scripts/nvmeof_two_vm_test.sh
```

脚本会执行：

```text
1. 使用 nvme discover 发现 Target。
2. 使用 nvme connect 连接 Subsystem。
3. 自动识别 /dev/nvmeXnY。
4. 如果是全新的模拟 namespace，则格式化为 ext4。
5. 挂载到 /srv/tokenfs/remote0。
6. 生成临时 TokenFS 配置，把 remote0 指向 /srv/tokenfs/remote0。
7. 启动 TokenFS。
8. 写入小文件，验证 local 层。
9. 写入 96 MiB token shard，触发 remote 溢写。
10. 读取校验内容。
11. 导出状态、指标和元数据报告。
```

报告位置：

```text
reports/nvmeof/latest/report.md
reports/nvmeof/latest/files.csv
reports/nvmeof/latest/status.txt
reports/nvmeof/latest/metrics.txt
```

## 判断是否成功

看到下面输出表示协议链路和 TokenFS 溢写路径都跑通：

```text
TokenFS NVMe-oF two-VM test passed.
```

同时可以查看元数据：

```bash
cat reports/nvmeof/latest/files.csv
```

你应该能看到类似：

```text
/gpu0/nvmeof-demo/local.tokens,0,local,...
/gpu0/nvmeof-demo/remote-spill.tokens,0,remote,/srv/tokenfs/remote0/gpu0/...
```

其中 `remote-spill.tokens` 的 `tier=remote`，并且物理路径位于 `/srv/tokenfs/remote0`，说明它不是落在本地模拟目录，而是落在 NVMe-oF 挂载后端。

## 接入真实实验室 SSD

真实环境到位后，Target 端一般由实验室存储服务器提供，不再需要 `setup_nvme_target.sh`。

需要拿到：

- SSD Target IP。
- NVMe/TCP 端口，通常为 `4420`。
- Subsystem NQN。
- 是否允许当前 GPU Host 连接。
- 远端 Namespace 是否是独占的。
- 设备是否已有文件系统，是否允许格式化。

然后在 Client 端执行：

```bash
TOKENFS_NVME_TARGET_IP=<真实 Target IP> \
TOKENFS_NVME_SUBNQN=<真实 Subsystem NQN> \
TOKENFS_NVME_MOUNT=/srv/tokenfs/remote0 \
  ./scripts/connect_nvme.sh
```

真实设备默认不格式化。只有确认这是全新的、可清空的测试 namespace 时，才允许使用：

```bash
--allow-format
```
