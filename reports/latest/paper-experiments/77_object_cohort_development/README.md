# 77：对象加权热点先验开发批次——12/16通过，尚未完成全指标验证

**本批数据完整性审计通过，但不是全部指标通过的最终结果。** 两个已检查输入、两个反向执行顺序轮次，共16个主比较，严格验收通过12个：热点H 3/4、亲和P 3/4、联合J 2/4、整体SIEVE对照4/4。不能只看汇总均值或动作哈希，就宣称三个创新点均已建立稳定的因果收益。所有失败轮次和原始数据保留，不与其他批次拼表。

四张完整数据表在 [validation/results/four-tables.md](validation/results/four-tables.md)，逐轮未取整结果在 `pairs.json`。吞吐为两轮总逻辑字节/总前台墙钟时间（MiB/s）；p99是两轮各自nearest-rank响应p99的中位数（ms），不是合并请求的p99。验收要求同轮吞吐提高、p99降低、包含后台排空的速度不下降、对应机制触发；消融还要求执行动作变化。这是预定的数值/机制筛查，不是统计显著性认证。

|消融或整体对照|移动热点吞吐变化 / p99降低|公开轨迹吞吐变化 / p99降低|同轮严格通过|
|---|---:|---:|---:|
|Full / NoHotspot|+0.206% / +0.962%|+1.522% / −0.232%|3/4|
|Full / NoAffinity|+7.183% / +1.585%|+2.415% / +0.316%|3/4|
|Full / NoJoint|+4.672% / −2.642%|+4.300% / +1.465%|2/4|
|Full / PoolSIEVE1|+4.868% / +1.711%|+18.887% / +7.395%|4/4|

前三行是完整策略分别去掉单项机制的消融；最后一行是整体策略比较。正百分比表示改善。汇总正向不覆盖逐轮失败。

## 仍未通过的四个比较

|输入与轮次|对照|吞吐变化|p99降低率|判定|
|---|---|---:|---:|---|
|moving_shared-74801-r2|NoJoint|−1.845%|−5.577%|吞吐、p99和排空速度均回退|
|public_toolagent-74802-r1|NoHotspot|+0.800%|−1.096%|p99回退|
|public_toolagent-74802-r1|NoAffinity|+1.172%|−1.103%|p99回退|
|public_toolagent-74802-r1|NoJoint|+2.895%|−0.358%|p99回退|

## H收益应如何解释

移动热点的Full/NoHotspot在两轮中，Full吞吐分别提高0.101%和0.311%，p99分别降低0.614%和1.306%，因而通过数值筛查；但两臂**每轮都是84次远端请求、28次完成拷贝、84个后台任务、696次物理pread**，远端/本地/RAM逻辑字节也相同。动作及放置位置的哈希不同，说明执行轨迹并非完全相同；它不能证明这些小幅性能差异是热点估值带来的强因果增益，也不能排除存储与调度波动。论文不能把这组结果写成“热点算法已经显著改善移动热点性能”。

相对LegacyCohortH，移动热点Full每轮只拷贝28次，Legacy分别73/71次；Full远端请求84/84次，Legacy80/77次。这支持新先验减少大量低价值复制、同时略增远端请求的机制解释。它是取舍而非所有子指标都变好。该单独诊断与NoHotspot消融回答不同问题，不能拿Legacy较弱来替代对NoHotspot的证据。

公开轨迹中Full/NoHotspot的两轮远端请求都是967/1002次、完成拷贝33/25次，体现热点策略用8次额外拷贝换取35次更少的远端请求，但第一轮p99仍回退。Full/LegacyCohortH则是**仅新人先验公式开关**的独立诊断。在固定成本模型里，这两种公式在公开输入上的输出相同；public74802各33条获准admission的cohort项均为0。此记录仅覆盖获准项，不单独断言全部被拒候选的prior都为0。实测第一轮Full和Legacy的访问/复制计数不同，不能直接归因于新人先验公式改善，应保留在线成本采样、异步时序与系统波动的解释；第二轮两者均967次远端请求/33次拷贝。详见单独的 `legacy-cohort-diagnostic.md` 与 `models/object-prior/`。

## 环境、控制变量与实现

