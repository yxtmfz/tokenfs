# TokenFS

TokenFS 是一个面向大规模机器学习 Token 数据的本地-远端分层文件系统原型。

它通过 FUSE 提供统一的 POSIX 文件访问接口，为不同 GPU 分配相互隔离的本地存储配额。数据写入时优先使用本地 SSD；如果对应 GPU 的本地空间不足，就自动溢写到远端存储。当前开发阶段使用普通目录模拟远端 SSD，后续可以把模拟目录替换为通过 NVMe-oF 挂载的远端 SSD。

## 项目定位

TokenFS 的目标不是一开始就做完整通用分布式文件系统，而是先解决机器学习 Token 数据场景中的一个具体问题：

```text
上层训练或推理程序
  |
  | open/read/write /mnt/tokenfs/gpu0/xxx.tokens
  v
TokenFS FUSE 文件系统
  |
  | 判断所属 GPU、本地配额、文件元数据
  |
  +--> 本地空间够：写入本地目录
  |
  +--> 本地空间不足：写入远端后端
```

上层程序只需要访问统一路径，例如：

```text
/mnt/tokenfs/gpu0/train-0001.tokens
/mnt/tokenfs/gpu1/train-0002.tokens
```

不需要关心文件实际在本地还是远端。

## 当前已经实现的能力

当前版本已经实现：

- `/gpu0` 和 `/gpu1` 两个逻辑命名空间。
- 本地优先存储，默认目录为 `/var/lib/tokenfs/local/gpu*`。
- 远端模拟存储，默认目录为 `/var/lib/tokenfs/remote-sim`。
- SQLite 元数据表，记录逻辑路径、所属 GPU、存储层级、后端 ID、物理路径、文件大小、校验值和状态。
- 当写入或 `truncate` 超过 GPU 本地配额时，自动从本地溢写到远端。
- 第二版写入状态模型：`CREATING` 和 `COMMITTED`。
- 启动恢复：自动清理未完成写入和临时文件。
- `fnv1a64` 文件校验值记录，用于验证已提交文件的内容状态。
- NVMe-oF 连接脚本框架，后续拿到 SSD Target IP、NQN 和设备名后可以接入真实远端 SSD。

## 目录结构

```text
tokenfs/
├── CMakeLists.txt
├── README.md
├── config/
│   └── tokenfs.dev.yaml
├── scripts/
│   ├── start_tokenfs.sh
│   ├── stop_tokenfs.sh
│   ├── smoke_test.sh
│   ├── v2_integration_test.sh
│   ├── reset_dev_state.sh
│   ├── connect_nvme.sh
│   ├── disconnect_nvme.sh
│   ├── perf_test.sh
│   └── perf_report.py
├── reports/
│   └── perf/
│       └── latest/
│           ├── report.md
│           ├── report.html
│           └── summary.csv
└── src/
    └── main.cpp
```

## 编译方法

在 Ubuntu 虚拟机中进入项目目录：

```bash
cd ~/projects/tokenfs
```

编译：

```bash
cmake -S . -B build -G Ninja
cmake --build build
```

编译完成后会生成：

```text
build/tokenfs
```

## 运行方法

先启动 TokenFS：

```bash
./scripts/start_tokenfs.sh
```

默认挂载点是：

```text
/mnt/tokenfs
```

然后可以像操作普通目录一样操作它：

```bash
mkdir -p /mnt/tokenfs/gpu0/demo
echo hello > /mnt/tokenfs/gpu0/demo/a.tokens
cat /mnt/tokenfs/gpu0/demo/a.tokens
```

停止 TokenFS：

```bash
./scripts/stop_tokenfs.sh
```

## 一键验证第二版

最推荐直接运行第二版集成测试：

```bash
cd ~/projects/tokenfs
./scripts/v2_integration_test.sh
```

如果最后看到：

```text
TokenFS v2 integration test passed.
```

说明第二版核心功能验证通过。

这个测试会自动完成：

- 清理开发环境。
- 编译 TokenFS。
- 挂载 FUSE 文件系统。
- 写入一个小文件，验证本地写入。
- 写入一个超过本地配额的大文件，验证远端溢写。
- 检查 SQLite 中是否记录了 checksum。
- 删除文件，验证物理文件和元数据都会清理。
- 人工制造一个 `CREATING` 状态的未完成文件，重启后验证自动恢复清理。

## 查看元数据

TokenFS 使用 SQLite 保存元数据，默认数据库路径是：

```text
/var/lib/tokenfs/metadata/tokenfs.db
```

查看文件元数据：

```bash
sqlite3 /var/lib/tokenfs/metadata/tokenfs.db \
"select logical_path,gpu_id,tier,physical_path,size_bytes,checksum,state from files;"
```

示例结果：

