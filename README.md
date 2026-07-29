# GPU-Aware TierFS / TokenFS

```text
面向多 GPU 大模型 KV Cache 的本地-远程自适应分层文件系统
```

TokenFS 是一个面向大模型 Prompt Token、Token Shard 和 KV Cache 数据的 GPU 感知分层文件系统原型。系统通过 FUSE 提供统一 POSIX 文件接口，让上层的 vLLM、SGLang 或测试程序像访问普通目录一样访问缓存数据；系统内部先根据数据热度、重算代价、远端访问代价和本地空间压力判断数据是否值得留在本地缓存，再根据 GPU 访问亲和度决定本地缓存副本应该放在哪些 GPU 对应的本地 SSD，或继续保留在 NVMe-oF 远程 SSD 池作为共享主副本。

这个项目当前的定位不是普通网盘，也不是完整替代 ext4/XFS 的底层文件系统，而是：

```text
面向多 GPU 大模型缓存场景的“本地 SSD + NVMe-oF 远端 SSD”自适应分层文件系统原型。
```

当前没有真实 SSD Target IP 也可以继续开发和验证：远端层先用普通目录或双 VM NVMe/TCP 模拟；拿到真实 IP、NQN、设备名后，只需要替换配置并运行 NVMe-oF 连接脚本。

---

## 1. 当前项目进度

当前已经完成的是“可运行的软件原型 + 策略框架 + 测试框架 + NVMe-oF 接入脚本”。真实 NVMe-oF 物理环境到位后，需要做的是替换配置、连接设备、重新跑真实性能实验。

| 模块 | 当前状态 | 说明 |
|---|---|---|
| FUSE 文件系统 | 已完成原型 | 支持常见 POSIX 文件操作 |
| GPU 命名空间 | 已完成 | 默认 `/gpu0`、`/gpu1` |
| 本地优先写入 | 已完成 | 本地配额够时写入 GPU 对应本地目录 |
| 远端溢写 | 已完成 | 本地空间不足时写入 remote 后端 |
| 远端主副本 + 本地热缓存 | 已完成 | 远端保存共享主副本，本地保存热点缓存副本 |
| SQLite 元数据 | 已完成 | WAL 模式，记录路径、层级、副本、指标等 |
| checksum 校验 | 已完成 | 当前使用 `fnv1a64`，可替换 |
| 迁移一致性状态机 | 已完成基础版 | 支持启动恢复和临时文件清理 |
| AI 价值感知缓存保留 | 已完成原型 | 决定数据值不值得继续占用本地缓存 |
| GPU 亲和感知副本放置 | 已深化 | 决定值得缓存的数据应该放在哪些 GPU 本地 |
| 多 GPU QoS | 已深化 | 已区分前台读写和后台迁移/预取/淘汰，并支持独立 QoS 指标 |
| 热点提升 | 已完成 | 远端热点数据可复制成本地缓存 |
| 顺序预取 | 已完成 | 连续 shard 可提前拉到本地 |
| 缓存 GC | 已完成 | 可删除远端已有主副本的本地缓存 |
| 性能/策略测试 | 已完成基础版 | 有 workload、策略矩阵、专项测试 |
| NVMe-oF dry-run | 已完成 | 没有真实 IP 时能检查配置流程 |
| 双 VM NVMe-oF 脚本 | 已具备 | 可用两台 VM 模拟真实 NVMe/TCP |
| 真实 SSD 环境测试 | 待实验室环境 | 需要 Target IP、NQN、设备名、权限 |

一句话总结当前阶段：

```text
功能框架已经基本成型；当前测试能证明系统逻辑正确，但还不能证明真实 NVMe-oF 环境下的最终性能。
```

---

## 2. 仓库结构

仓库按三大板块理解：

```text
代码：src/、scripts/、config/
说明文档：README.md
实验结果：reports/latest/final-report.md
```

核心文件：

| 路径 | 作用 |
|---|---|
| `src/main.cpp` | TokenFS FUSE 主程序，文件系统核心逻辑都在这里 |
| `config/tokenfs.dev.yaml` | 开发环境配置，包括 GPU、本地目录、远端后端、策略开关 |
| `scripts/tokenfsctl.py` | 管理工具，用来查看状态、元数据、副本、指标、一致性 |
| `scripts/start_tokenfs.sh` | 启动 TokenFS 并挂载到 `/mnt/tokenfs` |
| `scripts/stop_tokenfs.sh` | 停止 TokenFS 并卸载挂载点 |
| `scripts/reset_dev_state.sh` | 清理开发环境数据，重置到干净状态 |
| `scripts/connect_nvme.sh` | 连接真实 NVMe-oF 后端并挂载 |
| `scripts/setup_nvme_target.sh` | 在第二台 VM 上搭建 NVMe-oF Target |
| `scripts/nvmeof_two_vm_test.sh` | 双 VM NVMe-oF 连通性测试 |
| `reports/latest/final-report.md` | 当前统一实验报告 |

