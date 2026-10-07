# RAM capture value-retention: read-only implementation review

本审查未修改仓库或服务器。检查范围为当前冻结 `src/read_fill.h`、`TokenFS::Open/Read/Release`、`MeasuredPolicy::Ranked` 与已有 capture 测试。根任务要求先模型、后决定；模型负责人现已报告本轮候选均不具备晋升条件，因此本记录是保留设计依据，不建议为该候选安排实现或服务器运行。

## 可接入点与必须保留的语义

- `Open` 在选定并打开真实来源后调用 `measured_.Observe`，随后才调用 `fills_.Acquire`。Observe 的 policy mutex 已释放；保留此顺序可使 victim 排名使用截至当前请求的因果历史，但不能再次 Observe，否则重复计数。
- 实际 `Acquire` 在 **Open 阶段**逐出旧 capture 并预留新对象的整个 payload，当前请求尚未完成。只有完整有序 Append 并通过来源/anchor 身份校验后，Read 才执行 Retain。模型若在“新对象读完以后”才逐旧，是更理想的时序；partial/error read 在真实实现中可能已经失去旧对象。
- “总是接受当前新对象”只能解释为：不以新对象价值低为由额外拒绝，且有足够未 pin 旧 capture 能释放容量。两槽被当前 reader、Read handle 或排队/执行中的 copy 引用时，仍必须返回 capture_unavailable；不能偷增预算、取消 pin、强制覆盖旧数据。
- 4 MiB 是 active + retained + borrowed/copy pinned **payload 的共同上限**。2 MiB 对象时理想状态等于两个槽；不是额外获得两个 retained 槽。元数据/keys/ranking vectors 原本也不属于 payload，不能把“payload≤4 MiB”写成整个进程 RSS≤4 MiB。
- 只替换 `Acquire` 为腾出预算而选择的旧、已完成、未 pin retained victim；incoming 尚未进入 retained，自然不在候选集中。不能提前在 Retain 完成处做第二次逐出或选择是否接受 incoming。

## 最小可选 API（若未来有新证据再实施）

默认不传 selector，保持原 LRU 路径。只在确需回收预算、存在至少两个可选旧对象时调用同步 selector。selector 入参为只含 key、payload bytes、recency 的小型值对象列表；返回候选索引或 key。返回无效项、抛异常或无法构造候选快照应按原 LRU 回退，不影响数据读取。只剩一个 eligible victim 时直接用它，无需计算排名。

在 TokenFS::Open 中按该请求 caller 与原 Options 提供一个 **不逃逸**的同步 callback。其唯一策略调用为 `measured_.Ranked(caller, items, options)`；`front()` 是最低价值 victim。默认关闭新 flag；SIEVE 不传 selector，保留 LRU；Full/NoHotspot/NoAffinity/NoJoint 同用 selector，NoHotspot 唯一区别仍来自原 static reuse value 配置，其余模块的 Options 不得被暗中修改。若将 retained_capture=false 等 RAM 估值语义作为不同方案，应明确命名为另一个候选，所有相应消融臂保持同一语义，不能隐藏为旧 H。

RAM 的 Item coverage 不应调用 SSD `MarginalCoverage`（后者可因另一份 SSD 副本存在而返回 0）。RAM 命中仍能省下本地 SSD 服务。直接复用原价值排名时 coverage=1；如果引入 RAM 对本读/远读不同收益的权重，它是额外的跨层收益模型，需要单独冻结/解释，不能从已有 SSD 0/1 覆盖口径借来。

recency 只用于值相同的排序时，当前 retained 的 LRU 顺序已能提供确定性的先后关系。若模型/论文明确要求真实逻辑请求序号，则必须在 Open 的已完成 Observe 处记录一次序号，RAM hit 也更新一次；迟完成的 capture 只能保留其原请求序号，不能用完成时序覆盖更近访问。异步完成顺序与逻辑访问顺序不是一回事。不要用系统秒级时间戳替代逻辑先后。

## 锁序、pin 与预算风险

现可接受的 callback 锁序：`layout_mu → retained_mu → measured_policy.mu`。关键条件是 callback 纯计算，不重新进入 pool、layout、handles、metadata，不 stat/SQL，不写日志/触发复制；不能先持 policy lock 再调用 Acquire。Observe 在进入 Acquire 前已释放 policy lock。FindComplete 会先在 budget mutex 下取得弱引用的强引用，离开该锁后才做来源检查和 Retain；Retain 的 Buffer mutex 检查也在取得 retained mutex之前结束。

