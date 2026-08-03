# NVMe-oF 接入说明

## 1. 本文解决的问题

本文解释未来导师给出真实 IP、NQN 和设备信息后，AURA-KV/TokenFS 如何接入真实 NVMe-oF 环境，同时保持算法层与传输层解耦。

## 2. 基础概念

NVMe-oF 是 NVMe over Fabrics，即通过网络访问远端 NVMe 存储。

| 概念 | 中文解释 | 本项目作用 |
|---|---|---|
| Initiator/Host | 发起连接的客户端 | GPU 计算节点 |
| Target | 提供存储的服务端 | 远端 SSD 服务器 |
| Namespace | 暴露给 Host 的逻辑块设备 | 远端容量层 |
| NVMe/TCP | 通过 TCP 传输 NVMe 命令 | 易部署，适合当前实验 |
| NVMe/RDMA | 通过 RDMA 传输 | 延迟更低，后续优化 |
| SPDK | 用户态高性能存储栈 | 后续可能比较 |

## 3. 挂载目录模式

AURA-KV 不在算法层直接写 NVMe 命令。连接流程由脚本完成：

```text
nvme discover
nvme connect
等待 /dev/nvmeXnY
mkfs 仅首次手动确认
mount 到 /srv/tokenfs/remote0
TokenFS/AURA-KV 通过 POSIX 文件接口访问
```

这样策略层只依赖：

```text
remote_mount_path
remote_read_p99_ms
remote_bandwidth
queue_depth
```

不依赖 TCP/RDMA/IP 写死。

## 4. 需要导师提供的信息

```text
SSD Target IP
端口，通常 4420
transport: tcp 或 rdma
Subsystem NQN
Host NQN / ACL / 认证方式
Namespace 是否独占
设备名或 by-id 路径
是否已有文件系统
本地 SSD 路径
节点/GPU 拓扑
```

## 5. 避免误格式化

普通启动脚本不得默认执行 `mkfs`。首次初始化必须显式设置：

```bash
ALLOW_FORMAT=1 ./scripts/...
```

连接后先检查：

```bash
nvme list
lsblk
blkid
mount
```

确认不是系统盘、不是已有重要数据盘后才能格式化。

## 6. 指标采集

真实环境需要采集：

```text
fio local/remote P50/P95/P99
远端带宽 MiB/s
IOPS
NVMe 队列深度
TCP 重传
Target CPU
Host CPU
后台迁移期间前台 P99
```

这些指标将作为 AURA-KV 公式中的 remote penalty、bandwidth price 和 SLO price 输入。

## 7. 当前脚本

```text
scripts/connect_nvme.sh
scripts/disconnect_nvme.sh
scripts/setup_nvme_target.sh
scripts/nvmeof_two_vm_test.sh
scripts/nvmeof_loopback_test.sh
```

## 8. 实现状态

| 功能 | 状态 | 对应代码 | 对应测试 | 未完成原因 | 后续计划 |
|---|---|---|---|---|---|
| NVMe-oF 配置字段 | Implemented | `config/tokenfs.dev.yaml` | dry-run | 无 | 用真实值替换占位符 |
| 连接脚本 | Partial | `scripts/connect_nvme.sh` | loopback/two-vm | 缺真实 target | 真实环境复测 |
| MountedNVMeOFBackend | Partial | 目录后端模式 | FUSE 测试 | 尚未独立类化 | 抽象 StorageBackend |
| P99 采集 | Planned | 无 | 无 | 缺真实设备 | fio + token workload |