当前 GitHub 上主要保留这些清晰入口。某些测试生成的 CSV/JSON/HTML 结果默认不作为主文档入口，避免仓库看起来太乱。

---

## 3. 总体架构

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

这里的 GPU 不是存储设备。GPU 在系统里的作用是提供“亲和信息”：

```text
哪个 GPU 产生了这份缓存
哪个 GPU 最常访问这份缓存
哪些缓存是某张 GPU 的私有热点
哪些缓存适合放到远端共享层
```

真正保存数据的是本地 SSD 和远端 NVMe-oF SSD。

---

## 4. 核心存储语义

当前采用：

```text
远端共享主副本 + GPU 本地热缓存副本
```

含义是：

```text
远端 SSD：共享容量层/主副本层，适合保存冷数据或多 GPU 共享数据
本地 SSD：GPU 热缓存层，适合保存某张 GPU 近期高频使用的数据
```

这样做是为了解决多 GPU 共享场景中的矛盾：

```text
如果 GPU0 很常用某份数据，GPU0 希望它在本地；
如果 GPU1 也偶尔需要这份数据，GPU1 不应该直接访问 GPU0 的本地盘；
因此远端保留主副本，GPU0 本地只保存热点缓存副本。
```

### 4.1 副本状态

| 状态 | 含义 |
|---|---|
| `LOCAL_ONLY` | 文件只在本地，通常是刚写入且暂未迁远端的数据 |
| `REMOTE_ONLY` | 文件只在远端，通常是冷数据、共享数据或本地空间不足数据 |
| `REMOTE_WITH_LOCAL_CACHE` | 远端有主副本，本地有某个 GPU 的热点缓存副本 |

迁移过程中的临时状态：

| 状态 | 含义 |
|---|---|
| `COPYING_TO_REMOTE` | 正在从本地复制到远端 |
| `REMOTE_READY` | 远端副本已写完，等待提交元数据 |
| `COPYING_TO_LOCAL` | 正在从远端复制到本地 |
| `LOCAL_READY` | 本地缓存已写完，等待提交元数据 |
| `DELETING_CACHE` | 正在删除本地缓存副本 |

### 4.2 生命周期例子

新文件先写本地：

```text
LOCAL_ONLY
```

本地空间不足或低价值淘汰：

```text
LOCAL_ONLY
  -> COPYING_TO_REMOTE
  -> REMOTE_READY
  -> REMOTE_ONLY
```

远端热点数据被 GPU0 反复读取：

```text
REMOTE_ONLY
  -> COPYING_TO_LOCAL
  -> LOCAL_READY
  -> REMOTE_WITH_LOCAL_CACHE
```

本地缓存变冷，需要回收本地空间：

```text
REMOTE_WITH_LOCAL_CACHE
  -> DELETING_CACHE
  -> REMOTE_ONLY
```

---

## 5. 三个研究重点

按照当前论文方向，只保留三个主创新点：

```text
AI 价值感知缓存保留
GPU 亲和感知副本放置
多 GPU QoS
```

三者的分工是：

```text
创新点一：留不留本地
创新点二：如果留本地，放在哪些 GPU 本地，或保持远端共享
创新点三：多个 GPU 同时访问/迁移时，资源怎么公平分
```

跨层迁移一致性作为文件系统必要工程能力，不单独包装为创新点。公共 Prompt 前缀去重不再作为当前主线。

### 5.1 AI 价值感知缓存保留

传统策略通常只看剩余空间或最近访问时间。例如：

```text
本地满了 -> 随便找冷文件迁走
LRU -> 谁最久没访问就迁走
LFU -> 谁访问次数少就迁走
```

但大模型缓存数据不只看“最近访问”。一份 KV Cache 是否值得留在本地，还取决于：

```text
之后还会不会复用
重新计算它贵不贵
它有多大
远端读取它慢不慢
它是不是多 GPU 共享
当前本地空间紧不紧张
```

当前启发式公式：

```text
数据保留价值 =
复用概率
× 重新计算代价
× 远端访问代价
× 共享收益
÷ 数据大小
÷ 本地空间压力
```

这个公式不是声称数学最优，而是一个可解释、可替换的框架。它解决的是“这份数据该不该继续占本地 SSD 缓存”，也就是保留/淘汰问题。

当前工程落地：

```text
read_count              近似复用概率
recompute_cost          重算代价
size_bytes              数据大小
remote_access_cost      远端访问代价
share_count             共享度
local_space_pressure    本地空间压力
```

当前可验证点：

```bash
./scripts/eviction_test.sh
./scripts/advanced_policy_test.sh
./scripts/strategy_matrix_test.sh
```

后续真实环境可继续优化：

```text
把 read_count 换成滑动窗口热度
把 remote_access_cost 换成真实 P95/P99 远端读取延迟
根据实际 GPU 等待时间调整权重
把启发式公式替换为学习型策略
```

### 5.2 GPU 亲和感知副本放置

GPU 亲和感知解决的问题不是“这份数据值不值得留本地”，而是：

