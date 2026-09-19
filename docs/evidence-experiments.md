# 按真实速率判断贡献的消融实验

本页替代旧实验“命中率或模拟 objective 越好即策略越好”的解释。主依据为相同任务的 `job_wall_s` 与 `logical_bytes / job_wall_s`，后台收尾、尾延迟和资源开销同时报告。结果可以否定某个组件的性能贡献。

## 分类与可证实的结论

| 类别 | 对照 | 能检验什么 | 不能据此推出什么 |
|---|---|---|---|
| 整体性能 | RemoteOnly、LRU-equal、LFU-equal、AURA-core | 同一真实 FUSE/NVMe-TCP 路径上的完整任务耗时与实际吞吐 | 优于所有缓存算法、物理 GPU 推理 TTFT 提升 |
| 单组件：淘汰 | AURA-core vs no-value | 固定准入、亲和、后台执行，仅价值 victim 相对 LRU 的贡献；必须实际淘汰 | 没有淘汰时不能判断价值规则有效 |
| 单组件：准入 | AURA-core vs no-gain | 复制收益门槛是否减少无效搬运，并转化为实际提速 | 准入与淘汰不能合成一个含糊的 no-value |
| 单组件：亲和 | AURA-core vs no-affinity | 保留跨域缓存能力时，使用需求归属来决策的贡献 | 不能把禁止跨域复制当作去掉亲和算法 |
| 架构功能 | AURA-core vs no-xgpu | 跨逻辑 GPU 缓存功能的贡献 | 不等于多物理 GPU、PCIe/NVLink 或真实 Peer 网络扩展性 |
| 单组件：趋势 | AURA-core vs no-trend | 当前 C++ 长短窗口与趋势修正的贡献 | 不能替代 Python 概率需求区间的校准与实证 |
| 单组件：预取 | AURA-prefetch vs AURA-core | 编号顺序预取在可预测和随机 trace 上的净收益 | 不得只展示可预测顺序访问，也不代表真实模型前缀预测 |
| 协同 | E0A0、no-affinity、no-value、AURA-core | 价值淘汰×亲和放置的时间交互项 | 四格不等于完整 RobustBenefit 控制器优于 independent |
| 系统开销 | AURA-core vs synchronous | 同一策略后台异步执行相对同步执行的速度与尾部影响 | 异步不等于零前台开销，后台 drain 不能漏报 |
| 适用边界 | stable/scan/mixed/shared_shift/uniform/sequential，多容量 | 局部性、大小、容量和共享变化下收益何时成立/消失 | 单个手工 trace 不能代表生产负载 |

四格定义：E0A0 两者关闭；no-affinity=E1A0；no-value=E0A1；AURA-core=E1A1。按配对块计算 `T11-T10-T01+T00` 与置信区间。每个命名变体都有测试验证配置只改变指定字段；多个因果因素不能偷偷同时关闭。

基线的具体语义：LRU 用每个缓存域的最近逻辑读取序号；LFU 用该域在本次运行内的累计访问次数，驱逐后不清零。两者使用读取两次后准入的 read-through 规则、同一 caller-local 复制能力、关闭预取。每次运行重建 SQLite 与空应用缓存，不跨轮保留热度。no-gain 只关闭收益/复用门槛，仍保留亲和规则和硬容量约束；no-value 只换淘汰规则，准入中的价值项继续保留。

本批 cooldown 与最短驻留均设为0，以便在短任务内触发容量竞争；因此本批不检验防抖动的贡献。短长窗口为2秒/10秒，但单任务不是长时间稳态服务，趋势结果也受此范围限制。

`AURA-core` 特意不命名为“完整论文 AURA-Joint”：当前真实 C++ 仍是工程启发式实现，Python EvictionLoss/ReplicaGain/RobustBenefit 并未整体接入 FUSE。no-uncertainty、完整 independent-vs-joint、真实重计算/推理实验尚不能用一个空开关冒充完成。是否需要补这些实现，取决于论文保留的主张；现有结果不能支持它们的真实加速结论。

## 已实施的测量与正确性修复

- 读取策略访问统计不再绕过本地快路径。访问粒度是一轮成功工作负载 read-only open；每轮完整读一个 shard。LRU 使用持久化访问序号，避免秒级时间戳无法区分连续访问；LFU 用目标缓存域的次数。
- LRU/LFU ReadThrough 可通过同一复制路径创建 caller-local 副本；这些副本进入普通容量竞争与淘汰候选。
- 后台使用单工作线程与有界队列，统一约束复制并行度，退出前 join；前台计数与后台 submitted/completed 支持收尾验收。同步消融的复制也使用同一复制互斥，避免并行超配。
- 复制校验完成后才提交 READY，布局更新仅写布局字段，避免覆盖更新中的访问/亲和状态。新 benchmark 限定不可变、远端已有 canonical 的只读对象。
- 指标按事务批量持久化；采集等待最后 Release 指标落盘，避免将尚未完整的快照当作丢字节。副本和淘汰动作保存为 policy-events。
- 模拟器增加 COPYING/READY 时间和共享后台复制队列，来源在动作前确定；在途容量只预留一次，在途副本不能成为淘汰候选。修复 LFU 双计数。模拟仍不作为真实性能证据。
- 旧入口清缓存失败会报错退出，结果目录不再覆盖，分段计时不能再标为完整 wall-clock。新实验入口无需 sudo，也不会清共享机器全局缓存。

