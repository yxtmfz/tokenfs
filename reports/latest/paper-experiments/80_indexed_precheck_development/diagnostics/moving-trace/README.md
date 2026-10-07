# 80 移动负载 trace：已实际执行并完成双重复核

这两组诊断已在主测速结束后执行：Full、NoHotspot 各 1,152 次 moving_shared/74801 请求，共 2,304 条真实请求。沿用 80 原二进制与 355 文件源码冻结，仅增加 `request_trace_path`；`profile_control_path` 仍为 false。**它们是诊断，不是新增速度轮次，也不替代原始 11/16 主结果或 0/4 索引对照。** 请求没有逐次 SHA；原 driver 在计时后校验保留副本，原批次的 576 次内容验证仍单独计数。

`tools/README.md` 和冻结工具 manifest 中的 prepared/not-executed 是执行前历史记录，按原 SHA 完整保留，不能改写工具冻结来更新状态。本文件是执行后的记录。原拟议 public Full/NoAffinity 草案未作为这次诊断运行；本次确定运行的是 moving Full/NoHotspot。

## 实际结果与证据边界

两个独立 audit 均通过，JSON 相同；7 个分析输出逐字节一致。每臂 9,408 个 trace events、丢弃 0，source/binary/config/input、CPU `[0,2,4,6]`、Release/drain、SQL 和两个实际 partial indexes 均核验。数据目录 27 文件、两个 SQLite DB、无 sidecar。原始 tar、工具 tar 和文件哈希完整保留。

|诊断项|Full|NoHotspot|
|---|---:|---:|
|实际请求数|1,152|1,152|
|首次 remote|67|67|
|重复 remote / local / RAM|17 / 148 / 920|17 / 148 / 920|
|真实 pread 总操作|696|696|
|真实 pread 总字节|486,539,264|486,539,264|
|完成 copy / 后台任务|28 / 28|28 / 28|
|最慢 12 个请求|全部首次 remote|全部首次 remote|
|最慢 12 个 copy pipeline 重叠|0|0|
|诊断 p99（ms，不作性能验收）|26.965899|26.816452|

这里首次/重复请求的实际 tier 是由 trace 的唯一 handle 与客户端区间关联得到，未根据时延阈值猜测。**两臂全部 1,152 个同序号请求的 tier 一致，但 44 个请求的 location 不同**；层级相同不等于放置动作完全相同。本次没有 H 导致服务层减少的证据。

Full 最慢请求为 index 844/key17，响应 71.248458 ms，pread span 合计 67.382246 ms，且无 copy pipeline 重叠。同序号请求响应差 47.400895 ms，占这一次诊断墙时差 62.704546 ms 的约 75.6%；这些数字不是原 80 正式测速的同一次运行。它是单个远端冷读异常跨度，不能当作 p99 本身，更不能仅据此归因后台复制、网络或设备；pread 时段也可能包含调度等待。两臂各自 p99 是第 12 慢请求，双方 top12 的并集为 16 个逻辑序号，完整保留于 [same-ordinal-top12-union.tsv](review/same-ordinal-top12-union.tsv)。所有请求同序号配对见 [same-ordinal-all.tsv](review/same-ordinal-all.tsv)。

该 trace 记录 pread **时段**与逻辑字节，没有逐请求实际 pread 操作/物理字节/offset。因此逐请求 physical I/O 字段继续为 null/空，不能以 callback 数冒充系统调用数，也不能把 EOF 的非零 pread 时间当成一次数据传输。真实物理操作/字节仅能报告整臂计数。

最慢 12 个请求自己的 Release 均在客户端 close 之后，不能把其完整 flush 时长加到本请求响应中。其它 Release、shared plan 与 copy 的相交时段也只说明关联；这些类别相互重叠，不能相加当作互斥原因。Read 的 non-pread 剩余量含计数、分配、复制、capture、调度等，不能直接称为 SQL 或 fsync 成本。两个顺序诊断无独立重复，tracing 自身改变时序；不能用于证明稳定提速或为原先无 trace 请求补填实际 tier。

详见[独立结论与时间分解](independent-review/independent-findings.md)。本诊断没有发现新的、足以解释 H 未改善的已定位代码缺陷，不支持继续按正负号微调估值或重复测速等待四表全正。它不证明 H 在其它容量和负载下无效，但当前输入缺少独立的层级或净 I/O 优势。首次冷读 p99 也不能靠修改复用估值凭空消除。

## 归档与复核

- 原始诊断 tar SHA：`c71dec53662c741e0423814c8a8ff050a34ce97094f81dcd448d7a789e2e7fb1`。
- 原冻结工具 tar SHA：`540c7eddf7362313aca0dccf1b4cbe62d17e770ceb433e7503038a3f5b5c87c7`，12 文件原文不变。
- [provenance/agreement.json](provenance/agreement.json)记录 27 raw 文件与 7 分析文件哈希；两份原 audit 均保留。
- [protected-primary80-hashes.json](provenance/protected-primary80-hashes.json)锁定原 339 速度/内容原始文件、8 个主分析输出与冻结 source/evidence 包。附录加入后这些文件未变。
- 工具 [独立审查](../fuse-read-review/moving-trace-independent-review.md)是运行前记录，最终执行状态以两份通过的真实 audit 为准。

若需重新审计，在临时目录解包报告 `provenance/source.tar.gz`，使用这里原文保留的 `tools/tail-trace.py audit` 指向该源码、`tools/tail-trace-freeze.json` 和 `data/`；再用 `tail-trace-analysis.py` 输出到新的临时目录。禁止对 raw 写入或重新生成冻结工具覆盖原包。调用示例保留在历史 `tools/README.md`，这不是再次执行服务器实验的指令。