```text
如果创新点一已经判断它值得占用本地缓存，
那么它应该放在哪个 GPU 的本地 SSD？
是只放 GPU0？
还是 GPU0/GPU1 都放？
还是虽然有访问但更适合继续留在远端共享？
```

所以创新点二主要研究不同物理空间之间的选择：GPU0 本地、GPU1 本地、多个 GPU 本地，或远端共享层。

这不是简单地说“路径在 `/gpu0` 就永远归 GPU0”。例如：

```bash
TOKENFS_GPU_ID=1 cat /mnt/tokenfs/gpu0/value/hot.tokens
```

这表示文件逻辑上属于 `/gpu0`，但实际调用方是 GPU1。TokenFS 会把这次访问记入 GPU1，用来判断数据是否正在从 GPU0 私有热点变成跨 GPU 共享热点，或者亲和是否正在转向 GPU1。

#### 5.2.1 调用方 GPU 识别

TokenFS 会读取访问进程的环境变量：

```text
TOKENFS_GPU_ID
CUDA_VISIBLE_DEVICES
```

如果识别成功，就按真实调用方 GPU 统计；如果没有设置，就退回到路径所属 GPU。例如 `/gpu0/...` 默认归 GPU0。

这样做的意义是：文件系统虽然看不到 CUDA kernel，但可以通过训练/推理任务启动时注入的环境变量，知道“这次数据访问服务于哪张 GPU”。

#### 5.2.2 时间窗口热度，而不是只看累计次数

只看累计次数会有一个问题：早期 GPU0 读了很多次，后面 GPU1 开始变热，但累计统计仍然会被 GPU0 压住。

所以当前实现同时维护两类统计：

```text
gpu_access         累计访问次数，用来判断长期 dominant GPU
gpu_access_events  每次访问时间，用来计算短窗口热度和趋势
```

配置项：

```yaml
affinity_short_window_sec: 300
affinity_long_window_sec: 3600
affinity_trend_min_reads: 3
affinity_hot_read_threshold: 4
affinity_warm_read_threshold: 2
```

含义：

```text
短窗口：看最近谁真正变热
长窗口：看背景趋势
最小读数：避免一次偶然访问就改变判断
热阈值/温阈值：区分 hot、warm、cold
```

#### 5.2.3 访问趋势判断

TokenFS 会比较长期 dominant GPU 和短窗口 dominant GPU。

例如：

```text
长期统计：GPU0 占 80%
最近 300 秒：GPU1 占 100%
```

这说明访问亲和可能正在从 GPU0 转向 GPU1，系统会把状态标记为：

```text
AFFINITY_SHIFTING
trend = SHIFTING_TO_GPU1
```

这个状态不会立刻粗暴删除旧副本，而是让系统进入“准备迁移/复制但防止抖动”的阶段。

#### 5.2.4 多级亲和状态

当前亲和分类如下：

| 状态 | 含义 | 放置倾向 |
|---|---|---|
| `GPU_LOCAL_HOT` | 短窗口内明显集中在某张 GPU，且访问热 | 保留 1 个本地热点副本 |
| `GPU_LOCAL_WARM` | 短窗口内明显集中在某张 GPU，但访问量还不高 | 保留或准备 1 个本地温副本 |
| `REMOTE_SHARED_HOT` | 多 GPU 近期都在访问，且整体热 | 远端主副本保留，同时允许多个 GPU 本地副本 |
| `CROSS_GPU_SHARED` | 多 GPU 访问较均衡，但热度不高 | 倾向远端共享，暂不复制太多本地副本 |
| `AFFINITY_SHIFTING` | 最近 dominant GPU 与长期 dominant GPU 不一致 | 说明亲和正在转移，可向新 dominant GPU 生成副本 |
| `REMOTE_COLD` | 最近访问量很低 | 向价值层反馈低热度，通常可以减少本地副本 |
| `MIXED_AFFINITY` | 有偏向但不够绝对 | 保守观察 |
| `UNKNOWN` | 访问数据不足 | 使用默认策略 |

查看：

```bash
./scripts/tokenfsctl.py affinity
```

#### 5.2.5 GPU 亲和副本放置机制

自适应本地副本数量和跨 GPU 本地副本管理，本质上是同一个问题，但它不单独决定“这份数据还值不值得留在本地”。这个问题交给创新点一的价值层判断。

创新点二只回答位置问题：

```text
远端 SSD 保存主副本/容量层
各 GPU 本地 SSD 是巨大缓存层

当价值层认为这份数据值得占用本地缓存时：
1. 应该为哪个 GPU 创建本地副本
2. 应该创建到哪些 GPU 的本地 SSD
3. 是只保留 1 个 GPU 本地副本，还是多个 GPU 都保留
4. 如果价值层要求收缩本地缓存，应该优先释放哪个 GPU 位置的副本
```

所以这一节的核心不是“副本越多越好”，而是一个 GPU 感知的位置选择机制。

可以把三层决策关系理解为：

