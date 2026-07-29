# GPU-Aware TierFS / TokenFS

```text
面向多 GPU 大模型 KV Cache 的本地-远程自适应分层文件系统
```

TokenFS 是一个面向大模型 Prompt Token、Token Shard 和 KV Cache 数据的 GPU 感知分层文件系统原型。系统通过 FUSE 提供统一 POSIX 命名空间，让上层的 vLLM、SGLang 或测试程序像访问普通目录一样访问缓存数据；系统内部根据 GPU、本地 SSD 配额、数据热度、重算代价和远端访问代价，决定数据应该放在 GPU 对应本地 SSD，还是放在 NVMe-oF 远程 SSD 池。

当前没有真实 SSD Target IP 也可以开发和验证：远端层先用普通目录或双 VM NVMe/TCP 模拟；拿到真实 IP、NQN 和设备名后，只需要替换配置和运行 NVMe-oF 连接脚本。

## 项目结构

仓库只保留三类核心内容，避免文件过散：

```text
代码：src/、scripts/、config/
说明文档：README.md
实验结果：reports/latest/final-report.md
```

常用入口：

```text
src/main.cpp                    TokenFS FUSE 主程序
scripts/tokenfsctl.py           状态、文件、指标、副本、检查工具
config/tokenfs.dev.yaml         开发环境配置
reports/latest/final-report.md  当前统一实验报告
```

## 总体架构

```text
vLLM / SGLang / Token Workload
              |
              v
        FUSE 统一命名空间
              |
              v
       元数据与放置决策模块
       /                    \
      v                      v
GPU 对应本地 SSD       NVMe-oF 远程 SSD 池
      ^                      |
      |                      v
      +---- 迁移、预取、缓存回收 ----+
```

用户只看到统一目录：

```text
/mnt/tokenfs/gpu0/...
/mnt/tokenfs/gpu1/...
```

实际数据可能在：

```text
/var/lib/tokenfs/local/gpu0/...       GPU0 本地 SSD 层
/var/lib/tokenfs/local/gpu1/...       GPU1 本地 SSD 层
/var/lib/tokenfs/remote-sim/gpu0/...  开发阶段远端模拟层
/srv/tokenfs/remote0/gpu0/...         真实 NVMe-oF 挂载层
```

## 核心设计

TokenFS 不把 GPU 当作存储设备。GPU 的作用是告诉文件系统：这份缓存主要服务哪张 GPU、哪张 GPU 最常访问、哪个本地 SSD 更适合保存它。真正存数据的是本地 SSD 和远端 NVMe-oF SSD。

当前采用“远端共享主副本 + GPU 本地热缓存”的设计：

```text
远端 SSD：共享容量层，适合保存可跨 GPU 访问的数据主副本
本地 SSD：GPU 热缓存层，适合保存某张 GPU 近期高频使用的数据
```

典型状态：

```text
LOCAL_ONLY
  只有本地文件，适合刚写入且尚未共享的数据

REMOTE_ONLY
  只有远端文件，适合冷数据、共享数据或本地空间不足的数据

REMOTE_WITH_LOCAL_CACHE
  远端保留主副本，本地保留某个 GPU 的热点缓存副本
```

这样可以处理一个关键问题：如果 GPU0 很常用某份数据，GPU0 可以把它缓存到自己的本地 SSD；如果 GPU1 后续也要读，不需要直接访问 GPU0 的本地盘，而是从远端主副本读取，必要时再缓存到 GPU1 本地。缓存副本的创建和删除由元数据记录，避免本地副本越来越多、无法管理。

## 三个研究重点

### 1. AI 价值感知放置

传统本地优先或 LRU 只看空间和最近访问时间。TokenFS 会为数据估算价值：

```text
数据价值 = 复用概率 * 重新计算代价 * GPU 亲和度 / 数据大小 / 远程访问代价
```

这不是声称“最优公式”，而是一个可解释、可替换的启发式框架。它把大模型缓存场景里真正重要的因素放进同一个决策模型：

```text
复用概率高     -> 更值得留本地
重算代价高     -> 更值得留本地
GPU 亲和强     -> 更应该靠近对应 GPU
数据太大       -> 保留本地的空间代价更高
远端访问慢     -> 更应该提前迁入本地
```

后续论文实验可以比较：

```text
静态阈值
LRU
LFU
本地优先但不迁移
TokenFS 价值感知算法
```

### 2. GPU 亲和感知

系统记录每个文件由哪个 GPU 产生、被哪些 GPU 读取、哪个 GPU 访问占比最高。

例子：

```text
cache_A:
GPU0 访问 80%
GPU1 访问 15%
GPU2 访问 5%
```

这说明 `cache_A` 对 GPU0 亲和度最高，应优先放入 GPU0 所在节点的本地 SSD。如果多个 GPU 访问比例接近，说明它更像共享数据，应保留在远端共享层，避免每台机器都重复保存一份。

### 3. 多 GPU QoS

