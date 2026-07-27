# GPU-Aware TierFS / TokenFS

项目中文名：

```text
面向多 GPU 大模型 KV Cache 的本地-远程自适应分层文件系统
```

TokenFS 是一个面向大模型 prompt token、token shard 和 KV Cache 数据的 GPU 感知分层文件系统原型。它通过 FUSE 提供统一 POSIX 命名空间，为不同 GPU 分配独立本地 SSD 配额；写入时优先使用 GPU 对应本地 SSD，本地空间不足时自动溢写到远端 SSD 层。远端层在开发阶段可以用普通目录或双 VM NVMe-oF 模拟，真实环境中切换为 NVMe-oF 挂载目录。

当前仓库按三大板块组织：

```text
代码：src/、scripts/、config/
说明文档：README.md
数据结果：reports/latest/final-report.md
```

## 1. 总体架构

```text
vLLM / SGLang / token workload 测试程序
                  |
                  v
          FUSE 统一命名空间
                  |
                  v
        元数据与放置决策模块
          /                    \
         v                      v
 GPU 对应本地 SSD          NVMe-oF 远程 SSD 池
         ^                      |
         |                      v
         +---- 异步迁移与预取 ----+
```

用户只看到统一目录：

```text
/mnt/tokenfs/gpu0/...
/mnt/tokenfs/gpu1/...
```

系统内部记录每个文件或缓存块的逻辑路径、所属 GPU、local/remote 层级、物理路径、大小、checksum、访问次数、生产 GPU、重算代价和共享度。

## 2. 当前能力

核心文件系统能力：

- FUSE 文件接口：`getattr`、`readdir`、`mkdir`、`create`、`open`、`read`、`write`、`truncate`、`rename`、`unlink`、`fsync`、`release`。
- GPU namespace：默认支持 `/gpu0`、`/gpu1`，每个 GPU 有独立本地目录和本地配额。
- 本地优先：空间足够时写入 GPU 对应本地目录。
- 远端溢写：本地不足时写入 remote 后端。
- NVMe-oF ready：真实 IP 未到位时可 dry-run 或双 VM 验证；真实环境只需替换 IP、NQN、设备名和挂载目录。
- SQLite WAL 元数据：记录文件位置、状态、checksum、访问统计和策略字段。
- 一致性恢复：启动时处理未完成写入和迁移状态，清理临时文件。

策略能力：

- 价值感知放置/淘汰：按复用概率、重算代价、GPU 亲和度、共享度、文件大小和远端访问代价综合打分。
- GPU 亲和统计：记录每个文件被哪个 GPU 读取，支持判断数据更适合放在哪张 GPU 的本地层。
- 热点提升：远端文件被多次读取后可迁回本地。
- 顺序预取：连续编号 shard 被读取时，可提前迁入下一片。
- 迁移状态机：本地到远端、远端到本地都经过可恢复状态。
- QoS 原型：记录每 GPU 读写次数和字节量，并支持按 GPU 设置读/写 IOPS 限速。

## 3. 创新点

### 创新点 1：AI 价值感知的数据放置

不只按剩余空间或 LRU 淘汰，而是给每个缓存块计算价值：

```text
数据价值 =
复用概率 * 重新计算代价 * GPU 亲和度
/ 数据大小
/ 远程访问代价
```

高价值数据尽量留在本地，低价值数据优先迁到远端或淘汰。实验可对比：

```text
静态阈值
LRU
LFU
本地优先但不迁移
TokenFS 价值感知算法
```

### 创新点 2：GPU 亲和感知

系统记录：

- 文件由哪个 GPU 产生；
- 哪个 GPU 最常访问；
- 是否被多 GPU 共享；
- 是否应该放在共享远端层，避免多份本地重复占用；
- 是否应该迁入某个 GPU 的本地层，降低该 GPU 的数据等待时间。

例如 GPU0 访问 80%、GPU1 访问 15%、GPU2 访问 5% 的缓存，应优先靠近 GPU0；如果多个 GPU 访问比例接近，则更适合留在共享远端层，避免在多个本地盘重复保存。

### 创新点 3：多 GPU 配额公平和 QoS

