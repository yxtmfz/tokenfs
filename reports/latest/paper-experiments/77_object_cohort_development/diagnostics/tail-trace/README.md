# 77 public74802 尾延迟诊断：完整采集，独立审计通过

这两次运行启用了request trace和控制路径profiling，**只作诊断，不是正式测速证据**。两臂均使用77同一冻结源码/二进制、相同完整1,152请求，按预定Full→NoHotspot顺序运行；逐请求SHA关闭，结束副本内容校验保留。没有删掉慢请求、缩短轨迹或重新选择有利轮次。

27个原始文件和原始包完整保存在 `data/`、`evidence.tar.gz`；压缩包SHA256为 `922670322c4e579e7825d843bc50ead4da8c1522779e3dbd7009610ba6e0d12d`。本地复核340个源码哈希、配置/驱动/输入/执行二进制凭据、2,304次请求、SQLite计数及指标、零丢失trace事件、时钟和handle映射均通过。见 `status.json`、`data/diagnostic-audit.json`、`review/analysis.json`。

## 观察结果

以下时间只用于定位，不能补进正式四表。

|诊断量|Full|NoHotspot|
|---|---:|---:|
|请求响应p99，ms|29.895|29.621|
|远端请求 / 完成拷贝|977 / 33|1002 / 25|
|后台提交 / 无收益规划|977 / 941|1002 / 977|
|最慢12个中：首次 / 复用请求|7 / 5|12 / 0|
|最慢12个与copy pipeline重叠|7|3|
|首次请求最后非空read非pread残差均值，ms|0.602|0.604|
|所有请求read非pread残差均值，ms|1.498|1.531|

最慢12个全部来自远端读取。Full最慢一次为请求index194：响应87.199ms，其中pread82.478ms，且没有copy pipeline重叠。这是物理读取尾部异常的直接观测，不能把它归于热点策略的复制。该单次异常也不等于p99本身：1,152请求的nearest-rank p99对应第12慢请求。

Full有更多复用请求和后台拷贝重叠进入尾部，这支持继续检查控制路径/拷贝竞争；重叠只说明同时发生，不能证明因果。两个臂最慢12个的平均read非pread残差分别2.950/2.964ms，几乎相同。Full top12平均pread较高受上述单个长读取影响，不应把top12均值误当p99变化的解释。

## 能支持的修复方向与边界

冻结源码中`Read`先记录`RecordLatency`和`AccountRequestReadCost`，再执行capture的Append/Retain/ScheduleSharedPlacement。`SubmitBackground`同步调用`metadata_.AddMetric(background_submitted,1)`，即使启用background metric batching也是如此。因此端到端响应及完整read span包含尾部提交成本，但当前read cost采样/histogram不包含该段。首次请求最后非空read约0.60ms的非pread残差，说明这里存在可检查的公共开销。

然而77没有Submit/Append独立时间戳；非pread残差还含分配、内存拷贝、计数、capture和调度，不能全称为SQLite fsync耗时，更不能预先承诺延后提交指标一定改善H消融。若优化计数发布，应共同应用于所有主臂，并保留submitted/completed一致性、异常恢复和readonly Release之后的持久化排空栅栏；不能通过漏记后台工作获得表面速率。

本次Full远端请求为977，而正式77两轮都是967。启用trace/profiling会影响在线成本与异步状态，因此诊断本身也改变了执行轨迹。这进一步要求把该数据与正式24组分开。当前观察不足以宣称已解决三个创新点全部尾延迟缺口。

自己的Release在这两个臂的top12请求中均未与client close前的区间重叠；它通常异步执行。不能把完整Release时间从客户端响应中重复相减，其他请求的Release重叠另列。copy/plan/release各类区间以union计算，但类别间可互相重叠，不可直接相加。具体每请求分解及12个最慢请求见 `review/Full-requests.csv`、`review/NoHotspot-requests.csv` 和 `review/tail-top12.md`。

## 离线复核

从本诊断目录运行；临时解包只用于导入原冻结源码，不执行服务器程序：

```sh
source_dir=$(mktemp -d)
tar -xzf ../../provenance/source.tar.gz -C "$source_dir"
python3 tools/tail-trace.py audit --source-root "$source_dir" \
  --diagnostic-freeze tools/tail-trace-freeze.json --output data
review_dir=$(mktemp -d)
python3 tools/tail-trace-analysis.py --evidence data --output "$review_dir/analysis"
```

分析输出目录必须是证据外的新目录。原始SQLite按只读immutable打开，若发现WAL/SHM等sidecar会拒绝，不忽略待提交数据。