远端 SSD 和网络可以并行服务多个 GPU，但资源不是无限的。如果 GPU0 大量连续读取，GPU1 的在线推理请求可能被拖慢。TokenFS 因此记录每个 GPU 的读写次数、字节量和限速延迟，并支持按 GPU 配置读/写 IOPS 限制。

这个方向后续可以扩展为：

```text
每 GPU 独立请求队列
带权公平调度
Token Bucket 限速
延迟敏感任务优先
最低带宽保障
动态配额借用
空闲配额回收
```

可评测指标包括：

```text
每 GPU 吞吐
每 GPU 平均延迟和 P99 延迟
Jain 公平性指数
SLO 违反率
配额违约次数
总吞吐下降幅度
```

## 工程可靠性

跨层迁移一致性是文件系统必备能力，不作为论文创新点单独包装。TokenFS 使用 SQLite WAL、临时文件、fsync、原子 rename、checksum 和启动恢复来避免迁移中崩溃导致元数据指向半成品。

本地写入远端：

```text
LOCAL_ONLY
  -> COPYING_TO_REMOTE
  -> REMOTE_READY
  -> REMOTE_ONLY
```

远端提升到本地缓存：

```text
REMOTE_ONLY
  -> COPYING_TO_LOCAL
  -> LOCAL_READY
  -> REMOTE_WITH_LOCAL_CACHE
```

删除本地缓存：

```text
REMOTE_WITH_LOCAL_CACHE
  -> DELETING_CACHE
  -> REMOTE_ONLY
```

启动时会扫描未完成状态和临时文件，将系统恢复到可解释的一致状态。

## 当前能力

文件系统接口：

```text
getattr, readdir, mkdir, create, open, read, write,
truncate, rename, unlink, fsync, release
```

存储与元数据：

```text
GPU 独立命名空间 /gpu0、/gpu1
每 GPU 本地配额
本地优先写入
远端溢写
远端主副本 + 本地热缓存副本
SQLite WAL 元数据
checksum 校验
启动恢复和一致性检查
```

策略与观测：

```text
价值感知淘汰
热点提升
顺序 shard 预取
GPU 访问亲和统计
每 GPU QoS 指标和 IOPS 限速
性能报告生成
NVMe-oF dry-run 和双 VM 接入脚本
```

## 环境准备

推荐：

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

## 日常验证

基础读写：

```bash
mkdir -p /mnt/tokenfs/gpu0/demo
echo "hello tokenfs" > /mnt/tokenfs/gpu0/demo/a.tokens
cat /mnt/tokenfs/gpu0/demo/a.tokens
```

查看状态：

```bash
./scripts/tokenfsctl.py status
./scripts/tokenfsctl.py files
./scripts/tokenfsctl.py replicas
./scripts/tokenfsctl.py metrics
./scripts/tokenfsctl.py affinity
./scripts/tokenfsctl.py check
```

清理低价值本地缓存副本：

```bash
./scripts/tokenfsctl.py cache-gc --max-cache-mib 0
```

核心测试：

```bash
./scripts/integration_test.sh
./scripts/token_workload_test.sh
./scripts/strategy_matrix_test.sh
./scripts/promote_test.sh
./scripts/prefetch_test.sh
./scripts/eviction_test.sh
./scripts/replica_lifecycle_test.sh
./scripts/advanced_policy_test.sh
./scripts/fault_injection_test.sh
```

性能报告：

```bash
./scripts/perf_test.sh
```

生成的报告在 `reports/perf/latest/report.html` 和 `reports/perf/latest/report.md`。

## NVMe-oF 接入

开发阶段使用目录模拟远端：

```yaml
backends:
  - id: remote0
    type: directory
    root: /var/lib/tokenfs/remote-sim
```

真实环境到位后，切换为 NVMe-oF：

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
sudo ./scripts/connect_nvme.sh --config config/tokenfs.dev.yaml --backend remote0 --chown-current
./scripts/start_tokenfs.sh config/tokenfs.dev.yaml /mnt/tokenfs
```

注意：普通启动脚本不会自动格式化远端设备。首次初始化真实 SSD 前必须确认设备无重要数据。

## 当前结论

在没有真实 IP 的情况下，当前项目能验证的是：

```text
功能正确性
元数据一致性
放置策略是否按设计触发
热点提升、预取、淘汰、缓存 GC 是否形成闭环
GPU 亲和和 QoS 指标是否可观测
真实环境到位后是否能直接切换 NVMe-oF 后端
```

当前项目不能证明的是：

```text
真实 NVMe-oF SSD 的最终带宽
真实网络下的 P95/P99 延迟
真实 GPU 推理任务的数据等待时间下降比例
多 GPU 并发时的系统上限
```

因此现在的工作重点是把软件框架、策略接口、测试脚本和指标体系做完整；真实 IP、NQN 和 SSD 环境到位后，再用同一套实验脚本采集最终论文数据。
