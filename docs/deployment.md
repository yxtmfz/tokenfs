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

连接前先 dry-run：

```bash
./scripts/connect_nvme.sh --config config/tokenfs.dev.yaml --dry-run
```

真实连接：

```bash
sudo ./scripts/connect_nvme.sh \
  --config config/tokenfs.dev.yaml \
  --backend remote0 \
  --chown-current
```

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
| `scripts/setup_nvme_target.sh` | 双 VM Target 配置 |
| `scripts/setup_lab_nvmeof_target.sh` | 实验室 Target 通用配置脚本 |
| `scripts/real_nvmeof_baseline.sh` | 真实 NVMe-oF fio baseline |
| `scripts/paper_experiments.py` | 论文前四项实验总入口 |

## 7. 故障与边界

如果客户端连不上 4420，优先检查：

- 客户端是否在能访问 Target 私网的内网环境。
- Target 是否监听 4420。
- 安全组、防火墙或校园网策略是否拦截。
- Host NQN 是否在 Target ACL 内。
- `nvme discover` 是否能看到 Subsystem NQN。

当前本地 UTM VM 可能无法直连实验室私网 4420；这种情况下，VM 继续用于代码开发和双 VM 协议验证，真实 NVMe-oF 性能应在能直连实验室 Target 的内网客户端上采集。
