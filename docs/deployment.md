# 部署与配置

本文说明本地开发、双 VM NVMe-oF 和实验室 NVMe-oF 的部署入口。

## 1. Ubuntu 环境

推荐 Ubuntu 24.04 LTS：

```bash
sudo apt update
sudo apt install -y build-essential cmake ninja-build pkg-config \
  fuse3 libfuse3-dev sqlite3 libsqlite3-dev libyaml-cpp-dev \
  python3 fio nvme-cli
```

构建：

```bash
cmake -S . -B build -G Ninja
cmake --build build
```

## 2. TokenFS 开发模式

初始化：

```bash
./scripts/reset_dev_state.sh /mnt/tokenfs
```

启动：

```bash
./scripts/start_tokenfs.sh config/tokenfs.dev.yaml /mnt/tokenfs
```

查看：

```bash
./scripts/tokenfsctl.py status
./scripts/tokenfsctl.py files
./scripts/tokenfsctl.py metrics
```

停止：

```bash
./scripts/stop_tokenfs.sh /mnt/tokenfs
```

## 3. 配置文件

主要配置：

```text
config/tokenfs.dev.yaml
```

关键字段：

| 字段 | 含义 |
|---|---|
| `filesystem.mount_point` | FUSE 挂载点 |
| `filesystem.metadata_db` | SQLite 元数据文件 |
| `gpus[].local_root` | 某个 GPU 的本地缓存目录 |
| `gpus[].local_quota_gib` | 逻辑本地配额 |
| `backends[].type` | `directory` 或 `nvmeof` |
| `backends[].root` | 远端后端挂载目录 |

真实 NVMe-oF 示例：

```yaml
backends:
  - id: remote0
    type: nvmeof
    root: /srv/tokenfs/remote0
    nvme_target_ip: "<SSD Target IP>"
    nvme_transport: tcp
    nvme_port: "4420"
    nvme_subnqn: "<Subsystem NQN>"
    nvme_device: "/dev/nvmeXnY"
    nvme_mount: /srv/tokenfs/remote0
```

## 4. 双 VM NVMe-oF

Target VM：

```bash
cd ~/projects/tokenfs
sudo ./scripts/setup_nvme_target.sh --target-ip 0.0.0.0 --size 20G
```

Client VM：

```bash
cd ~/projects/tokenfs
./scripts/nvmeof_two_vm_test.sh <TARGET_VM_IP>
./scripts/nvmeof_perf_test.sh <TARGET_VM_IP>
```

这条路径会真实使用 Linux `nvme-tcp` Host 和 `nvmet` Target。

## 5. 实验室 NVMe-oF

当前推荐的真实实验形态不是继续依赖双 VM Target，而是：

```text
Ubuntu VM / 内网客户端
  ├── TokenFS / AURA-KV
  ├── gpu0/gpu1/gpu2 本地缓存目录
  └── NVMe/TCP Host
        ↓
    /srv/tokenfs/remote0
        ↓
远端 NVMe/TCP Target
```

这里的 `gpu0/gpu1/gpu2` 是逻辑 GPU 节点，用于模拟多 GPU KV Cache 的访问分布和本地副本放置；远端 `/srv/tokenfs/remote0` 必须是通过 NVMe-oF 挂载出来的真实远端目录。

当前已排查到的边界：

```text
本地 UTM VM:
  tokenfs-dev  192.168.64.2
  tokenfs-target 192.168.64.3
  网络模式: Shared/NAT

老师内网:
  nvm-jump-public 可登录
  从跳板机内部可以访问 28.10.10.13:4420
  28.10.10.14:4420 当前不可达

阻塞点:
  Mac 本机和 UTM VM 当前都不能直连 28.10.10.13:4420。
  SSH 跳板能登录，不等于 NVMe/TCP 能直连。
```

因此，切换到老师物理远端 SSD 前，必须先让 Ubuntu 客户端位于能访问 `28.10.10.13:4420` 的网络里。最直接的方法是把 UTM 网卡从 `Shared` 改成 `Bridged`，或者使用老师提供的真实内网 Ubuntu 客户端。

### 5.1 准备配置

复制示例配置：

```bash
cp config/tokenfs.nvmeof.example.yaml config/tokenfs.nvmeof.yaml
```

至少修改：

```yaml
backends:
  - id: remote0
    type: nvmeof
    root: /srv/tokenfs/remote0
    nvme_transport: tcp
    nvme_target_ip: "<远端 NVMe/TCP Target IP>"
    nvme_port: "4420"
    nvme_subnqn: "<Subsystem NQN>"
    nvme_device: "/dev/nvmeXnY"
    nvme_mount: /srv/tokenfs/remote0
```

