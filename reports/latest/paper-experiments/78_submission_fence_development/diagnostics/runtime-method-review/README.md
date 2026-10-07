# 77/78 运行时量测与最小后续诊断审查

本审查只读取本地冻结的 77 原始记录、追踪和当前冻结 78 源码；没有连接服务器、启动新实验或修改仓库源码。78 结果尚未纳入本文。`analysis.json` 为描述性诊断，不能替代验收表；`analyze_local.py` 可复现数字。

## 已能确定的事实

77 的 H 消融（Full 对 NoHotspot）：

| 场景/轮次 | 吞吐提升 | p99 降低 | 少读远端对象 | 少提交任务 | 多复制对象 |
|---|---:|---:|---:|---:|---:|
| moving r1 | 0.101% | 0.614% | 0 | 0 | 0 |
| moving r2 | 0.311% | 1.306% | 0 | 0 | 0 |
| public r1 | 0.800% | -1.096% | 35 | 35 | 8 |
| public r2 | 2.257% | 0.652% | 35 | 35 | 8 |

- Moving 两臂两轮均为 remote/local/RAM = 84/148/920，复制 28，提交 84。动作顺序/位置 hash 不同只能证明策略执行不同；这些计数不能证明 0.10%–0.31% 的速度差来自更少 I/O。对应两轮最慢 12 个请求全部首次访问；H 对这些请求无法消除其首次远端数据读取。
- Public 两轮均是 Full remote/local/RAM = 967/183/2，对照 = 1002/148/2；35 次远读变成本读，增加 8 次复制，构成可解释的收益机制。共 1152 请求中 864 次是对象首次访问（75%），只有 288 次是重复访问。H 对重复访问的平均响应改善分别为 1.475/1.702 ms，但首次访问平均响应差为 +0.249/-0.106 ms，足以影响总体小幅收益和尾部方向。
- Public Full 每轮 967 个后台任务中 934 个最终 no_gain，其中 897 个在全域乐观预判时拒绝，未生成 resident snapshot。这是明确的无效提交开销机会，但 897 是**后台决策时刻**计数，不是安全前台预筛可省任务数的证明。

## 现有 profile counters 不足以精确归因

以下来自 77 同源、仅诊断的 Full/NoHotspot 两组追踪；启用 tracing 的数据不并入冻结速度表。

| 计时口径 | Full | NoHotspot | 含义 |
|---|---:|---:|---|
| 全部 shared_plan trace 时间 | 0.3480 s / 977 次 | 0.3469 s / 1002 次 | 包含被拒任务与布局锁等待 |
| shared_plan_latency counter | 0.0476 s / 36 次 | 0.0290 s / 25 次 | 只在成功选择目的域的函数尾记录 |
| trace 中 Read 回调总时间 | 22.5392 s | 22.7975 s | 完整 Read 回调 |
| read_latency_us_total | 21.5290 s | 21.7748 s | 在 capture 和调度之前取样 |
| Read counter 未计入的后段 | 1.0102 s | 1.0227 s | capture、策略更新、提交、记录等混合项 |
| Release flush 总时间 | 0.7785 s | 0.7696 s | 含 flush mutex 等待与 SQL 事务，无法再分 |

具体限制：

1. `PlaceShared` 在大量 no_gain/covered 等早返回之前有 trace span，但 `RecordLatency("shared_plan",...)` 只在函数尾；不能拿该 counter 除以 background_submitted，也不能据此称规划只占 0.048 秒。
2. `Read` 先取 `latency_us`，随后才 `AccountRequestReadCost`、`ReadFill::Append`、`ScheduleSharedPlacement`。同步 `background_submitted` WAL 事务发生于后段；`request_cost_remote_us` 和 `read_latency_us_total` 不能测出其完整成本。78 此项优化可能改善实际速度而这些计数不变，这是预期的口径差异。
3. 追踪中远端请求的最后一次有效数据回调 pread 为 0（尾片复用），该回调平均约 0.60 ms；本地约 0.039 ms。它支持检查远端后处理开销，但没有独立 SubmitBackground/SQLite 时间戳，不能把全部差额叫作 fsync。
4. Full/NoHotspot Release 总耗时约 0.79/0.78 秒，但与对应客户端请求的直接重叠仅 0.021/0.009 **毫秒总和**；Release 通常在客户端 close 返回后异步执行。其开销可通过下一请求、锁竞争或最终 drain 体现，不能把 Release 总时间直接加到每请求响应上，也不能因 close 很快就忽略它。78 的 read_release_count 屏障与最终计数一致性检查解决了提前 drain 的观测问题。
5. `pread_ns` 包含内核、块设备、NVMe/TCP 与调度停顿；没有 block/network/CPU off-CPU 细分。Full 最大异常请求为 87.199 ms，其中 pread 82.478 ms，证明异常主要发生在数据调用中，但不能确定是哪一层，也不能删掉该请求。p99 是第 12 大样本，这一个最大离群点不等价于整个 p99 回退的原因。
6. open_layout_wait 只测 layout mutex；Open 的 SQLite 元数据锁/事务没有单独计时。Release flush 是总段，无法区分 flush mutex、MetadataStore mutex、SQLite SQL/WAL/同步。后台 copy overlap 是时间区间相关性，不是阻塞原因或可相加的成本。
7. 主速度测试 profile=false；其粗 read buckets（0.1/1/10/100 ms）不能重建精确 p99。精确 p99 应始终用完整 requests.json 的 response_seconds。该响应包含 loader/IPC/调度；已有 tracing 的 IPC/调度均值约 0.25–0.29 ms，不能将它当噪声直接减掉。
8. 两轮和每轮 1152 个相互相关的请求不能支持稳定小收益的显著性结论。保留逐轮方向、p99 邻近排序值和全部失败；不能把请求当独立样本来制造很窄的置信区间。

