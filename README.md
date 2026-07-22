# TokenFS

TokenFS 是一个面向大规模机器学习 Token 数据的本地-远端分层文件系统原型。它通过 FUSE 提供统一的 POSIX 文件访问接口，为不同 GPU 分配相互隔离的本地存储配额；写入时优先使用本地 SSD，本地配额不足时自动溢写到远端后端。

当前项目同时支持两种远端形态：

```text
开发模拟：普通目录 /var/lib/tokenfs/remote-sim
协议模拟：双 Ubuntu VM，通过真实 NVMe/TCP 连接到 /srv/tokenfs/remote0
```

等实验室真实 SSD Target 到位后，只需要把 Target IP、端口、Subsystem NQN 和挂载点写入配置或环境变量，即可把远端后端切换到真实 NVMe-oF SSD。

上层训练或推理程序只需要访问统一路径：

```text
/mnt/tokenfs/gpu0/train-0001.tokens
/mnt/tokenfs/gpu1/train-0002.tokens
```

程序不需要关心文件最终落在本地目录还是远端目录。TokenFS 会在内部记录文件的逻辑路径、所属 GPU、存储层级、物理路径、文件大小、校验值和提交状态。

## 系统架构

```text
机器学习程序 / Token Loader
  |
  | open/read/write/fsync
  v
TokenFS FUSE 挂载点：/mnt/tokenfs
  |
  | 解析 /gpu0、/gpu1，检查 GPU 本地配额，维护 SQLite 元数据
  |
  +-- local 层：/var/lib/tokenfs/local/gpu0
  |           /var/lib/tokenfs/local/gpu1
  |
  +-- remote 层：
      开发模拟目录：/var/lib/tokenfs/remote-sim
      NVMe-oF 挂载：/srv/tokenfs/remote0
          |
          | nvme-tcp
          v
      远端 SSD Target / tokenfs-target VM
```

## 已实现能力

- FUSE 挂载，支持常用文件操作：`getattr`、`readdir`、`mkdir`、`create`、`open`、`read`、`write`、`truncate`、`rename`、`unlink`、`fsync`、`release`。
- `/gpu0` 和 `/gpu1` 两个逻辑命名空间，不同 GPU 使用独立本地目录和独立配额。
- 本地优先写入；当写入或 `truncate` 后的文件大小会超过对应 GPU 本地配额时，自动迁移到远端层。
- SQLite 元数据表，记录 `logical_path`、`gpu_id`、`tier`、`backend_id`、`physical_path`、`size_bytes`、`checksum`、`state`。
- 可靠写入状态模型：写入中为 `CREATING`，完成 `fsync` 和元数据更新后为 `COMMITTED`。
- 启动恢复：自动清理未完成写入记录和残留临时文件，避免半成品 Token 文件被当成有效数据。
- `fnv1a64` 文件校验值记录，用于确认已提交文件的内容状态。
- 管理工具 `tokenfsctl.py`，可以查看挂载状态、GPU 配额使用、local/remote 文件数量、后端目录和文件清单。
- 集成测试脚本，覆盖本地写入、远端溢写、GPU1 命名空间、校验值、删除清理和启动恢复。
- 性能测试脚本，自动生成 CSV、Markdown 和 HTML 报告。
- NVMe-oF Host 连接脚本，支持 dry-run、自动发现连接后的 `/dev/nvmeXnY`、显式格式化保护和挂载。
- NVMe-oF Target 模拟脚本，可以在第二台 Ubuntu VM 上用 Linux `nvmet` 导出 loop 文件作为远端 Namespace。
- 双 VM NVMe/TCP 测试脚本，验证 TokenFS 的远端溢写确实可以落到 NVMe-oF 挂载后端。

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
│   ├── check_environment.sh
│   ├── tokenfsctl.py
│   ├── integration_test.sh
│   ├── token_workload_test.sh
│   ├── smoke_test.sh
│   ├── v2_integration_test.sh
│   ├── reset_dev_state.sh
│   ├── connect_nvme.sh
│   ├── disconnect_nvme.sh
│   ├── setup_nvme_target.sh
│   ├── cleanup_nvme_target.sh
│   ├── nvmeof_loopback_test.sh
│   ├── nvmeof_two_vm_test.sh
│   ├── nvmeof_perf_test.sh
│   ├── perf_test.sh
│   └── perf_report.py
├── reports/
│   ├── perf/
│   │   └── latest/
│   │       ├── report.md
│   │       ├── report.html
│   │       └── summary.csv
│   └── token-workload/
│       └── latest/
│           ├── report.md
│           ├── summary.csv
│           ├── metrics.txt
│           └── files.csv
├── docs/
│   ├── research-plan.md
│   └── nvmeof-two-vm.md
└── src/
    └── main.cpp