```text
远端 SSD：保存主副本，提供共享容量层
创新点一：判断数据是否值得留在本地缓存层
创新点二：判断本地缓存副本应该放在哪些 GPU 附近
```

##### 5.2.5.1 决策输入

TokenFS 为每个文件持续收集以下信息：

```text
文件大小
远端主副本是否存在
每个 GPU 的累计访问次数
每个 GPU 的短窗口访问次数
最近 dominant GPU
长期 dominant GPU
访问趋势是否正在变化
远端访问代价
本地副本复制成本
副本创建后的驻留时间
价值层给出的本地缓存预算或保留建议
```

其中最重要的是时间窗口热度和趋势：

```text
如果 GPU1 最近突然频繁访问 GPU0 的数据
说明这份数据可能正在变成 GPU1 的热点
系统应考虑在 GPU1 本地创建副本
```

##### 5.2.5.2 位置收益评分

对每个候选 GPU，系统可以抽象出一个本地副本位置收益：

```text
位置收益 =
该 GPU 近期访问热度
× 远端转本地的访问节省
× GPU 亲和强度
- 复制到该 GPU 的成本
- 该 GPU 本地空间压力
```

更工程化地写，可以理解为：

```text
PlacementScore(gpu, file)
  = recent_reads(gpu, file)
  × (remote_read_cost - local_read_cost)
  × affinity_score(gpu, file)
  - copy_cost(file)
  - local_space_pressure(gpu)
```

解释：

| 因素 | 作用 |
|---|---|
| `recent_reads` | 最近读得越多，越值得复制 |
| `remote_read_cost - local_read_cost` | 远端比本地慢得越多，复制收益越高 |
| `affinity_score` | 越偏向某个 GPU，越应该靠近它 |
| `copy_cost` | 创建副本本身要消耗网络和 SSD 写入 |
| `local_space_pressure` | 某个 GPU 本地越满，越不应该优先把副本放到那里 |

当前代码里先实现了可解释启发式版本：用访问热度、亲和状态、目标副本数、空间配额和防抖参数共同决定副本位置。真实 NVMe-oF 环境到位后，可以把 `remote_read_cost`、`local_read_cost` 和 `copy_cost` 替换成实测延迟/带宽数据。

##### 5.2.5.3 目标副本数

每个文件都有一个策略建议字段：

```text
target_local_replica_count
```

它表示“在价值层允许占用本地缓存的前提下，当前亲和层建议这份文件最多放到几个 GPU 本地”。

当前规则：

```text
GPU_LOCAL_HOT
  -> 目标本地副本数 1
  -> 放在最近 dominant GPU 本地

GPU_LOCAL_WARM
  -> 目标本地副本数 1
  -> 可以准备本地温副本

AFFINITY_SHIFTING
  -> 目标本地副本数 1
  -> 放向新的 recent dominant GPU

REMOTE_SHARED_HOT
  -> 目标本地副本数 min(近期访问 GPU 数, max_local_replicas_per_file)
  -> 多个 GPU 都热时，允许多个本地副本

CROSS_GPU_SHARED
  -> 先倾向远端共享
  -> 热度不足时不急着复制

REMOTE_COLD
  -> 亲和层建议本地副本数 0
  -> 向价值层反馈这份数据近期不适合继续占本地缓存
```

配置上限：

```yaml
max_local_replicas_per_file: 2
```

这个值控制“最多允许多少个 GPU 同时拥有该文件的本地缓存副本”。它不是越大越好，因为副本多会占本地 SSD 空间，也会增加复制和回收成本。

##### 5.2.5.4 副本创建

典型场景：

```text
文件：/gpu0/shared/a.tokens
远端主副本：remote/gpu0/shared/a.tokens
GPU1 最近频繁读取它
状态变成 REMOTE_SHARED_HOT 或 AFFINITY_SHIFTING
```

系统会判断：

```text
远端主副本是否存在
GPU1 是否是近期热点访问者
当前副本数是否低于 target_local_replica_count
GPU1 本地空间是否足够
是否刚创建过副本，避免重复复制
```

如果条件满足，就在 GPU1 本地生成隐藏副本：

```text
/var/lib/tokenfs/local/gpu1/.tokenfs-replicas/gpu0/shared/a.tokens
```

之后 GPU1 再读这个文件时，可以直接命中 GPU1 本地副本，而不是每次都走远端。

副本记录在 `local_replicas` 表中：

```text
logical_path
gpu_id
physical_path
size_bytes
cache_generation
created_at
last_access_at
state
```

##### 5.2.5.5 副本位置收缩

当创新点一判断本地缓存空间需要回收，或者亲和层判断副本数超过当前建议值时，创新点二负责回答：

```text
不是“这份数据要不要删”，而是“如果要减少本地副本，先删哪个 GPU 位置上的副本”。
```

当前位置收缩逻辑：

```text
如果实际本地副本数 > target_local_replica_count
  找出最久未访问的本地副本
  如果仍处于最短驻留时间内，则暂时不删
  否则删除该 GPU 本地副本
  更新 local_replicas 表
```

