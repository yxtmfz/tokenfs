# TokenFS

TokenFS 是一个面向大规模机器学习 Token 数据的 GPU 感知本地-远端分层文件系统原型。它通过 FUSE 提供统一 POSIX 文件接口，为不同 GPU 分配独立本地 SSD 配额；写入时优先使用 GPU 本地目录，本地容量不足时自动溢写到远端后端。远端后端在开发阶段可以是普通目录，在双 VM 或真实环境中可以切换为 NVMe-oF 挂载目录。

当前版本已经按“未知真实 IP 信息时可做到的最完整状态”收口：代码、说明文档、数据结果分成三大板块。真实 SSD Target 的 IP、端口、NQN 到位后，只需要改配置和运行连接脚本，不需要重写 TokenFS 主体逻辑。

## 一、代码板块

### 核心代码

```text
src/main.cpp
```

核心能力：

- FUSE 文件系统：支持 `getattr`、`readdir`、`mkdir`、`create`、`open`、`read`、`write`、`truncate`、`rename`、`unlink`、`fsync`、`release`。
- GPU namespace：默认支持 `/gpu0`、`/gpu1`，每个 GPU 有独立本地目录和本地配额。
- 本地优先：本地空间足够时写本地。
- 远端溢写：本地不足时把文件放到远端后端。
- 热点提升：远端文件被多次读取后，可迁回本地。
- 顺序预取：读取连续编号 shard 时，可提前把下一片 shard 拉回本地。
- Cost-aware 淘汰：本地不足时，优先淘汰访问少、较久未访问、体积较大的冷文件。
- SQLite 元数据：记录逻辑路径、GPU、local/remote 层级、物理路径、文件大小、checksum、状态和读取次数。
- 一致性恢复：启动时清理未完成写入，避免半成品文件被当成有效 token 数据。

### 配置文件

```text
config/tokenfs.dev.yaml
```

当前开发配置使用目录模拟远端：

```text
local:  /var/lib/tokenfs/local/gpu0
remote: /var/lib/tokenfs/remote-sim/gpu0
mount:  /mnt/tokenfs
```

真实环境到位后，把远端配置切换为 NVMe-oF 挂载目录：

```yaml
backends:
  - id: remote0
    type: nvmeof
    root: /srv/tokenfs/remote0
    nvme_transport: tcp
    nvme_target_ip: "<SSD_TARGET_IP>"
    nvme_port: "4420"
    nvme_subnqn: "<SUBSYSTEM_NQN>"
    nvme_device: "/dev/nvmeXnY"
    nvme_mount: /srv/tokenfs/remote0
    nvme_filesystem: ext4
```

### 脚本入口

日常使用只需要记住这些：

```bash
./scripts/check_environment.sh        # 检查 Ubuntu/FUSE/NVMe 工具环境
./scripts/start_tokenfs.sh            # 启动并挂载 TokenFS
./scripts/stop_tokenfs.sh             # 停止并卸载 TokenFS
./scripts/tokenfsctl.py status        # 查看系统状态
./scripts/tokenfsctl.py files         # 查看文件元数据
./scripts/tokenfsctl.py metrics       # 查看读写和策略指标
./scripts/tokenfsctl.py check         # 检查元数据和物理文件一致性
./scripts/integration_test.sh         # 核心功能测试
./scripts/strategy_matrix_test.sh     # 策略矩阵/消融实验
./scripts/nvmeof_two_vm_test.sh       # 双 VM NVMe-oF 协议路径测试
```

其他脚本是专项测试或部署辅助：

```text
connect_nvme.sh / disconnect_nvme.sh      连接和断开 NVMe-oF 后端
setup_nvme_target.sh / cleanup_nvme_target.sh
                                          在第二台 VM 上模拟 NVMe-oF Target
promote_test.sh                           热点提升专项测试
prefetch_test.sh                          顺序预取专项测试
eviction_test.sh                          Cost-aware 淘汰专项测试
fault_injection_test.sh                   故障注入测试
random_io_test.sh                         小块随机 I/O 测试
token_workload_test.sh                    token shard workload 测试
```

## 二、说明文档板块

本仓库只保留这一份主说明文档：`README.md`。

### 项目定位

TokenFS 不是重复实现 CephFS、BeeGFS、3FS 这类通用分布式文件系统，而是聚焦一个更窄但更适合论文切入的场景：

```text
大模型训练/推理中的 prompt token、token shard、可复用中间数据，
在 GPU 本地 SSD 容量有限、远端 NVMe-oF SSD 容量更大的条件下，
如何自动放置、迁移、预取和淘汰，减少 GPU 等待数据的时间。
```

### 当前差异化能力

- GPU-aware：不同 GPU 的本地空间和访问统计相互隔离。
- Token workload-aware：围绕大文件 shard、连续编号 shard、重复热点读取设计策略。
- Local-first + Remote-spill：本地优先，空间不足时远端扩展容量。
- Hot promotion：远端热点数据自动回本地。
- Sequential prefetch：连续 shard 自动预取下一片。
- Cost-aware eviction：不是简单 LRU/LFU，而是综合热度、时间和大小选择淘汰对象。
- Metrics-driven：所有策略都有可观测指标，方便做论文实验。
- NVMe-oF-ready：没有真实 IP 时可以 dry-run 和双 VM 验证；真实 IP 到位后改配置即可接入。