当前版本已经记录每个 GPU 的读写次数和数据量，并实现了可配置的每 GPU 读/写 IOPS 限速。后续可以在此基础上继续增强：

```text
每 GPU 独立请求队列
带权公平调度
Token Bucket 更细粒度限速
延迟敏感任务优先
最低带宽保障
动态配额借用
空闲配额回收
```

论文指标可加入 Jain 公平性指数、每 GPU P99 延迟、SLO 违反率、配额违约次数。

## 4. 工程可靠性能力

跨层迁移一致性是文件系统必须具备的基础可靠性能力，不作为论文创新点单独包装。

```text
LOCAL
  -> COPYING_TO_REMOTE
  -> REMOTE_READY
  -> COMMITTED

REMOTE
  -> COPYING_TO_LOCAL
  -> LOCAL_READY
  -> COMMITTED
```

系统使用 SQLite WAL、临时文件、fsync、原子 rename、checksum 和启动恢复，避免迁移中崩溃造成元数据指向半成品。

P95/P99 延迟、远端读写耗时和网络状态只作为性能评估指标，不作为当前阶段的核心创新点。真实环境较小时，P99 驱动迁移很难稳定测出论文级收益，因此后续重点不放在这里。

## 5. 环境准备

推荐环境：

```text
Ubuntu 24.04 LTS ARM64
C++20
CMake + Ninja
FUSE3
SQLite WAL
nvme-cli
fio
```

安装依赖：

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

停止：

```bash
./scripts/stop_tokenfs.sh
```

## 6. 日常使用

写入和读取：

```bash
mkdir -p /mnt/tokenfs/gpu0/demo
echo "hello tokenfs" > /mnt/tokenfs/gpu0/demo/a.tokens
cat /mnt/tokenfs/gpu0/demo/a.tokens
```

查看状态：

```bash
./scripts/tokenfsctl.py status
./scripts/tokenfsctl.py files
./scripts/tokenfsctl.py metrics
./scripts/tokenfsctl.py affinity
./scripts/tokenfsctl.py check
```

核心测试：

```bash
./scripts/integration_test.sh
./scripts/token_workload_test.sh
./scripts/strategy_matrix_test.sh
./scripts/promote_test.sh
./scripts/prefetch_test.sh
./scripts/eviction_test.sh
./scripts/advanced_policy_test.sh
./scripts/fault_injection_test.sh
```

## 7. NVMe-oF 接入

当前没有真实 IP 时，remote 后端可以是目录：

```yaml
backends:
  - id: remote0
    type: directory
    root: /var/lib/tokenfs/remote-sim
```

真实环境到位后，改成 NVMe-oF 挂载目录：

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

连接流程：

```bash
./scripts/check_environment.sh
sudo ./scripts/connect_nvme.sh config/tokenfs.dev.yaml
./scripts/start_tokenfs.sh
```

双 VM 模拟真实 NVMe/TCP 路径：

```bash
# Target VM
sudo ./scripts/setup_nvme_target.sh

# Client VM
sudo ./scripts/connect_nvme.sh config/tokenfs.dev.yaml
./scripts/nvmeof_two_vm_test.sh
./scripts/nvmeof_perf_test.sh
```

## 8. 当前能验证什么

没有真实 SSD IP 时，仍然可以真实验证：

- FUSE 文件系统语义；
- GPU 配额隔离；
- 本地优先和远端溢写；
- 价值感知淘汰；
- 热点提升；
- 顺序预取；
- 迁移状态机；
- checksum 和启动恢复；
- GPU 访问亲和统计；
- QoS 指标采集和限速原型；
- 双 VM NVMe/TCP 协议路径。

当前不能证明：

- 真实 SSD 和真实网络下的绝对带宽；
- 真实 P95/P99 延迟；
- 真实 GPU 等待数据时间；
- 多 GPU 并发下的系统上限。

因此当前阶段的结论应表述为：

```text
在未知真实 IP 和真实 SSD 环境前，TokenFS 已完成可部署软件框架、
策略逻辑、可观测指标和实验脚本；真实环境到位后复用同一套接口
重新采集最终性能数据。
```

## 9. 数据结果

统一结果入口：

```text
reports/latest/final-report.md
```

后续实验继续更新这一个文件即可，不再分散生成多份说明文档。