```

## 环境准备

建议在 Ubuntu 24.04 LTS 虚拟机或服务器中运行：

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  cmake \
  ninja-build \
  git \
  fuse3 \
  libfuse3-dev \
  sqlite3 \
  libsqlite3-dev \
  libyaml-cpp-dev \
  fio \
  nvme-cli
```

当前项目使用 C++20、FUSE3、SQLite 和 yaml-cpp。

## 编译

```bash
cd ~/projects/tokenfs
cmake -S . -B build -G Ninja
cmake --build build
```

编译完成后会生成：

```text
build/tokenfs
```

## 启动和停止

启动：

```bash
cd ~/projects/tokenfs
./scripts/start_tokenfs.sh
```

默认挂载点：

```text
/mnt/tokenfs
```

停止：

```bash
./scripts/stop_tokenfs.sh
```

## 基本使用

```bash
mkdir -p /mnt/tokenfs/gpu0/demo
echo "hello tokenfs" > /mnt/tokenfs/gpu0/demo/a.tokens
cat /mnt/tokenfs/gpu0/demo/a.tokens
```

写入小文件时，默认落在本地层：

```text
/var/lib/tokenfs/local/gpu0/demo/a.tokens
```

当前开发配置中，每个 GPU 的本地配额是 64 MiB。写入超过配额的大文件会触发远端溢写：

```bash
truncate -s 80M /mnt/tokenfs/gpu0/big.tokens
```

实际文件会落到：

```text
/var/lib/tokenfs/remote-sim/gpu0/big.tokens
```

## 查看系统状态

推荐使用管理工具查看状态：

```bash
cd ~/projects/tokenfs
./scripts/tokenfsctl.py status
```

它会显示：

- 当前配置文件。
- 挂载点是否已经挂载。
- SQLite 元数据库是否存在。
- 文件记录总数、已提交数量、未完成数量。
- 每个 GPU 的本地目录、本地配额、本地已用空间。
- 每个 GPU 在元数据中记录的 local/remote 文件数量和容量。
- 远端后端目录是否存在、占用多少空间。

查看文件清单：

```bash
./scripts/tokenfsctl.py files
```

查看读写、命中率、溢写和预分配指标：

```bash
./scripts/tokenfsctl.py metrics
```

如果你想直接查看 SQLite，也可以执行：

```bash
sqlite3 /var/lib/tokenfs/metadata/tokenfs.db \
"select logical_path,gpu_id,tier,physical_path,size_bytes,checksum,state from files;"
```

字段含义：

```text
logical_path   用户看到的路径，例如 /gpu0/big.tokens
gpu_id         文件归属的 GPU 逻辑空间
tier           local 表示本地层，remote 表示远端层
physical_path  文件真实落盘位置
size_bytes     文件大小
checksum       文件校验值
state          COMMITTED 表示已经可靠提交
```

## 一键验证

运行集成测试：

```bash
cd ~/projects/tokenfs
./scripts/integration_test.sh
```

测试会自动完成：

- 清理开发环境。
- 编译 TokenFS。
- 启动 FUSE 挂载。
- 写入小文件，验证本地层。
- 写入大文件，验证远端溢写。
- 写入 `/gpu1` 文件，验证 GPU 命名空间隔离。
- 检查 SQLite 中的校验值和状态。
- 删除文件，验证物理文件和元数据都会清理。
- 人工制造一个 `CREATING` 状态的未完成文件，重启后验证自动恢复。