### 编译和运行

Ubuntu 24.04 LTS 推荐安装：

```bash
sudo apt update
sudo apt install -y \
  build-essential cmake ninja-build git \
  fuse3 libfuse3-dev \
  sqlite3 libsqlite3-dev libyaml-cpp-dev \
  fio nvme-cli
```

编译：

```bash
cmake -S . -B build -G Ninja
cmake --build build
```

启动：

```bash
./scripts/start_tokenfs.sh
```

使用：

```bash
mkdir -p /mnt/tokenfs/gpu0/demo
echo "hello tokenfs" > /mnt/tokenfs/gpu0/demo/a.tokens
cat /mnt/tokenfs/gpu0/demo/a.tokens
```

停止：

```bash
./scripts/stop_tokenfs.sh
```

### 未知 IP 时怎么做到可验证

现在没有真实 SSD Target IP，并不意味着项目只能停留在理论层面。当前能真实验证：

- FUSE 文件系统功能是否正确。
- GPU 本地配额是否生效。
- 本地优先和远端溢写逻辑是否正确。
- 热点提升、顺序预取、Cost-aware 淘汰是否按预期改变元数据和物理位置。
- checksum、启动恢复、一致性检查、故障注入是否有效。
- 双 VM 环境下真实 NVMe/TCP 协议路径是否能跑通。

当前不能验证：

- 真实 SSD 和真实网络下的绝对带宽。
- 真实 P95/P99 延迟。
- 真实 GPU 等待数据时间。
- 真实多 GPU 并发下的性能上限。

因此当前实验结论应该表述为：

```text
当前阶段验证系统设计、策略逻辑、工程闭环和实验框架；
真实 NVMe-oF 环境到位后，复用同一套脚本重新采集最终性能数据。
```

### 真实 NVMe-oF 接入流程

第二台 VM 或真实 SSD Target 准备好后：

```bash
# Target 侧，模拟 NVMe-oF Target
sudo ./scripts/setup_nvme_target.sh

# Client 侧，连接远端 Namespace
sudo ./scripts/connect_nvme.sh config/tokenfs.dev.yaml

# Client 侧，运行 TokenFS + NVMe-oF 测试
./scripts/nvmeof_two_vm_test.sh
./scripts/nvmeof_perf_test.sh
```

真实实验室环境只需要替换：

```text
SSD Target IP
NVMe/TCP 端口
Subsystem NQN
/dev/nvmeXnY 设备名
挂载目录 /srv/tokenfs/remote0
```

### 论文实验建议

建议最终对比组：

```text
Baseline 1：直接本地 SSD
Baseline 2：直接 NVMe-oF 远端 SSD
Baseline 3：TokenFS 本地优先 + 远端溢写
Ours 1：TokenFS + 热点提升
Ours 2：TokenFS + 顺序预取
Ours 3：TokenFS + 热点提升 + 顺序预取 + Cost-aware 淘汰
```

建议指标：

```text
端到端 token workload 耗时
本地读命中率
远端读取次数和远端读取字节数
平均读写延迟
P95/P99 延迟
IOPS
溢写次数
热点提升次数
预取成功次数
本地淘汰次数
GPU 等待数据时间，真实 GPU 环境到位后补充
```

## 三、数据结果板块

最新结果统一放在：

```text
reports/latest/final-report.md
```

该文件是当前仓库唯一需要直接查看的数据结果入口，已经整合：

- token shard workload 结果。
- 本地/远端读写指标。
- SQLite 文件分布。
- 策略矩阵消融实验。
- 当前结果能说明什么、不能说明什么。

重新生成当前结果：

```bash
./scripts/token_workload_test.sh /tmp/tokenfs-workload-report
./scripts/strategy_matrix_test.sh /tmp/tokenfs-strategy-matrix
```

如果要更新仓库里的最终报告，把新结果整理进 `reports/latest/final-report.md` 即可。

## 当前完成度

在没有真实 SSD IP 的条件下，TokenFS 已经做到：

- 可编译。
- 可挂载。
- 可读写。
- 可分 GPU 管理本地配额。
- 可本地优先和远端溢写。
- 可热点提升、顺序预取和 Cost-aware 淘汰。
- 可连接双 VM NVMe-oF 模拟环境。
- 可进行一致性检查、故障注入和策略矩阵实验。
- 可在真实环境到位后通过配置切换到真实 NVMe-oF 后端。

下一步真正需要的是实验室真实环境：

```text
GPU 服务器 IP
SSD Target IP
Subsystem NQN
Namespace 设备名
远端 SSD 容量和文件系统
网络带宽、MTU、是否 RDMA
真实 token 数据规模和访问模式
```

拿到这些信息后，重点不是改代码，而是跑真实实验和调参。
