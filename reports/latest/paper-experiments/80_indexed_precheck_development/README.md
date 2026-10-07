# 80：索引预筛开发批次——主比较 11/16，索引对照 0/4

**本批没有达到四表逐轮吞吐与 p99 全部提高的目标，也不支持把索引候选宣称为稳定的整体提速。** 24 次真实速度实验、27,648 次请求和独立的 576 次内容 SHA 检查均通过完整性审计。主 H/P/J/SIEVE 比较完整验收为 **11/16**；Full/NoIndexedPrecheck 的实现诊断为 **0/4**。全部正负结果保留，没有选轮次、补换样本或修改门槛。

四张完整速率表见 [four-tables.md](validation/results/four-tables.md)，所有逐轮比较见 [pairs.json](validation/results/pairs.json)。吞吐用两轮总字节/总前台墙时汇总，p99 用两轮各自 nearest-rank p99 的中位数，不是混合请求 p99。完整验收另要求包含后台完成的速率不退化、相应机制触发与消融动作变化；汇总均值不能掩盖失败轮次。

|主比较|移动负载通过|公开负载通过|本批可支持的结论|
|---|---:|---:|---|
|Full / NoHotspot|1/2|2/2|公开输入双轮正；移动吞吐仍有回退且无服务 I/O 减少|
|Full / NoAffinity|1/2|2/2|公开输入双轮正；移动第二轮 p99 回退|
|Full / NoJoint|1/2|2/2|公开输入双轮正；移动第二轮 p99 回退|
|Full / PoolSIEVE1|0/2|2/2|公开负载双轮正；移动两轮 p99 均回退|

主比较的五个失败项如下。正值表示改善，负值表示回退：

|负载/轮次|对照|吞吐变化 %|p99 降低 %|drain 速率变化 %|
|---|---|---:|---:|---:|
|moving r1|PoolSIEVE1|+2.884034|−0.085334|+2.881184|
|moving r2|NoHotspot|−1.145009|+0.609495|−1.144941|
|moving r2|NoAffinity|+5.143704|−0.537579|+5.142230|
|moving r2|NoJoint|+6.234795|−1.186596|+6.233058|
|moving r2|PoolSIEVE1|+1.901347|−0.499160|+1.898583|

## 受控实现改动

在 79 相同的 fresh、独占管理、不可变缓存生命周期检查通过后，`indexed_shared_precheck` 可创建两个 partial covering indexes，缩小预筛 resident 查询扫描的元数据范围。SELECT 本身、谓词、UNION ALL 的重复行语义及原有校验不变。普通建立失败保守回退；同名异定义不被 DROP；事务无法恢复时必须失败退出。

Full/NoHotspot/NoAffinity/NoJoint 只差各自一个原始消融开关，均启用相同索引实现。NoIndexedPrecheck 与 Full 只差 `indexed_shared_precheck=false`，仍执行 79 的提交前预筛、deferred submission 与 Release fence。PoolSIEVE1 虽配置索引开关为 true，但不属于 measured precheck 模式，不建立或执行这些索引路径。所有臂使用全新应用缓存和数据库，避免历史索引污染禁用对照。

30 个实际 DB 均经独立 immutable 审计：20 个 indexed DB 必须存在两个正确索引，10 个 NoIndexed/SIEVE DB 必须均不存在；核验 sqlite_master 完整定义、所属表、大小写敏感的谓词、非唯一/partial 属性、覆盖列顺序与排序规则，不只检查启用计数。所有启用臂 `index_enabled=1`、`index_fallback=0`，控制/SIEVE 两计数为 0。

这属于公共元数据实现优化，不是新的 H/P/J 策略贡献。索引维护和写入成本仍计入端到端结果；更快的查询可改变线程交错及在线成本采样，所以实际动作不保证完全相同。只以本批 NoIndexedPrecheck 作实现对照，不能把 79/80 跨批时间差当作受控增益。

## 查询工作减少，没有稳定转化为总收益

独立索引对照全部保留，见 [indexed-precheck-diagnostic.md](validation/results/indexed-precheck-diagnostic.md)：