当本地空间紧张时，价值感知淘汰策略先决定哪些低价值缓存可以释放；GPU 亲和层再帮助选择释放哪个 GPU 本地位置，避免误删仍被某张 GPU 高频访问的副本。

##### 5.2.5.6 防抖动机制

缓存系统最怕“刚复制过去又删掉，刚删掉又复制回来”。这种现象叫抖动，会浪费网络和 SSD 写入寿命。

当前实现了两个防抖参数：

```yaml
affinity_replica_cooldown_sec: 30
affinity_replica_min_residency_sec: 120
```

含义：

```text
cooldown：同一个文件刚生成过本地副本后，短时间内不重复触发复制
min_residency：副本刚创建后至少保留一段时间，即使目标副本数下降也不立刻收缩
```

##### 5.2.5.7 当前实现中的副本算法流程

一次读请求到来时，TokenFS 的决策流程可以概括为：

```text
1. 识别调用方 GPU
2. 更新 gpu_access 和 gpu_access_events
3. 计算短窗口热度、长期 dominant GPU、recent dominant GPU
4. 判断 affinity_state
5. 计算 target_local_replica_count
6. 如果调用方 GPU 本地已有副本，直接命中本地
7. 如果没有副本，判断是否值得创建
8. 如果值得创建，复制远端主副本到调用方 GPU 本地隐藏目录
9. 如果副本数超过目标值，选择亲和度低/久未访问的 GPU 位置收缩
10. 通过 cooldown 和 min_residency 防止频繁复制和收缩
```

查看：

```bash
./scripts/tokenfsctl.py replicas
./scripts/tokenfsctl.py metrics
```

相关指标：

```text
cross_gpu_replica_create_count
cross_gpu_replica_create_bytes
cross_gpu_local_replica_hit
cross_gpu_replica_reuse_count
cross_gpu_replica_delete_count
cross_gpu_replica_skip_cap
cross_gpu_replica_skip_cooldown
cross_gpu_replica_keep_min_residency
cross_gpu_replica_delete_bytes
```

#### 5.2.6 当前创新点二已经包含的技术

目前 GPU 亲和感知已经包括：

```text
1. 调用方 GPU 识别
2. 累计访问统计
3. 时间窗口热度统计
4. 访问趋势判断
5. 多级亲和状态分类
6. GPU 亲和副本放置机制：放到哪个 GPU、本地放几份、是否保持远端共享
7. 位置收益评分：访问热度、远端节省、GPU 亲和度、复制成本和空间压力
8. 副本收缩位置选择：价值层决定是否释放本地缓存，亲和层决定先释放哪个 GPU 位置
9. 防抖动机制：冷却时间 + 最短驻留时间
10. 与 AI 价值感知淘汰联动
11. 与多 GPU QoS 指标联动
```

测试：

```bash
./scripts/advanced_policy_test.sh
```

这个脚本会验证：

```text
高价值热点文件不会被优先淘汰
GPU 访问亲和状态能识别 REMOTE_SHARED_HOT
GPU 访问趋势能识别 AFFINITY_SHIFTING
跨 GPU 本地副本可以创建并命中
QoS 延迟指标可以记录
一致性检查可以通过
```

### 5.3 多 GPU QoS

远端 NVMe-oF SSD 可以并行服务多个 GPU，但带宽、队列深度和网络资源不是无限的。如果 GPU0 长时间大流量读取，GPU1 的在线请求可能被拖慢。

QoS 要解决的是：

```text
不能只追求总吞吐，还要避免某一张 GPU 或某个任务被长期饿死。
```

当前工程落地：

```text
记录每 GPU 读写次数
记录每 GPU 读写字节数
支持按 GPU 设置读 IOPS 限速
支持按 GPU 设置写 IOPS 限速
记录 QoS 延迟次数和总延迟
区分前台 read/write 请求
区分后台 promote/prefetch/evict 请求
支持后台迁移 IOPS 限制
支持后台迁移 MiB/s 限制
```

配置项：

```yaml
qos_read_iops_per_gpu: 0
qos_write_iops_per_gpu: 0
qos_background_iops_per_gpu: 0
qos_background_mib_per_sec_per_gpu: 0
```

`0` 表示不限速。做 QoS 实验时可以改成具体数值，例如：

```yaml
qos_read_iops_per_gpu: 100
qos_write_iops_per_gpu: 50
qos_background_iops_per_gpu: 10
qos_background_mib_per_sec_per_gpu: 200
```

查看命令：

```bash
./scripts/tokenfsctl.py metrics
```

后续真实环境可继续优化：

```text
每 GPU 独立请求队列
带权公平调度
Token Bucket 限速
在线推理优先级
最低带宽保障
动态配额借用
空闲配额回收
Jain 公平性指数评估
```

---

## 6. 元数据设计

TokenFS 使用 SQLite 保存元数据，默认数据库路径：

```text
/var/lib/tokenfs/metadata/tokenfs.db
```

配置文件中对应字段：