看到下面输出表示通过：

```text
TokenFS integration test passed.
```

## 环境检查

真实服务器到位后，先运行：

```bash
cd ~/projects/tokenfs
./scripts/check_environment.sh
```

它会检查：

- C++ 编译工具、CMake、Ninja。
- FUSE3 和 `/dev/fuse`。
- SQLite、fio、nvme-cli。
- 配置文件、挂载点、元数据库目录。
- 远端后端目录。
- NVMe-oF dry-run 路径。

## Token Workload 测试

TokenFS 提供一个更接近机器学习 Token 数据的 workload：

```bash
cd ~/projects/tokenfs
./scripts/token_workload_test.sh
```

它会模拟：

- token shard 文件。
- `fallocate` 预分配。
- 顺序写入。
- 顺序读取。
- 本地层和远端溢写。
- `/gpu0` 和 `/gpu1` 两个命名空间。

报告位置：

```text
reports/token-workload/latest/report.md
reports/token-workload/latest/summary.csv
reports/token-workload/latest/metrics.txt
reports/token-workload/latest/files.csv
```

## 性能测试和报告

运行：

```bash
cd ~/projects/tokenfs
./scripts/perf_test.sh
```

脚本会测试：

- 直接写本地后端目录。
- 直接写远端模拟目录。
- 通过 TokenFS 写本地层文件。
- 通过 TokenFS 写超过配额的大文件，触发远端溢写。
- 通过 TokenFS 读取本地层文件。
- 通过 TokenFS 读取远端层文件。

报告生成位置：

```text
reports/perf/latest/report.md
reports/perf/latest/report.html
reports/perf/latest/summary.csv
```

说明：

```text
report.md    适合在 GitHub 上直接查看
report.html  带条形图，适合截图放进汇报
summary.csv  适合后续导入 Excel 或继续画图
```

当前远端仍是目录模拟，因此性能结果主要用于观察 FUSE 开销、本地优先策略和远端溢写路径。接入真实 NVMe-oF 后，需要重新运行同一脚本生成真实远端 SSD 数据。

## 双 VM NVMe-oF 性能基线

双 VM NVMe-oF 链路跑通后，可以运行更接近论文实验的基线测试。假设 Target VM IP 是 `192.168.64.3`：

```bash
cd ~/projects/tokenfs
TOKENFS_NVME_TARGET_IP=192.168.64.3 ./scripts/nvmeof_perf_test.sh
```

该脚本会比较：

```text
直接读写本地目录
直接读写 NVMe-oF 挂载目录
通过 TokenFS 写入/读取本地层文件
通过 TokenFS 触发远端溢写并从 NVMe-oF 后端读取
```

报告生成位置：

```text
reports/nvmeof-perf/latest/report.md
reports/nvmeof-perf/latest/report.html
reports/nvmeof-perf/latest/summary.csv
reports/nvmeof-perf/latest/metrics.txt
reports/nvmeof-perf/latest/files.csv
```

这组结果可以证明 TokenFS 已经接入真实 NVMe/TCP 协议路径，并能观察 FUSE 层和策略层带来的相对开销。由于当前 Target 后端仍是虚拟机 loop 文件和虚拟网络，因此它适合作为工程验证和论文预实验，最终性能数据仍需要在真实 SSD 与实验室网络上重新采集。

## 配置文件

默认配置文件：

```text
config/tokenfs.dev.yaml
```

核心配置：

```yaml
filesystem:
  mount_point: /mnt/tokenfs
  metadata_db: /var/lib/tokenfs/metadata/tokenfs.db

policy:
  mode: local_first
  checksum: fnv1a64

gpus:
  - gpu_id: 0
    logical_root: /gpu0
    local_root: /var/lib/tokenfs/local/gpu0
    local_quota_mib: 64
    remote_backend: remote0

  - gpu_id: 1
    logical_root: /gpu1
    local_root: /var/lib/tokenfs/local/gpu1
    local_quota_mib: 64
    remote_backend: remote0

backends:
  - id: remote0
    type: directory
    root: /var/lib/tokenfs/remote-sim
```