## 78 完成后先做零额外运行分析

按预定义全部 24 臂审计，包括每臂 requests、release_count、submitted/completed/error、冻结哈希、后台等待口径。然后同批 Full/SyncSubmission 四个配对逐一比较：

- 若远/本/RAM 请求数、复制数、动作序列、提交数相同：这是最清楚的同步提交实现开销比较；同时报告真实 wall、p99、wall+drain，不拿 read_latency counter 替代速度。
- 若动作或 I/O 数改变：异步时序改变了在线策略的实际路径，收益应称“实现与在线执行的综合效应”，不能全部归因于少一次 WAL 同步。记录变化方向，尤其是否少复制/多远读。
- Full/NoHotspot 仍需独立比较。共同优化即使让 Full/SyncSubmission 明显变快，也不自动建立 H 的消融收益。Moving 若仍同量 I/O，只能报告小幅观测差；public 的远端→本地替代才是更直接机制证据。
- 用现有 requests 离线分首次/重复访问，并检查 p99 第 11/12/13 大附近值。分类只用于解释，完整总吞吐和总 p99 的验收口径不变。

目前不建议再启动 shadow 或追踪服务器实验。只有 78 同批结果仍无法区分控制路径与远端读取问题、且需要据此选择下一次代码修改时，才考虑**一个固定配对**诊断（Full/SyncSubmission，相同完整输入和容量，追踪仅诊断）。复用现有 span 已能区分 pread 与 read 后段；若仍不足，新增诊断专用 submit span（queue lock wait、同步 SQL 总段）、worker flush span（等待/事务总段）、覆盖所有早返回的 plan span，再做相同配对。不要一次同时改策略、计时、工作负载或容量；更不要为 p99 加人工延迟或挑请求。

## 前台乐观预筛：值得探索，当前不能宣称等价或稳赚

现有 `HasReuseEvidence` 在 adaptive_control 时恒 true，是 cold public 请求大量排队再拒绝的来源。目标可以是避免“肯定没有容量探索机会、即使忽略 victim loss 也不盈利”的后台任务，不改盈利阈值。

必要条件：

1. 只在明确 immutable readonly、TokenFS 管理独占 cache 目录、当前 shared/measured 分支支持的状态启用。未知状态、模式或容量证据不足一律照常提交。
2. 对**所有允许目的域**证实 `free_bytes_upper < object_bytes`，才能关掉 free_headroom 分支。依据必须是 used 的可信**下界**；过高的旧 used snapshot、旧“已满”布尔值都会误拒已释放容量的请求。Pinned、临时文件等未计入可以让下界偏低，结果只是少筛掉任务。
3. 在同一一致 policy 快照上，按该臂原 Options 对每个允许域运行原 `PotentiallyProfitable`。Full/NoHotspot/NoAffinity/NoJoint 共用预筛实现，但必须保持各自 static H、可用位置、joint/noise 语义。NoJoint 不得重新收取 victim/noise 费用；SIEVE 没有原 profitability gate，不能加上 H gate 改造 baseline。
4. 保留后台最终容量、源身份、pin、复制收益 recheck。负面结果不得缓存到下一请求；下一次访问必须能因新证据重新触发。
5. 即使对提交时刻的乐观上界证明成立，也不等价于原任务稍后在后台使用更新后的历史/成本所作决定。这属于调度时机变化，必须显式评估。未来若需 shadow，仅记录前台拒绝预测与原后台最终 admit/拒绝的冲突；此处不启动额外 shadow 运行。

### 两条实现路径比较