## 真实测量口径

入口 `scripts/evidence_benchmark.py`，需 Linux、FUSE 与已经挂载的独立 NVMe/TCP namespace。入口绑定 sysfs 的 transport=tcp、目标 IP 和 NQN，禁止把本地 NVMe 或未挂载的后备目录混入。

主耗时从第一条正式请求发出到最后一条完成，使用客户端 `monotonic_ns`；包括 IPC、排队、文件打开、实际完整读取和关闭。对象预置、进程启动、验证及报告生成在外；后台 drain 单列，同时报告含 drain 的完成时间。不将已重叠的后台耗时重复相加。

所有策略同一二进制、数据、trace、初始应用缓存状态、每域配额、复制工作线程和复制校验规则。逐请求全内容 SHA256 仅用于正确性验收；正式性能运行关闭该额外验证开销，运行后仍完整校验留下的副本，复制路径本身维持一致校验。

两种缓存条件分开成批：

1. 默认：预热 backing 文件、清空应用缓存，FUSE direct_io，但底层读取有页缓存。这是暖后端系统表现。
2. `--backend-direct`：前台本地和远端都使用 O_DIRECT，同样的 4 KiB 对齐缓冲；不支持即失败，不悄悄退回 buffered。准备阶段只对本次自建远端文件发出 fadvise；不宣称它清空目标端 loop/backing 缓存。该模式代表客户端直接读的真实协议路径，不是两端物理盘全冷实验。

cn7 本地目录与 cn13 loop 后端都不是独占裸 NVMe，目标端可能存在其他任务争用。自然网络不注入延迟，结果按实际测得的 MiB/s 判断。

## 执行顺序与判据

1. Python 回归、真实 C++ 元数据/访问顺序回归。
2. `--verify` 小规模验收：所有读取与 canonical 全哈希一致、无短读、源字节与请求字节相同、缓存不超配、后台正常结束。不能把这一批开销含哈希的数字当作正式性能结果。
3. 容量压力验收：保存真实 EVICT 和副本动作；未触发的对照标为未检验，而不是宣告组件有效。
4. pilot 采用开发种子，估计时长和方差；决定正式样本量后冻结配置。
5. 正式用预先指定种子，块内随机策略顺序；同块所有策略使用相同 trace。不得根据输赢删轮次、追加到显著或改负载。
6. 每场景报告全部运行、平均实际总耗时/吞吐、相对 LRU 的配对时间比与按块 bootstrap 95% 区间；时间比 <1 表示更快。样本不足不生成假置信区间。
7. 多重比较和单组件配对、四格交互需在最终报告中单独处理，不能只给每策略平均数。任何“显著提高”必须有匹配的区间/检验支持。

示例（必须使用全新 output 名称，不能复用历史目录）：

```bash
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-eval-20260919
export LIBRARY_PATH="$TOKENFS_TOOLS_ROOT/usr/lib/x86_64-linux-gnu${LIBRARY_PATH:+:$LIBRARY_PATH}"
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release -j 4
python3 scripts/evidence_benchmark.py \
  --binary build-release/tokenfs --profile paper \
  --output /home/wjxt/aura-kv-cn7/evidence/unique-run-id \
  --remote-root /srv/tokenfs/remote-cn7 \
  --backend-direct --seeds 201 202 203 204 205 206 207 208 209 210 \
  --scenarios stable scan mixed shared_shift uniform sequential \
  --requests 96 --shard-mib 4 --quota-mib 8
```

该示例重现 formal-02 的固定 trace；它不是为后续调参提供新的未知测试集。正式速度运行前应另用 `--verify` 完成全内容校验，校验批次不能纳入性能统计。

输出包含 manifest（源码/二进制/入口 hash、真实设备身份、配置）、每块 trace 和顺序、每组解析配置/请求/动作/文件快照/结果或失败记录，以及汇总 JSON/CSV。原始报告不能手动拼接；旧 cn14 数据和修复前模拟结果保留为历史资料。

## 论文完成的标准

每项速度结论都要指向真实运行与适用条件。如果价值消融没有更慢，价值组件的净速度贡献就未得到支持；如果 full 只提高命中而实际更慢，就不能称整体性能更好；如果只在部分场景获益，应写明边界。真实推理、生产 trace、完整联合模型、现代额外基线、并发与故障专项尚未产生对应证据前，不作已经完成的声明。