```text
/gpu0/big.tokens|0|remote|/var/lib/tokenfs/remote-sim/gpu0/big.tokens|83886080|fnv1a64:...|COMMITTED
```

重点看：

```text
tier=local      表示文件在本地层
tier=remote     表示文件已经溢写到远端层
state=COMMITTED 表示文件已经完成可靠提交
checksum=...    表示记录了文件校验信息
```

## 元数据状态模型

TokenFS 当前使用一个简单的文件生命周期：

```text
CREATING
  文件已经创建或正在写入，但尚未可靠提交

COMMITTED
  文件已经 fsync，并且元数据已经更新完成
```

启动时，TokenFS 会清理长期停留在 `CREATING` 状态的记录和对应物理文件。这样可以避免“写到一半崩溃”的坏文件被当成有效 Token 数据使用。

## 本地和远端目录

当前开发环境中的默认目录：

```text
本地 GPU0：/var/lib/tokenfs/local/gpu0
本地 GPU1：/var/lib/tokenfs/local/gpu1
远端模拟： /var/lib/tokenfs/remote-sim
```

配置文件是：

```text
config/tokenfs.dev.yaml
```

当前为了方便测试，本地配额设置为 64 MiB：

```yaml
gpus:
  - gpu_id: 0
    local_quota_mib: 64

  - gpu_id: 1
    local_quota_mib: 64
```

所以写入 80 MiB 文件时，会触发远端溢写。

## 接入真实 NVMe-oF 的方式

当前版本还没有真实 SSD Target 信息，所以远端层先用普通目录模拟：

```text
/var/lib/tokenfs/remote-sim
```

后续拿到真实 NVMe-oF 信息后，可以把远端层替换为：

```text
/srv/tokenfs/remote0
```

真实接入时需要的信息包括：

- SSD Target IP
- NVMe/TCP 端口，通常是 `4420`
- Subsystem NQN
- 连接后出现的设备名，例如 `/dev/nvme1n1`
- 挂载点，例如 `/srv/tokenfs/remote0`

示例：

```bash
export TOKENFS_NVME_TARGET_IP=<SSD_TARGET_IP>
export TOKENFS_NVME_SUBNQN=<SUBSYSTEM_NQN>
export TOKENFS_NVME_DEVICE=/dev/nvmeXnY
export TOKENFS_NVME_MOUNT=/srv/tokenfs/remote0

./scripts/connect_nvme.sh
```

断开：

```bash
./scripts/disconnect_nvme.sh
```

注意：脚本不会自动执行 `mkfs`，也就是不会自动格式化设备。真实 SSD 是否需要格式化，必须单独确认后手动操作，避免误删数据。

## 当前边界

当前 TokenFS 仍是课程/研究原型，不是生产级分布式文件系统。

当前暂不支持：

- 多台 GPU Host 同时写同一个文件。
- 多 MDS。
- Raft。
- SPDK。
- RDMA。
- 裸 LBA extent 管理。
- 完整 POSIX 文件锁语义。

当前重点是先把：

```text
FUSE 接口
本地优先策略
远端溢写策略
SQLite 元数据
可靠写入状态
启动恢复
NVMe-oF 接入脚本
```

这条主线做稳。

## 推荐验证顺序

第一次查看项目时，建议按这个顺序：

```bash
cd ~/projects/tokenfs
./scripts/v2_integration_test.sh
sqlite3 /var/lib/tokenfs/metadata/tokenfs.db \
"select logical_path,tier,size_bytes,checksum,state from files;"
```

如果测试通过，并且能看到 `remote`、`fnv1a64`、`COMMITTED`，说明第二版核心逻辑是正常的。

## 第三版：性能测试和可视化报告

第三版加入了性能测试脚本和自动报告生成能力。

运行：

```bash
cd ~/projects/tokenfs
./scripts/perf_test.sh
```

脚本会自动完成：

- 清理开发环境。
- 编译 TokenFS。
- 启动 FUSE 挂载。
- 测试直接写本地后端目录。
- 测试直接写远端模拟目录。
- 测试通过 TokenFS 写本地层文件。
- 测试通过 TokenFS 写超过配额的大文件，触发远端溢写。
- 测试通过 TokenFS 读取本地层文件。
- 测试通过 TokenFS 读取远端层文件。
- 生成 CSV、Markdown 和 HTML 报告。

报告路径：

```text
reports/perf/latest/report.md
reports/perf/latest/report.html
reports/perf/latest/summary.csv
```

其中：

```text
report.md    适合在 GitHub 上直接查看
report.html  带条形图，更适合截图放进汇报
summary.csv  适合后续导入 Excel 或画图
```

注意：当前远端仍然是目录模拟，因此第三版性能数据主要用于观察 FUSE 开销、本地优先策略和远端溢写路径；接入真实 NVMe-oF 后，需要重新运行同一脚本生成真实远端 SSD 数据。