```yaml
filesystem:
  metadata_db: /var/lib/tokenfs/metadata/tokenfs.db
```

### 6.1 files 表核心字段

| 字段 | 含义 |
|---|---|
| `logical_path` | 用户看到的路径，例如 `/gpu0/demo/a.tokens` |
| `gpu_id` | 归属 GPU 编号 |
| `tier` | 当前活跃读取层，`local` 或 `remote` |
| `backend_id` | 后端 ID，本地为 `local`，远端如 `remote0` |
| `physical_path` | 当前活跃物理文件路径 |
| `size_bytes` | 文件大小 |
| `checksum` | 内容校验值 |
| `state` | 提交状态，正常为 `COMMITTED` |
| `read_count` | 文件读取次数 |
| `content_key` | 内容标识，当前不作为主线创新点 |
| `recompute_cost` | 重算代价 |
| `remote_access_cost` | 远端访问代价 |
| `producer_gpu` | 生产该文件的 GPU |
| `share_count` | 共享度 |
| `primary_tier` | 主副本所在层，当前常见为 `local` 或 `remote` |
| `has_remote_copy` | 是否存在远端副本 |
| `local_cache_owner_gpu` | 本地缓存副本归属 GPU，`-1` 表示无本地缓存 |
| `replica_state` | 副本生命周期状态 |
| `cache_generation` | 缓存代数，每次生成本地缓存递增 |
| `last_promoted_at` | 最近提升到本地缓存的时间 |
| `last_demoted_at` | 最近转回远端/删除本地缓存的时间 |
| `dominant_gpu_id` | 当前访问占比最高的 GPU |
| `dominant_gpu_read_share_x100` | dominant GPU 的读取占比，单位是百分比整数 |
| `recent_dominant_gpu_id` | 短时间窗口内访问占比最高的 GPU |
| `recent_dominant_gpu_read_share_x100` | 短时间窗口 dominant GPU 读取占比 |
| `recent_read_count` | 短时间窗口内的读取次数 |
| `affinity_trend` | 亲和趋势，例如 `STABLE`、`SHIFTING_TO_GPU1` |
| `target_local_replica_count` | 当前策略建议保留的本地缓存副本数量 |
| `affinity_state` | GPU 亲和分类，例如 `GPU_LOCAL_HOT`、`REMOTE_SHARED_HOT` |
| `affinity_updated_at` | 最近一次更新亲和分类的时间 |

### 6.2 metrics 表

记录系统运行指标，例如：

```text
read_ops
write_ops
read_local_ops
read_remote_ops
spill_count
promote_count
prefetch_count
evict_count
local_cache_create_count
local_cache_gc_count
qos_delay_ops
qos_foreground_read_ops
qos_foreground_write_ops
qos_background_ops
qos_background_bytes
qos_background_delay_ops
qos_gpu0_read_ops
qos_gpu1_write_bytes
affinity_cross_gpu_caller_count
affinity_cross_gpu_promote_skip
affinity_shared_remote_preferred_skip
affinity_non_dominant_promote_skip
```

### 6.3 gpu_access 表

记录每个文件被哪个 GPU 累计访问：

```text
logical_path
gpu_id
read_count
last_access_at
```

### 6.4 gpu_access_events 表

记录每一次读访问发生的时间：

```text
logical_path
gpu_id
access_at
```

这个表用于计算短窗口热度和访问趋势。当前默认短窗口为 300 秒，长窗口为 3600 秒。

### 6.5 local_replicas 表

记录跨 GPU 本地缓存副本：

| 字段 | 含义 |
|---|---|
| `logical_path` | 原始逻辑路径，例如 `/gpu0/xgpu/shared.tokens` |
| `gpu_id` | 这份本地副本放在哪个 GPU 的本地空间 |
| `physical_path` | 隐藏副本的真实路径 |
| `size_bytes` | 副本大小 |
| `cache_generation` | 副本代数 |
| `created_at` | 创建时间 |
| `last_access_at` | 最近命中时间 |
| `state` | 当前为 `READY` |

跨 GPU 本地副本使用隐藏目录，不会暴露给 `/mnt/tokenfs` 的普通目录列表：

```text
/var/lib/tokenfs/local/gpu1/.tokenfs-replicas/gpu0/...
```

---

## 7. 配置文件说明

开发配置在：

```text
config/tokenfs.dev.yaml
```

核心配置：