- cn7客户端上三个逻辑GPU/缓存域，共用本地磁盘；cn13提供NVMe/TCP远端存储。串行请求，无物理GPU共享、NVLink、真实LLM推理或GPU算力收益主张。
- 固定 `moving_shared-74801`、`public_toolagent-74802`；六臂×两个输入×两个反向顺序轮次，**24次测速、27,648次请求**。每臂1,152次请求，每请求2 MiB，磁盘缓存总24 MiB、保留捕获RAM总4 MiB。
- 六臂为Full、NoHotspot、NoAffinity、NoJoint、PoolSIEVE1、LegacyCohortH。Legacy仅禁用新对象加权先验，是开发诊断，不是第四项创新。
- 所有臂共同使用O_DIRECT、RAM-first路由和直接读取尾片复用。77优化了尾片身份检查：只有可能存在剩余边缘数据时才提前fstat，消费尾片前仍完整验证身份。
- 77修复76的SIEVE公平性缺陷：RAM提前命中时，仍对真实可读且已resident的对应SIEVE条目更新visited；不创建条目，不伪造磁盘命中，不额外探测磁盘。该修复对所有主臂使用的公共路径统一生效。
- 每个非capture打开句柄额外最多4 KiB尾片载荷；本批实测峰值4096字节，在4 MiB捕获RAM外另计。该指标不含C++对象元数据，也不保证所有环境中全进程峰值恒为4096字节。
- 测速不做逐请求SHA；结束后验证保留副本内容。另有六臂各96次逐请求完整内容检查，合计**576次SHA校验**，与测速分离。

## 档案与复核范围

|对象|SHA256|
|---|---|
|冻结源码 `provenance/source.tar.gz`|`9a0c75c36674333212ad18b8b0a78fcb7ab9824c07d8bf2e80db45b424bbf156`|
|原始元数据归档 `provenance/evidence.tar.gz`|`27b4dcd44d843250230427d07a7fdfd058836a742e44ded5f2c0b5f9bd99aa2b`|
|运行二进制哈希凭据|`6334375577555abe6886db40a49f55f379f8291993880fdf6f8d5c4cdd2cf8cb`|

- `data/`：290个原始元数据文件，逐字节保留，包括请求、配置、SQLite、事件、二进制执行凭据和退出状态。元数据压缩包与这290个文件完全对应；不含二进制实体或缓存载荷。
- `provenance/`：原始源码/元数据包、340文件源码哈希、逐文件原始数据哈希、构建和测试日志。12项原生测试、155项Python测试通过；构建预检不混入正式576次内容检查。
- `validation/verify77.py`：离线解包冻结源码，在临时副本执行源audit/report，复算吞吐和p99、输入对象哈希、SQLite指标/访问次数、顺序及配置。原数据只读。两次独立执行的8个输出文件逐字节一致，见 `independent-review.json`。
- `validation/results/`：完整四表、20个逐轮比较（16主比较、4先验诊断）、机制记录及严格验收状态。`review.json`的`passed=true`是数据审计通过；`primary_all_passed=false`才是性能总验收状态。
- `models/object-prior/`、`models/capacity-boundary/`：只归档源文件及JSON/TXT/Markdown，不归档编译出的可执行文件。模型只支持机制和容量边界解释，不能代替实测速率/p99。详见 `models/README.md`。
- `diagnostics/tail-trace/`：两臂完整trace诊断已下载并独立审计通过，含27个原始文件、2,304次请求、冻结工具及逐请求拆分。这部分始终标为diagnosis_only，不进入四表，不修改本批主数据。诊断Full出现一次82.478ms物理pread且无copy重叠，不能归因热点复制；详细边界见其README。

审计验证了30份二进制哈希凭据，**没有离线校验二进制实体**（`binary_file_verified=false`）。不能将“凭据一致”写成“重新构建出了相同字节二进制”。两轮已检查输入属于开发验证，不能宣称独立确认、显著性或未见负载上的泛化。

从仓库根目录进入本报告目录后可复核；输出写入外部临时目录：

```sh
cd reports/latest/paper-experiments/77_object_cohort_development
python3 validation/verify-archive.py
review_dir=$(mktemp -d)
python3 validation/verify77.py --evidence data --source provenance/source.tar.gz --output "$review_dir"
```

预期数据审计通过，`full_acceptance_primary=12`、`primary_comparisons=16`、`primary_all_passed=false`。主批次后续诊断或实现修复必须另建证据；不能回写原始请求或删除四个失败比较。