如果 `nvme_device` 还不知道，可以先保留 `/dev/nvmeXnY`，连接后由脚本自动识别；如果自动识别失败，再根据 `nvme list` 输出手动填写。

连接前先 dry-run：

```bash
./scripts/connect_nvme.sh --config config/tokenfs.nvmeof.yaml --dry-run
```

连接前先做只读网络探测：

```bash
./scripts/lab_network_probe.sh \
  --config config/tokenfs.nvmeof.yaml \
  --target-ip 28.10.10.13 \
  --port 4420
```

合格状态应该至少包含：

```text
[OK] TCP 28.10.10.13:4420 is reachable from this client
[OK] nvme-cli is installed
```

如果这里显示 `TCP ... is not reachable`，就不要继续跑真实实验。此时问题在客户端网络路径，不在 AURA-KV 策略代码。

真实连接：

```bash
sudo ./scripts/connect_nvme.sh \
  --config config/tokenfs.nvmeof.yaml \
  --backend remote0 \
  --chown-current
```

验证挂载：

```bash
findmnt --target /srv/tokenfs/remote0
nvme list
df -h /srv/tokenfs/remote0
```

合格状态应该是：

```text
/srv/tokenfs/remote0 的挂载源是 /dev/nvme...
nvme list 能看到远端 namespace
```

如果 `/srv/tokenfs/remote0` 只是普通目录或来自 `/dev/vda`、`/dev/sda`，就不能把结果写成真实 NVMe-oF。

### 5.2 单客户端多逻辑 GPU 实验

挂载成功后，直接运行当前推荐入口：

```bash
TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/lab_single_client_multigpu_experiment.sh
```

它会生成：

```text
reports/latest/paper-experiments/08_lab_single_client_multigpu/
├── lab_single_client_multigpu_report.md
├── environment_evidence.txt
├── 01_environment_gap/
├── 02_single_run_speed/
└── 03_repeat_speed/
```

这份结果是当前最适合论文汇报的真实系统结果：远端层是真实 NVMe-oF，GPU 节点是单客户端内的逻辑模拟。

### 5.3 fio 基线

复测 baseline：

```bash
AURA_REMOTE_DEVICE=/dev/nvmeXnY \
AURA_LOCAL_READ_DEVICE=/dev/nvme0n1 \
./scripts/real_nvmeof_baseline.sh
```

安全提醒：

- 写测试只能对专用测试 Namespace 或 backing file 做。
- 不要对系统盘或已有业务数据盘运行 fio 写测试。
- 不要把同一个普通 ext4/xfs Namespace 同时挂载给多台机器读写。

## 6. 常见脚本

| 脚本 | 作用 |
|---|---|
| `scripts/check_environment.sh` | 检查依赖和运行环境 |
| `scripts/connect_nvme.sh` | 连接并挂载 NVMe-oF 后端 |
| `scripts/disconnect_nvme.sh` | 断开 NVMe-oF 后端 |
| `scripts/lab_network_probe.sh` | 只读检查实验室 Target 端口、NVMe 工具和挂载状态 |
| `scripts/setup_nvme_target.sh` | 双 VM Target 配置 |
| `scripts/setup_lab_nvmeof_target.sh` | 实验室 Target 通用配置脚本 |
| `scripts/real_nvmeof_baseline.sh` | 真实 NVMe-oF fio baseline |
| `scripts/nvmeof_gap_diagnostic.sh` | 诊断本地目录与 NVMe-oF 挂载目录的原始性能差距 |
| `scripts/nvmeof_net_profile.sh` | 在双 VM 环境中用 `tc` 设置可记录的 NVMe/TCP 网络校准档位 |
| `scripts/paper_experiments.py` | 论文前四项实验总入口 |

## 7. 故障与边界

如果客户端连不上 4420，优先检查：

- 客户端是否在能访问 Target 私网的内网环境。
- Target 是否监听 4420。
- 安全组、防火墙或校园网策略是否拦截。
- Host NQN 是否在 Target ACL 内。
- `nvme discover` 是否能看到 Subsystem NQN。

当前本地 UTM VM 可能无法直连实验室私网 4420；这种情况下，VM 继续用于代码开发和双 VM 协议验证，真实 NVMe-oF 性能应在能直连实验室 Target 的内网客户端上采集。