要新增 GPU，可以在 `gpus` 中增加新的条目，例如 `/gpu2`，并给它独立的 `local_root` 和 `local_quota_mib`。

## 接入真实 NVMe-oF

开发时远端层可以先使用：

```text
/var/lib/tokenfs/remote-sim
```

拿到真实 SSD Target 信息后，可以把远端层替换成：

```text
/srv/tokenfs/remote0
```

需要的信息：

- SSD Target IP。
- NVMe/TCP 端口，通常是 `4420`。
- Subsystem NQN。
- 连接后出现的设备名，例如 `/dev/nvme1n1`。
- 挂载点，例如 `/srv/tokenfs/remote0`。

连接脚本支持从配置文件读取，也支持用环境变量覆盖。真实设备连接示例：

```bash
export TOKENFS_NVME_TARGET_IP=<SSD_TARGET_IP>
export TOKENFS_NVME_SUBNQN=<SUBSYSTEM_NQN>
export TOKENFS_NVME_MOUNT=/srv/tokenfs/remote0

./scripts/connect_nvme.sh
```

脚本会自动执行 `nvme discover`、`nvme connect`，并尝试根据 Subsystem NQN 自动识别连接后的 `/dev/nvmeXnY`。

也可以直接读取配置文件并预演命令：

```bash
./scripts/connect_nvme.sh --config config/tokenfs.dev.yaml --backend remote0 --dry-run
```

断开：

```bash
./scripts/disconnect_nvme.sh
```

同样支持 dry-run：

```bash
./scripts/disconnect_nvme.sh --config config/tokenfs.dev.yaml --backend remote0 --dry-run
```

注意：脚本默认不会自动执行 `mkfs`，也就是不会自动格式化设备。只有确认这是全新的、可清空的测试 namespace 时，才允许显式加：

```bash
--allow-format
```

## 双 VM NVMe-oF 测试

如果没有真实实验室 SSD，可以用两台 Ubuntu VM 先跑通真正的 NVMe/TCP 协议：

```text
tokenfs-dev     运行 TokenFS + NVMe/TCP Host
tokenfs-target  运行 Linux NVMe/TCP Target
```

在 Target VM 上启动模拟远端 SSD：

```bash
cd ~/projects/tokenfs
sudo ./scripts/setup_nvme_target.sh \
  --target-ip 0.0.0.0 \
  --port 4420 \
  --subnqn nqn.2026-07.local.tokenfs:remote0 \
  --image /var/lib/tokenfs/nvmeof-target/remote0.img \
  --size 20G
```

在 Client VM 上运行双 VM 测试。假设 Target IP 是 `192.168.64.3`：

```bash
cd ~/projects/tokenfs
TOKENFS_NVME_TARGET_IP=192.168.64.3 ./scripts/nvmeof_two_vm_test.sh
```

测试通过后会生成：

```text
reports/nvmeof/latest/report.md
reports/nvmeof/latest/files.csv
reports/nvmeof/latest/status.txt
reports/nvmeof/latest/metrics.txt
```

更详细说明见：

```text
docs/nvmeof-two-vm.md
```

接入真实 NVMe-oF 后，把配置文件中的远端后端根目录改为真实挂载点：

```yaml
backends:
  - id: remote0
    type: directory
    root: /srv/tokenfs/remote0
```

## 项目边界

TokenFS 当前是课程/研究原型，不是生产级分布式文件系统。

当前暂不支持：

- 多台 GPU Host 同时写同一个文件。
- 多 MDS。
- Raft。
- SPDK。
- RDMA。
- 裸 LBA extent 管理。
- 完整 POSIX 文件锁语义。

当前重点是把 FUSE 接口、本地优先策略、远端溢写、SQLite 元数据、可靠写入、启动恢复、性能测试和 NVMe-oF 接入流程打通。真实 SSD Target 信息到位后，主要改配置和运行连接脚本，不需要重写 TokenFS 主体逻辑。

## 研究计划

论文方向和优化路线见：

```text
docs/research-plan.md
```
