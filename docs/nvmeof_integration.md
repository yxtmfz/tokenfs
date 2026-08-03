# AURA-KV / TokenFS 的 NVMe-oF 接入方式

当前算法不写死 IP、端口、RDMA、TCP 或 SPDK。真实环境到位后，上层策略只需要知道“远端后端挂载目录”和采集到的性能指标。

## 当前后端模式

```text
LocalDirectoryBackend       本地 SSD 目录
SimulatedRemoteBackend      普通目录模拟远端层
MountedNVMeOFBackend        已挂载的 NVMe-oF 目录
```

MountedNVMeOFBackend 不在策略中直接执行 NVMe/TCP 协议，而是依赖启动脚本把远端 Namespace 挂载为目录：

```text
/srv/tokenfs/remote0
```

TokenFS 和 AURA-KV 只通过 POSIX 文件接口访问该目录。

## 真实环境所需信息

```text
Target IP
NVMe-oF transport: tcp 或 rdma
端口，通常 4420
Subsystem NQN
Host NQN / ACL
连接后设备名
远端挂载点
本地 SSD 路径
节点 ID 和 GPU 拓扑
```

## 已有脚本

```text
scripts/connect_nvme.sh
scripts/disconnect_nvme.sh
scripts/setup_nvme_target.sh
scripts/nvmeof_two_vm_test.sh
scripts/nvmeof_loopback_test.sh
```

## 注意

多个计算节点不能把同一个普通 ext4 Namespace 同时读写挂载。真实共享方案应采用：

```text
每节点独立 Namespace
或远端主副本服务化
或集群文件系统
或由 TokenFS/AURA-KV 管理共享语义
```

当前项目默认远端层是权威 KV Cache 对象池，不把同一个 ext4 裸设备随意多机挂载。

