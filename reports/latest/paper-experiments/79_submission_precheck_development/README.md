# 79：提交前预筛开发批次——11/16，尚未全部通过

这是冻结版本、两个已检视输入、两轮反序的开发实验，**不是独立确认，也没有实现四表逐轮所有指标均提升**。完整验收为吞吐提高、请求 p99 降低、包含后台完成的速率不退化，并满足消融机制/执行动作检查。24 次测速、27,648 次请求及另行 576 次内容 SHA 校验全部通过数据审计；主性能比较通过 **11/16**。NoSubmitPrecheck 是单独的实现诊断，通过 **3/4**，不计作第四个策略创新。

完整的四张速率/p99 表见 [four-tables.md](validation/results/four-tables.md)，逐轮全部正负数值见 [pairs.json](validation/results/pairs.json)。两轮汇总吞吐是总字节除以总前台墙时，p99 是两轮各自 nearest-rank p99 的中位数，不是混合请求 p99；汇总改善不能替代逐轮验收。

|主比较|移动负载通过|公开负载通过|结论|
|---|---:|---:|---|
|Full / NoHotspot|1/2|1/2|热点收益仍不稳定，移动负载没有减少 I/O|
|Full / NoAffinity|2/2|0/2|移动亲和收益明确到本批两轮；公开负载吞吐两轮均负|
|Full / NoJoint|2/2|2/2|本批联合消融四项通过，不代表普遍优势|
|Full / PoolSIEVE1|1/2|2/2|移动第二轮 p99 回退，公开负载两轮均提高|

未通过项全部保留。下表正值表示改善，负值表示回退：

|负载/轮次|对照|吞吐变化 %|p99 降低 %|drain 速率变化 %|
|---|---|---:|---:|---:|
|moving r2|NoHotspot|−0.147670|+1.223576|−0.147107|
|moving r2|PoolSIEVE1|+2.671530|−0.413440|+2.668911|
|public r1|NoHotspot|−0.264726|+0.791475|−0.264733|
|public r1|NoAffinity|−0.535432|+0.474323|−0.535497|
|public r2|NoAffinity|−0.043872|+2.627458|−0.044026|

## 实现改动与受控比较

默认关闭的 `precheck_shared_submission` 在完成且来源校验通过的捕获之后，针对当前观察快照执行保守的乐观收益检查，提前拒绝明显无法获益的后台提交。它只在 fresh、独占管理、不可变缓存生命周期和受支持的共享估值配置中启用；现有排队任务仍保留最终来源、容量、pin 和收益检查。根目录非空、遗留 resident 元数据、无效路径/重复尺寸、锁忙、部分捕获等情况回退原路径。

这不是旧排队策略的输出等价优化：排队任务可能在稍后的需求与成本状态下重新判断。应同时报告新增前台 SQL/估值成本、少提交的任务，以及实际访问和复制变化。NoSubmitPrecheck 与 Full 只差这一开关；H/P/J 各自也只差对应策略开关。所有臂共用对齐尾缓存、RAM 优先路由、object cohort prior、提交计数 fence 和 Release fence。PoolSIEVE1 不受新的利润门控限制。

本批速度驱动在创建子进程之前绑定 CPU `[0,2,4,6]`，位于同一 socket 的四个不同物理核。24 个 case 的前后 48 个亲和回执独立复核通过。Linux 子进程继承该集合；没有逐线程实时运行核回执。`schedutil` 与非独占负载仍可能影响时间。**78 未作此绑定，不能把 78/79 的时间差作为预筛因果增益。** 实现因果比较只使用本批 NoSubmitPrecheck。

## 实际机制与剩余缺口

移动 Full/NoHotspot 两轮均为 84 remote / 148 local / 920 RAM、28 次完成复制、28 个后台任务，真实 pread 总操作/字节也相同。虽然放置目的地与动作摘要有变化，这不证明 H 减少了服务成本。第二轮 Full 比 NoH 多 9.740 ms，总吞吐回退 0.148%；不能把第一轮的小幅正值作为稳定热点收益。

公开负载的亲和对照：第一轮 Full 为 997 remote / 23 copy，NoAffinity 为 1010 / 21；第二轮为 967 / 33 对 995 / 21。减少远端请求没有转化为吞吐优势。Full 的 shared placement plans 为 219/186，对照为 85/94；daemon CPU 多 0.31/0.43 s。额外规划/复制成本与节省服务相互竞争，但计数不能唯一分离在线成本变化、复制时机和调度影响。不能只以 remote 更少宣布优化成功。

预筛诊断见 [submission-precheck-diagnostic.md](validation/results/submission-precheck-diagnostic.md)：

|负载/轮次|Full / NoSubmit 后台任务|Full / NoSubmit remote|Full / NoSubmit 完成 copy|吞吐变化 %|p99 降低 %|
|---|---:|---:|---:|---:|---:|
|moving r1|28 / 84|84 / 84|28 / 28|+2.412465|+0.744747|
|moving r2|28 / 84|84 / 84|28 / 28|+0.027753|+0.182235|
|public r1|81 / 967|997 / 967|23 / 33|−0.452179|+2.650834|
|public r2|70 / 988|967 / 988|33 / 32|+0.603925|+2.100935|