```yaml
filesystem:
  mount_point: /mnt/tokenfs
  metadata_db: /var/lib/tokenfs/metadata/tokenfs.db
  temp_suffix: ".tokenfs_tmp"

policy:
  mode: local_first
  placement_policy: value_aware
  replica_policy: remote_primary_local_cache
  cache_gc_policy: value_aware
  local_eviction_policy: value_aware
  promote_on_read: false
  promote_read_threshold: 2
  prefetch_on_read: false
  qos_read_iops_per_gpu: 0
  qos_write_iops_per_gpu: 0
  qos_background_iops_per_gpu: 0
  qos_background_mib_per_sec_per_gpu: 0
  affinity_dominant_threshold_x100: 70
  affinity_shared_threshold_x100: 55
  affinity_short_window_sec: 300
  affinity_long_window_sec: 3600
  affinity_trend_min_reads: 3
  affinity_hot_read_threshold: 4
  affinity_warm_read_threshold: 2
  max_local_replicas_per_file: 2
  cross_gpu_local_cache: true
  affinity_replica_cooldown_sec: 30
  affinity_replica_min_residency_sec: 120

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

当前默认策略是保守 baseline：

```text
热点提升默认关闭
顺序预取默认关闭
QoS 默认不限速
```

这样做是为了方便和增强策略做对照实验。专项测试脚本会临时打开对应策略。

---

## 8. 运行环境准备

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

重置开发环境：

```bash
./scripts/reset_dev_state.sh
```

启动：

```bash
./scripts/start_tokenfs.sh
```

停止：

```bash
./scripts/stop_tokenfs.sh
```

---

## 9. 日常使用和查看

基础读写：

```bash
mkdir -p /mnt/tokenfs/gpu0/demo
echo "hello tokenfs" > /mnt/tokenfs/gpu0/demo/a.tokens
cat /mnt/tokenfs/gpu0/demo/a.tokens
```

查看挂载、配额、后端：

```bash
./scripts/tokenfsctl.py status
```

查看文件元数据：

```bash
./scripts/tokenfsctl.py files
```

查看副本状态：

```bash
./scripts/tokenfsctl.py replicas
```

查看 GPU 亲和访问统计：

```bash
./scripts/tokenfsctl.py affinity
```

模拟“GPU1 访问 GPU0 目录中的缓存”：

```bash
TOKENFS_GPU_ID=1 cat /mnt/tokenfs/gpu0/demo/a.tokens >/dev/null
./scripts/tokenfsctl.py affinity
```

这条命令的意义是验证第二个创新点：文件路径属于 `/gpu0`，但实际调用方可以被识别成 GPU1。TokenFS 会把这次访问记入 `gpu_access`，并重新计算该文件是偏向某一张 GPU，还是更像多 GPU 共享数据。

查看读写、命中率、迁移、QoS 指标：

```bash
./scripts/tokenfsctl.py metrics
```

检查元数据和物理文件是否一致：

```bash
./scripts/tokenfsctl.py check
```

清理远端已有主副本的本地缓存：

```bash
./scripts/tokenfsctl.py cache-gc --max-cache-mib 0
```

只看将删除什么，不真正删除：

```bash
./scripts/tokenfsctl.py cache-gc --max-cache-mib 0 --dry-run
```

---

## 10. 测试脚本说明

核心测试：

| 脚本 | 验证内容 |
|---|---|
| `scripts/integration_test.sh` | 基础 FUSE 读写、目录、删除、重启恢复 |
| `scripts/token_workload_test.sh` | 模拟 token shard 顺序写入、读取和 GPU 隔离 |
| `scripts/strategy_matrix_test.sh` | baseline/promote/prefetch/full 策略矩阵 |
| `scripts/promote_test.sh` | 远端热点数据提升成本地缓存 |
| `scripts/prefetch_test.sh` | 连续 shard 顺序预取 |
| `scripts/eviction_test.sh` | 价值感知淘汰低价值本地数据 |
| `scripts/replica_lifecycle_test.sh` | 远端主副本 + 本地缓存 + 缓存 GC 生命周期 |
| `scripts/advanced_policy_test.sh` | 价值感知、GPU 亲和、QoS 综合验证 |
| `scripts/fault_injection_test.sh` | 故障注入和恢复 |
| `scripts/consistency_test.sh` | 元数据和物理文件一致性 |
| `scripts/random_io_test.sh` | 随机读写行为 |

建议开发时常跑：

```bash
./scripts/integration_test.sh
./scripts/promote_test.sh
./scripts/prefetch_test.sh
./scripts/eviction_test.sh
./scripts/replica_lifecycle_test.sh
./scripts/advanced_policy_test.sh
```

性能报告：

```bash
./scripts/perf_test.sh
```

生成位置：

```text
reports/perf/latest/report.html
reports/perf/latest/report.md
reports/perf/latest/summary.csv
```

统一实验报告：

```text
reports/latest/final-report.md
```

---

## 11. NVMe-oF 接入方式

### 11.1 当前目录模拟模式

没有真实 IP 时，远端后端用普通目录模拟：

```yaml
backends:
  - id: remote0
    type: directory
    root: /var/lib/tokenfs/remote-sim