|负载/轮次|吞吐变化 %|p99 降低 %|drain 变化 %|完整验收|
|---|---:|---:|---:|---:|
|moving r1|−1.528613|−0.624098|−1.528635|失败|
|moving r2|−0.460838|+0.870283|−0.460856|失败|
|public r1|+2.038938|−0.485475|+2.038873|失败|
|public r2|−0.379285|+1.870457|−0.379551|失败|

公开负载的汇总吞吐 +0.822%、p99 降低 +0.704%，仍是 **0/2 逐轮通过**；不能凭汇总正值宣称成功。

|负载/轮次|整段 precheck 累计 ms：Full / NoIndex|每 attempt μs：Full / NoIndex|remote：Full / NoIndex|完成 copy：Full / NoIndex|
|---|---:|---:|---:|---:|
|moving r1|12.225 / 13.359|145.536 / 159.036|84 / 84|28 / 28|
|moving r2|12.265 / 13.581|146.012 / 161.679|84 / 84|29 / 28|
|public r1|145.573 / 231.432|150.541 / 232.128|967 / 997|33 / 23|
|public r2|147.619 / 226.710|149.563 / 234.447|987 / 967|25 / 33|

这里记录的是整个 `submission_precheck_us`，含 SQL、锁、路径/元数据处理和策略判断；不是独立 index/query 计时，也不包含所有索引维护成本。公开负载每次尝试约从 232–234 μs 降至 150 μs，局部成本下降有证据，但无法直接据此推导整体墙时。

- moving r1 两臂动作摘要、服务请求与 I/O 总工作相同；预筛累计仅少 1.134 ms，Full 整轮反而多 101.954 ms、daemon CPU 多 0.10 s。现有计数不能把差额唯一归因索引维护、后端波动或调度。
- moving r2 服务请求数相同，但 indexed Full 多一次完成复制与一个后台任务，动作摘要不同；不能将该轮当成完全相同执行序列的纯查询微基准。
- public r1 Full 少 30 次 remote、多 10 次 copy；public r2 Full 多 20 次 remote、少 8 次 copy。在线执行分支改变，端到端结果同时包含路径/复制差异。不能把第一轮 +2.039% 全部归于 SQL，也不能由第二轮回退断言索引的局部工作量未减少。

完整 24 次运行的 precheck 计数/最大值/均值、真实 I/O、CPU、复制、动作摘要、p99 邻近秩和 20 个配对见 [mechanism-diagnosis.json](validation/mechanism-diagnosis.json)。

## H 证据边界仍未补齐

移动 Full/NoHotspot 两轮仍同为 84 remote / 148 local / 920 RAM。第一轮两者完成 28 次 copy，第二轮 Full 为 29、NoH 为 28。真实 pread 操作/字节总数相同；目的地/动作摘要变化并不等于热点估值降低服务成本。该批移动 H 汇总吞吐 −0.380%，不能主张“创新一稳定提速”。

公开 H/P/J 和整体比较本批双轮正，可作为这两个既有开发输入下的证据；不能据此说上一批的缺陷已被因果解决，更不能扩展为物理 GPU 或 LLM tokens/s 的结论。两个已检视输入、两轮不足以建立统计稳定性或普遍优越性。

## 测试与环境

cn7 为单客户端、三个逻辑缓存域、串行 caller，cn13 提供远端 NVMe-oF/TCP 存储。没有物理多 GPU/kernel/NCCL 测量。moving_shared seed 74801 / public_toolagent seed 74802，每臂 1,152 次、对象 2 MiB、总磁盘缓存 24 MiB；两轮使用 seed1050000+input seed 的预定逆序。速度驱动在子进程创建前绑定 `[0,2,4,6]`，48 个 before/after 回执通过。绑定不表示独占核心或固定 CPU 频率。

计时请求不做逐请求哈希；另外 6 臂×96 次真实内容请求共 576 SHA 全部正确，哈希时间不进入速度表。服务器 Release 构建的 12 项 native、166 项 Python 测试通过。单元测试日志中的 fixture 内容打印不算作服务器内容 sweep。