moving 的动作摘要及 I/O 总工作相同，但两轮墙时节省分别 158.468 ms 和 1.830 ms，不能认定固定幅度收益。public 的动作/路径确实变化；第一轮虽少提交 886 个任务，却多 30 次远端读而吞吐下降。Full 的 public 预筛计数器累计耗时为 223.943/217.377 ms，平均每次尝试 224.617/224.795 μs，约占前台墙时 0.85%/0.84%。这些累计时段是成本诊断，不是可直接相减得到的因果墙时收益。完整 24 次运行、所有 20 个配对的预筛、服务请求、规划、CPU、p99 邻近秩、亲和与负载回执见 [mechanism-diagnosis.json](validation/mechanism-diagnosis.json)。

## 测量、正确性与资源边界

cn7 单客户端、远端 NVMe-oF/TCP 存储，三逻辑缓存域/串行 caller；没有物理多 GPU 或 GPU kernel/NCCL 测速。本批 moving_shared seed 74801 / public_toolagent seed 74802，每臂 1,152 次、每对象 2 MiB、总磁盘缓存 24 MiB。请求 p99 包含客户端发起、读取和返回的端到端响应；前台吞吐使用完整请求循环墙时。另收取最后 Release/后台任务 drain，并逐轮要求其速率不退化。

最终 SQLite 同一快照验证 `release == open == requests` 与 `submitted == completed`；daemon 退出后的 I/O/提交计数不得变化。计时阶段关闭逐请求 SHA；6 臂内容 sweep 各 96 次、共 576 SHA 单独运行，hash 时间不进入速率表。12 项 Linux native 与 163 项 Python 通过；源打包/单元测试中打印的 3×96 fixture 内容回执不计入这 576 次真实服务器内容校验。

所有臂 capture payload 峰值 4 MiB。对齐尾缓存是每个非 capture 打开句柄最多额外 4 KiB，实测该独立 payload 峰值均为 4 KiB；未把它算进 4 MiB capture 限额。元数据及进程 RSS 另计，不能声称总 RAM 只有 4 MiB。

SQLite 原始 30 个主数据库及 48 个 sidecar 全保留：24 对 WAL 均 0 字节，SHM 均 32 KiB；6 个内容 case 无 sidecar。收集前后 SHA 不变，先确认 WAL 为空再以 immutable 方式读取并逐项复算。未删除 sidecar、修改数据库、隐藏待回放日志或重新运行测速。

## 来源与附录

- 冻结 source 350 文件：`623debd261469ae7377c6072ceb3333f425abf2014bb686f4b153a56f16ffb65`；二进制构建/执行回执：`fa02620a8982818ca6bf99067bc3a57166211fc056ab8cebdc223a27f5728e27`。归档未包含二进制本体，30 个执行哈希回执已核验。
- 原始 evidence tar：`eeb92841aeaaf02a76ffc5ff33ec9e6556a0dc41ac52ee79757456526e2db96f`，339 文件全部与下载件相同。两次独立复算的 8 个输出逐字节一致，见 [independent-review-agreement.json](validation/independent-review-agreement.json)。
- CI：commit `34e73888406800dbd0d2d465287e04ef4059507b`，[Evidence regression #111](https://github.com/yxtmfz/tokenfs/actions/runs/37617725915) completed/success；原始连接器回执保存在 `provenance/ci-receipt.json`。服务器冻结构建日志另行保留。
- [预审](validation/preaudit-brief.md)保留 18 个定向验证检查：亲和/开关错误必须拒绝、禁用臂不得执行预筛、内容短前缀允许零尝试、正汇总不能掩盖坏轮次。synthetic fixture 仅测试验收逻辑，不是性能数据。
- [本地 sanitizer harness](diagnostics/local-harness/README.md)保留真实类/测试源与日志，剔除可执行文件。它不是 Linux 挂载/O_DIRECT 测试。[独立上界审查](diagnostics/precheck-bound/prefilter-independent-review.md)及源码/日志保留 110,592 次受限当前快照上界检查，不宣称未来排队任务等价。
- [public78 分支诊断](models/public78-branch/README.md)为 78 历史机制复核，不能替代本批速度；[RAM 排名模型](models/ram-value-model/README.md)保留 120 臂及 90 个前缀 case/360 验证臂，结果不支持晋升候选。它们使用固定成本/简化执行，不是实际吞吐/p99。原始纯文本包和文件 manifest 均保留，无执行文件。
- [grace 反事实](models/grace-counterfactual/README.md)另保留 40 个原始臂、40 个新开关臂和 60 个前缀 case/240 验证臂。Full 相对原 immediate decay 为 1 个输入改善、2 个恶化、7 个不变，四个移动输入均不改善；不晋升该开关，不能用它宣称已补上 H 的实际速度缺口。
- [RAM retention 只读审查](diagnostics/ram-retention-review/ram-retention-readonly-review.md)保存预算、pin、锁序和实现时机约束；未在本批实现 RAM 排名。

复核全部归档与模型已有前缀（不执行模型或服务器）：

```sh
python3 validation/verify-archive.py
```

重新执行独立源码/SQL/请求审计，输出必须位于 raw 数据外：

```sh
python3 validation/verify79.py --evidence data --source provenance/source.tar.gz --output /tmp/tokenfs-batch79-review
```
