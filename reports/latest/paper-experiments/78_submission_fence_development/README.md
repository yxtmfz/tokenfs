# 78：后台提交计数延后发布开发批次——审计通过，性能12/16

**本批不是全部指标通过的最终结果。** 24次正式测速、27,648次请求以及576次独立内容SHA检查均通过完整性审计；16个主比较中12个通过逐轮严格验收。H、P、J、整体SIEVE比较各3/4。所有失败轮次、原始SQLite及旁文件均保留，不用77或诊断数据补齐失败格。

四张完整结果表在 [validation/results/four-tables.md](validation/results/four-tables.md)，所有未取整逐轮结果在 `validation/results/pairs.json`。下面只作概览：吞吐为两轮总字节/总前台墙钟时间，p99为两轮各自nearest-rank响应p99的中位数；正百分比表示改善，汇总正向不能代替同轮验收。

|比较|移动热点吞吐变化 / p99降低|公开轨迹吞吐变化 / p99降低|严格通过|
|---|---:|---:|---:|
|热点消融 Full / NoHotspot|+4.415% / +2.059%|+1.305% / +1.788%|3/4|
|亲和消融 Full / NoAffinity|+11.038% / +2.015%|+1.560% / +2.029%|3/4|
|联合消融 Full / NoJoint|+12.226% / +1.326%|+1.647% / +1.663%|3/4|
|整体 Full / PoolSIEVE1|+6.399% / +1.451%|+17.937% / +13.305%|3/4|

前三行是完整方案分别去掉单个策略机制，最后一行是整体比较。严格验收要求每轮吞吐提高、p99降低、包含后台排空的速度不下降，以及机制条件；消融还要求动作变化。主比较固定16项，不含下面的实现诊断。

## 四项仍未通过

|输入/轮次|对照|吞吐变化|p99降低率|失败原因|
|---|---|---:|---:|---|
|moving_shared-74801-r2|NoAffinity|+6.414%|−0.576%|p99回退|
|moving_shared-74801-r2|NoJoint|+8.505%|−1.274%|p99回退|
|moving_shared-74801-r2|PoolSIEVE1|+2.218%|−0.804%|p99回退|
|public_toolagent-74802-r2|NoHotspot|−0.908%|+2.658%|吞吐与排空速度回退|

`review.json`的`passed=true`表示数据可复核；`primary_all_passed=false`才是性能总验收状态。两轮已检查输入属于开发验证，不是独立确认，不支持统计显著性或所有负载均提升的主张。

## 本次实现修复及SyncSubmission对照

78把后台任务接受计数从每次前台单独SQLite同步写，改为与现有持久化计数批次一起发布。任务入队和计数受队列互斥保护；只有任务结束后才记录completed。事务失败时保留待重试计数、事件及错误观察，不丢弃或重复计数。核心缓存数据与复制事务的持久化策略未变。

所有五个主臂共同启用该优化；第六臂`SyncSubmission`只关闭 `defer_background_submission_metrics`，使用同一个78二进制、热点先验、公共读取路径、容量和Release fence。它是实现对照，不是第四项策略创新，不要求缓存动作变化，也不是78与77二进制的跨批比较。

|输入/轮次|Full/Sync吞吐改善|p99降低|Full/Sync远端请求|Full/Sync拷贝|
|---|---:|---:|---:|---:|
|移动r1|+10.415%|+2.637%|84 / 84|28 / 28|
|移动r2|+0.849%|+2.167%|84 / 84|28 / 28|
|公开r1|+4.189%|+0.743%|967 / 997|33 / 23|
|公开r2|+1.188%|+6.254%|997 / 967|25 / 33|

四项均通过含排空的实现验收，见 `sync-submission-diagnostic.md`。移动两轮的远端/本地/RAM次数、拷贝、物理pread、提交数和动作哈希均相同，是较清楚的公共实现对照。但r1的10.415%不能全部解释为省掉提交fsync：两臂前台时间6.080/6.713秒、CPU2.39/2.90秒，累积read计数时间3.265/3.449秒也不同；r2的吞吐改善仅0.849%。这些变化包含控制路径及系统运行波动，现有计数没有独立fsync时长。不可承诺稳定10%的实现收益。

公开两轮的实际路由与动作都变化，尤其第二轮Full多30次远端读取仍更快。因此应称为“实现与在线执行的综合效应”，不能把全部改善单独归因于少一次SQLite写，也不能将Sync对照的4/4自动算作H/P/J贡献。

## H仍需保留的证据边界

移动Full/NoHotspot两臂两轮依旧都是84次远端、148次本地、920次RAM请求、28次复制、84个后台任务，物理pread总量相同。虽然H的速度数字两轮正向，尤其r1数值较大，但没有减少物理工作量的证据；动作哈希不同也不是强因果证明。第二轮p99相差仅0.004945ms，不能写成稳健的热点尾延迟优势。

公开r1 Full比NoHotspot少35次远端请求、多8次拷贝，存在明确的读路径变化；r2则仅少5次远端请求、拷贝同为25次，最终吞吐回退。H的在线成本/异步路径敏感性尚未完全解决。真实失败应作为后续修改依据，不能缩容量、删首次访问或换有利轨迹后覆盖本批。