绝不能在持 `budget.mu` 时删除最后一个 Buffer 引用：Buffer 析构会再取得 budget mutex，形成自锁。现 Acquire 在 retained 锁下逐出，析构之后再检测 UsedBytes，正是为了保持计费与生命周期一致。排名回调也不要持 budget mutex。

候选快照不能保存额外 `shared_ptr<Buffer>`：这会把本来 use_count==1 的唯一池引用增加到 2，使对象被误判为 pinned。用 key/bytes/recency 值拷贝，候选身份在 retained 锁内有效。不要在 selector 里访问 Buffer 的可变数据、调用 ReadCaptured/Retain/FindComplete。

现 `use_count()==1` 检查与另一线程从 registry `weak_ptr.lock()` 取得 pin 之间可能交错。其现有安全保证是：若出现新 pin，Buffer 不会析构，bytes 继续记账，Acquire 继续重查预算并可能失败；不能把 use_count 检查称为严格原子的 pin 仲裁。FindComplete 随后还会 Retain 该仍然有效的对象。新 selector 至少需要在应用选择前再次验证 eligibility，不能凭回调开始时的 use_count 假定 payload 已释放。

不宜为了消除这个窄竞态顺手提前删除 `budget.paths[key]`：如果旧 Buffer 又被弱引用持有、期间创建了同 key 新 capture，旧 Buffer 的析构目前无条件 `erase(path_)`，可能删除新 registry 项。若未来决定改变 registry 生命周期，需要 generation/token 身份校验和专门并发测试；这超出单纯替换 LRU 的最小范围。维持原 registry/计费生命周期更稳妥。

其它风险：

- 当前 failed/duplicate Acquire 可能在最终 path 重复检查之前已逐旧，这是现有行为；不要在新策略分支顺便改它，导致对照混入另一项实现优化。
- SQL/SSD复制期间持有 fill 的 lambda 是真实 pin，不能忽略。串行请求模型的 instant-copy 假设不能证明实际两槽每次都可用。
- 回调排名与 key 快照会增加 Open 的 CPU 时间，并延长 layout/retained 锁持有。两槽仅比较两个对象时成本小但不是零；若模型收益本已很小，实际收益更不确定。
- callback 不应持有长期捕获的 TokenFS 指针或保存未来异步调用；同步参数可避免 pool/TokenFS 析构顺序与循环 ownership 风险。

## 如果未来重新实施，必要测试清单

1. Flag 默认关闭和 SIEVE 路径：固定访问序列与当前 LRU 的 victim、bytes、capture hit/miss 完全一致。
2. 两个 eligible 旧 capture、第三个 incoming：只逐最低旧值；incoming 必被保留到原 Append/Retain流程，new key不在排名候选中；值相同保持确定性的 recency/key 顺序。
3. 不额外复制 shared_ptr；一次 selector 调用不会把所有旧项变成“假 pin”。无压力或一个 eligible项时不运行 selector。
4. Reader pin、active copy pin、queued copy pin分别测试：被 pin payload内容完整、bytes不提前减少；两项都 pin 则 Acquire 失败且峰值≤预算，解除一项后恢复；候选被并发 FindComplete pin 时也不超预算或产生悬空引用。
5. callback 返回未知 key/越界 index/抛异常：回到 LRU，不破坏 registry、引用计数或已存内容；默认路径无额外 callback成本。
6. 不同大小对象需要逐出多个 victim：每步按仍 eligible 项选择并重算实际 UsedBytes；oversize、零大小、size不匹配不增预算，allocation失败不错误计费。
7. Partial、乱序 Append、源替换/修改、canonical anchor失效：不将未验证 capture发布为可借用；copy完成、SSD逐出不撤销仍有效的 capture。
8. 同 key 并发 Acquire/FindComplete、retained invalidation、pool销毁后尚有借用引用：registry与payload计费最终一致，无死锁/ownership cycle；如果 registry生命周期变动，增加旧Buffer析构不能删新generation条目的测试。
9. TokenFS集成：RAM hit与disk hit各Observe一次；当前访问确已Observe后才排序；current没有双计；NoH使用static、P/J原语义不变，SIEVE visited保持已有修复。
10. 真实四臂同冻结预算与负载报告 read_remote/local/inflight、capture_unavailable、eligible/pinned/selector次数、复制数、峰值payload/RSS、selector/Open成本和最终吞吐/p99/wall+drain。不能以模型命中率替代真实速度，不能掩盖对其它创新点的回退。

结论：技术接入可以做到局部、默认关闭、预算不变，但 pin、失败捕获、异步时序使模型成为理想化诊断。当前模型没有给出稳定跨臂 I/O 优势，就不值得承担新同步热路径和生命周期复杂度；保存此审查即可。