```

这个模式可以验证：

```text
FUSE 功能
元数据正确性
本地/远端放置逻辑
热点提升
预取
淘汰
缓存 GC
GPU 亲和统计
QoS 指标
```

不能验证：

```text
真实 NVMe-oF 网络延迟
真实远端 SSD 带宽
真实多 GPU 并发远端访问上限
```

### 11.2 真实 NVMe-oF 模式

拿到真实环境后，后端改为：

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

`connect_nvme.sh` 会做：

```text
加载 nvme-tcp
创建挂载目录
执行 nvme discover
执行 nvme connect
识别 /dev/nvmeXnY
挂载到 /srv/tokenfs/remote0
```

安全提醒：

```text
普通启动不会自动格式化远端设备。
首次初始化真实 SSD 前必须确认设备无重要数据。
多个 Host 不能随便同时把同一个普通 ext4/XFS Namespace 挂载为可写。
```

### 11.3 双 VM NVMe-oF 模拟

当前仓库已经准备了双 VM 脚本：

```text
scripts/setup_nvme_target.sh
scripts/cleanup_nvme_target.sh
scripts/nvmeof_two_vm_test.sh
scripts/nvmeof_perf_test.sh
```

典型结构：

```text
VM1: tokenfs-dev
  作为 GPU Host / NVMe-oF Host

VM2: tokenfs-target
  作为 SSD Target / NVMe-oF Target
```

这比目录模拟更真实，因为它真的走 NVMe/TCP 协议；但它仍然是虚拟机环境，性能不能代表最终实验室物理 SSD。

---

## 12. 当前能证明什么，不能证明什么

当前能证明：

```text
TokenFS FUSE 文件系统可以正常挂载和读写
GPU namespace 和本地配额隔离可用
本地优先、远端溢写、热点提升、顺序预取、价值淘汰可运行
远端主副本 + 本地热缓存副本生命周期可运行
本地缓存可以被安全 GC，不删除远端主副本
SQLite 元数据、checksum、状态机和一致性检查可用
GPU 亲和统计可观测
QoS 指标和每 GPU IOPS 限速可运行
NVMe-oF 接口已经配置化，真实环境到位后能切换后端
```

当前不能证明：

```text
真实 NVMe-oF SSD 的最终带宽
真实网络下的 P50/P95/P99 延迟
真实 GPU 推理任务的数据等待时间下降比例
多 GPU 并发访问远端 SSD 时的系统上限
最终论文中的真实性能收益
```

所以当前阶段的正确目标是：

```text
把软件框架、策略接口、测试脚本、指标体系做完整；
等真实 IP、NQN、设备名到位后，用同一套脚本采集最终数据。
```

---

## 13. 真实环境到位后需要的信息

需要实验室提供：

```text
GPU 服务器 IP
GPU 数量和编号
每张 GPU 对应的本地 SSD 路径和容量
SSD Target IP
NVMe/TCP 端口，通常是 4420
Subsystem NQN
Host NQN 或 ACL 要求
远端 Namespace 容量
远端设备名 /dev/nvmeXnY
Namespace 是否独占
是否允许格式化
网络带宽和 MTU
是否有认证要求
```

其中最关键的是：

```text
Namespace 是否独占
Token 数据是否可丢失并重算
多个 GPU 是否需要共享同一份缓存
远端 SSD 是正式主存储还是只是溢出空间
```

这些会影响最终实验和论文表述。

---

## 14. 后续优化路线

功能维护方向：

```text
更细粒度的迁移恢复测试
rename/unlink 与多副本状态的更多边界测试
更完整的错误码和日志
更清晰的配置校验
多后端 remote SSD 池
多 GPU Host 共享元数据服务
```

性能方向：

```text
批量读写和大块顺序 I/O 优化
更接近 token/KV Cache 的 workload
真实 NVMe-oF 下的 fio baseline 对照
减少 FUSE 路径额外开销
预取窗口动态调整
缓存 GC 后台化
QoS 从简单 IOPS 限制升级为带权公平调度
```

论文实验方向：

```text
本地 SSD baseline
直接 NVMe-oF baseline
TokenFS baseline
TokenFS + AI 价值感知缓存保留
TokenFS + GPU 亲和感知副本放置
TokenFS + 多 GPU QoS
TokenFS full
P50/P95/P99 延迟
每 GPU 等待数据时间
Jain 公平性指数
SLO 违反率
```

---

## 15. 快速命令清单

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

查看当前状态：

```bash
./scripts/tokenfsctl.py status
```

查看文件：

```bash
./scripts/tokenfsctl.py files
```

查看副本生命周期：

```bash
./scripts/tokenfsctl.py replicas
```

查看指标：

```bash
./scripts/tokenfsctl.py metrics
```

检查一致性：

```bash
./scripts/tokenfsctl.py check
```

跑核心测试：

```bash
./scripts/integration_test.sh
./scripts/promote_test.sh
./scripts/prefetch_test.sh
./scripts/eviction_test.sh
./scripts/replica_lifecycle_test.sh
./scripts/advanced_policy_test.sh
```

---

## 16. 当前最新提交

当前主线已经完成：

```text
远端主副本 + GPU 本地热缓存副本生命周期
README 和 final-report 整合
三大创新点聚焦：AI 价值感知缓存保留、GPU 亲和感知副本放置、多 GPU QoS
```

最新实验结论和结果请看：

```text
reports/latest/final-report.md
```