离线模型也支持收紧主张：固定移动74801输入下Full和NoH不仅远端/复制数量相同，模型中的远端请求`(时间序号,key)`序列与admission时刻/key也相同，差别主要在目的域和牺牲对象。模型不能替代实测速率，更不能把策略分数变化当作吞吐收益。

## 计时、环境与完整性

- cn7客户端上三个逻辑GPU/缓存域，共用本地磁盘；cn13为NVMe/TCP远端。串行请求，没有物理GPU、NVLink或真实LLM推理速度主张。
- 两个固定已检查输入，六臂、两轮反向执行顺序；每臂1,152请求×2 MiB，磁盘缓存共24 MiB，保留捕获RAM共4 MiB。所有臂相同O_DIRECT、RAM-first与尾片复用，保留77的SIEVE逻辑visited公平性修复。
- 每个非capture打开句柄额外最多4 KiB尾片载荷；本批峰值4096字节，单列于4 MiB捕获RAM之外，不含C++对象元数据。
- 响应p99包含真实loader/IPC/调度及前台I/O；它不声称包含每个异步Release或后台任务的最终完成时间。另测`completed_with_background_s`并用于验收，不能通过未计最后后台工作抬高总收益。
- 六臂都有新配置键，Sync=false也要求Release fence。有效只读Release在可能的fallback提交后仅计数一次并持久化；drain同一SQLite快照要求`read_release_count==请求数`且`submitted==completed`。关停后若这几个计数或I/O计数又改变，benchmark拒绝该运行；离线再次校验。
- 测速不做逐请求哈希，结束后校验保留副本。六臂各96次内容运行单独逐请求SHA，共576次；其含哈希时间不进入速度表。

## SQLite采集防线的真实触发与处理

第一次采集源audit通过，但随后检测出24个测速库都有WAL/SHM，于是**在打包前拒绝**；见 `provenance/collect.log` 和哈希与预审记录一致的 `collect-rejected.sh`。只读stat确认24个WAL全部0字节，24个SHM全部32768字节。它们与对24个测速库使用`mode=ro`源audit的行为相符，但没有audit前的旁文件清单，不能唯一认定创建来源；本地只读复现未成功，未把猜测写成事实。

修复的是采集/离线工具，不是实验代码或原数据库：完整保留全部48个旁文件，不checkpoint、不删除、不重跑实验。只允许无旁文件或成对“0字节WAL+32768字节SHM”，随后immutable只读quick_check，并比对原result中的metrics和请求访问计数；非空WAL、缺配对或未知journal仍拒绝。0字节WAL没有待合并帧，故此限定下读取主库不会漏读WAL中的提交。

30个主库及48个旁文件的采集前尺寸/SHA、打包后检查及最终原始包内容完全一致。全部记录在 `data/provenance/sqlite-sidecars.json`、`provenance/sidecars.log`、`validation/archive-copy-review.json`。339个原始文件全部保存，其中包含这48个旁文件及新增的保全凭据。

## 档案清单与离线复核

|对象|SHA256|
|---|---|
|冻结源码|`c9ba5be4549aae563594a09c110a53d1b95a99bd63d033910b36bfbd4e4eeb76`|
|原始339文件归档|`c994514a33387c48200b2c99b2a1392d8c5f78b5345e2483e95d5ff211503211`|
|运行二进制凭据|`fa7450237ef5fc4a9291ed79f057f48bb858caed784c7ff56a454e242ae58cfe`|

`provenance/`保存源码/原始压缩包、345个源文件哈希、构建/测试/采集脚本和完整SQL事件记录；`data/`逐字节保存339个原始文件。12项原生测试、161项Python测试通过。离线验证30份二进制哈希凭据，未持有二进制实体，`binary_file_verified=false`，不声称完成同字节重构。

`validation/`包含独立验证器、四表/20逐轮比较、计时邻近样本与机制说明、历史预审及旁文件处理测试。预审中的“拒绝所有sidecar”是采集失败前规则，后被明确保全空WAL规则取代；其原日志和旧collector哈希保留，不伪装旧检查已经覆盖后来的情况。

`diagnostics/runtime-method-review/`保存78结果生成前对77及78冻结方法的审查，原文字保留，其数字不是78最终结果。`diagnostics/telemetry-local/`保存实际类代码构成的本地ASan/UBSan正确性harness源码、构建脚本、日志及README，两个来源文件哈希与冻结78一致；不含可执行文件/dSYM，不代替Linux/FUSE或O_DIRECT测试。

`models/migration-model/`完整保存360臂离线模型及54次前缀检查（216验证臂）的源码、所有TXT/TSV/JSON、README；仅排除本机可执行文件。负结果、非对称执行机会诊断及公平common-RAM对照均保留，未只挑有利模式。模型使用固定成本和瞬间复制，没有实测速率/p99，当前没有新H估值候选被该模型充分支持。

从仓库根目录复核，分析输出放在原始数据之外：

```sh
cd reports/latest/paper-experiments/78_submission_fence_development
python3 validation/verify-archive.py
review_dir=$(mktemp -d)
python3 validation/verify78.py --evidence data --source provenance/source.tar.gz --output "$review_dir"
```

预期数据审计通过，主验收12/16且`primary_all_passed=false`，独立Sync实现验收4/4。分析脚本是历史开发来源；部分保留原工作目录依赖，不承诺迁移后原模型生成命令可直接执行。当前可移植复核入口是上面两个验证器。