| 路径 | 优点 | 风险/成本 | 判断 |
|---|---|---|---|
| 全 mutation 原子 used 下界/容量 epoch | 前台接近 O(域数)，无 SQL | 每种 evict/unlink/truncate/recovery/重命名都要先失效或扣减；漏一个就可能误拒；已有队列/成本版本仍需处理 | 不是本轮收口的最小修改 |
| readonly 限定 + try_lock(layout) + READY 元数据下界 | 复用现有删除串行化，改动更局部 | 当前 PlanningResidents 的 SQL/锁并不便宜；需限定状态不变量、去重物理路径、处理 metadata 锁等待 | 更适合先评估，但不能直接调用现有全快照 |

READY 路线的可行约束：

- 当前 measured shared readonly 路线的容量驱逐在 `EnsureLocalCapacity` 持 layout_mu 下进行，canonical 先转 DELETING_CACHE 再删除；replica 删除后删元数据也在该锁内。新复制先物理 rename，后发布 COMMITTED/READY，遗漏尚未发布对象只低估 used。该限定下，当前 READY/COMMITTED 行可作为候选下界来源。
- 这不覆盖任意外部 rm/truncate、带陈旧 READY 行的重启、非 measured 的 ReconcileCrossGpuReplicas、可写/rename/unlink路径。只看 readonly 配置不足以证明上述不变量。初始非空/不可证实状态应禁用预筛或初始化验证，不能仅相信元数据大小。物理路径去重，防止 canonical/replica 行别名双计；查询所有实际驻留字节，不采用去掉 pinned/protected objects 的 victim snapshot。
- `try_lock(layout_mu_)` 失败立即正常提交。成功后若调用现有 `PlanningResidents()`，仍会阻塞在 MetadataStore 的 mutex；该 mutex 可能被 FULL-WAL telemetry 事务持有。所以它不是无等待快速路径。若做此候选，宜新增只读 `TryReadyResidentBytes`：metadata mutex 也 try_lock，单语句聚合 READY/COMMITTED 的位置与字节，不取 recency，不 JOIN gpu_access，不 stat/fs 遍历；无法立即取得锁就回退。SQL 执行本身仍非零，try_lock 只限制锁等待。
- 已用 77 public 只读 DB 执行 EXPLAIN：files 表有 864 行、READY 集合 12 行；现 `PlanningResidents` 会 SCAN files、SCAN local_replicas 并 join access 表（见 planning-query-plan.json）。每个远读引入这类前台扫描，会把后台已通过 optimistic reject 避免的 897 次 snapshot 成本重新加回来。优先使用更小聚合查询；不要在 ScheduleSharedPlacement 假设已经有全域 resident snapshot，当前那里仅有 incoming FileMeta。
- 新的只读 aggregate 如无 tier/state 索引仍扫描 files；不能仅因为输出 3 行就称 O(3)。不要为了这个诊断暗中加索引改变每次写成本。先本地功能/锁序/Query Plan 评估，78 raw 确认问题仍存在后才考虑实现和同批对照。

预筛的收支应写成：少掉的 queue + worker plan + worker telemetry fence **可兑现的等待/CPU**，减去每次尝试的前台锁/SQL/三域 policy 判断和新增 buffer counters 成本。后台开销可能与前台 I/O 重叠，不能把 0.30 s 被拒 plan 总和或每任务 flush 时间直接当作 wall 收益。78 已去掉前台 submission 持久化后，预筛的边际回报应在 78 上判断，而不是用 77 原事务成本高估。

## H 机制的可支持表述

77 的 object-weighted newcomer prior 防止同一个热点反复返回，把所有新对象的先验不断抬高：每个 retained object 至多提供一份 recurrence 支持。它是有界、因果、按对象计数的收缩先验，**不是校准的返回概率**；不同对象年龄/截尾机会不同。历史仍以逻辑 run 为单位，不等价于实际磁盘复用；RAM 捕获可能吸收部分预测回报。max(recent,persistent,burst,cohort) 也使某些机制变化被其他分量遮盖。因而该新机制的实测支持应落在减少无益复制、保住有用复制及实际远端读取变化，不能仅用先验值更合理或 action hash 不同证明速度。

当前足够明确的定位：H 在 public 有一致的读路径改善机制；moving 在当前容量下两臂的物理工作量已等量，小收益未独立归因。应保持这个边界，先读完 78 全批；不为制造 H 差异而临时缩容量、改工作负载或删首次读取。

复现离线分析：

```sh
python3 work/hotspot-submission78/runtime-method-review/analyze_local.py
```

脚本根据自身路径定位 work/hotspot-object77，因此可从任意 cwd 运行；只写本目录 analysis.json。原始证据不变。