最后 Release 与后台提交完成通过同一快照 fence 检查，drain 等待计入完成时间，daemon 停止后计数不得变化。所有 capture payload 峰值 4 MiB，另外每个非 capture 打开句柄最多 4 KiB tail payload（本批峰值均为 4 KiB）；不能称整个进程 RAM 只有 4 MiB。

30 主数据库与 48 个 sidecar 完整保留。24 对 WAL 均为空、SHM 32 KiB；确认 WAL 无内容后才读 immutable 主库并核对 SQL 与结果；原始 DB/sidecar 无删除、无 checkpoint、无改写。339 个原始文件与下载 tar 全部一致，两次独立复算 8 个输出逐字节一致。

## 来源与非测速附录

- source 355 文件 SHA：`f6691da87b5cf91edc594cad618562f77f0de5fb8a6060fb395f69fc64bfbd45`；binary 执行回执：`f5e2981b8b4f0ce54bb2994e53998608de4cec4a3c861531e8e86e0aab031f71`。本体未打包，30 个执行哈希回执核对一致。
- 原始 tar SHA：`baa5f35623e2faaba17068407621a5519d44abaac027dd3961a80f2f7515ed27`。冻结源码、采集工具、构建/内容/审计日志完整保留。
- [CI #113](https://github.com/yxtmfz/tokenfs/actions/runs/37622605042) completed/success；原始工具请求明确指定 commit `bf52430e4fa5e8cd2e3fb6b024f3a73ed6f89e03`，原始响应本体没有重复该 SHA，二者封装在 `provenance/ci-receipt.json`。
- [实际类 sanitizer harness](diagnostics/local-harness/README.md)保留源/哈希/log，剔除 native 二进制。其 full-scan steps 4101→3 是查询工作检查，不是速度证据。
- [独立索引审查](diagnostics/index-independent-review/README.md)保留最终源码身份与早期问题修复记录。SQLite 查询 proof 使用历史 79 DB 的内存副本，不能当作 80 真实测速；索引定义/回滚等最终 native 测试另有日志。
- [tail79 只读诊断](diagnostics/tail79-readonly/README.md)明确属于旧 79：五个失败配对/5,760 行匹配不能当作本批样本；重复请求实际 tier 和逐请求 pread 未记录，不按延迟阈值猜测。
- [run-unit 模型](models/hotspot-run-unit-review/README.md)保留 80 个模型臂及 60 个前缀 case/240 个验证臂，主要 moving74801 仍为 84 remote/28 copy，不晋升。模型值不是墙时/p99。
- [79 extra-read 诊断](models/hotspot-extra-read79/README.md)保留 29 个纯文本文件及 3 前缀/9 比较：模型中的 84 vs77 是 16 个 Full 独有 remote 与 9 个 SIEVE 独有 remote 的净差，不是真实逐请求 source 标签。不能挑出“7 次读”就推算实际节省。
- [planning cost 只读审查](diagnostics/planning-cost-review/README.md)针对 80 源码和旧 79 计数；提出单次锁内精确复用的可能性，同时明确没有实测瓶颈或速度保证，未作为本批实现。
- [已执行的 moving trace](diagnostics/moving-trace/README.md)新增的是诊断附录：Full/NoHotspot 共 2,304 个请求、双重复核一致。实际全部同序号请求 tier 相同，最慢 12 个均首次 remote、无 copy pipeline 重叠；这不增加主速度轮次或内容 SHA 样本，原四表与源码未变。
- [FUSE callback 只读审查](diagnostics/fuse-read-review/README.md)使用历史 77 trace、本地 3.14 头文件和既有 6.8 kernel 回执，注明上游版本推断与 Ubuntu 补丁/未捕获握手的局限。它反驳“三次均为数据远读”的假设，不构成新内核检查或 80 性能测量；未打包或运行库二进制。

归档检查（不运行模型或服务器）：

```sh
python3 validation/verify-archive.py
```

重新复算真实源码/请求/SQL/索引证据，输出放到 raw 目录外：

```sh
python3 validation/verify80.py --evidence data --source provenance/source.tar.gz --output /tmp/tokenfs-batch80-review
```
