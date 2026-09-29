# 固定热点短窗口遗忘修复：18次开发验证

已定位并修复跨突发重访证据随短请求窗口消失的问题。修复采用容量有界的独立摘要：记录已完成突发长度及实际重访间隔，新旧对象对称估值；单次突发没有持续重访加成，过时证据逐渐衰减。默认关闭，通过persistent_run_reuse独立消融。代码修复不等于性能已过关，以下保留全部结果。

## 实际吞吐

|场景/种子|重复数|修复Full MiB/s|原策略WindowFull MiB/s|共享SIEVE MiB/s|相对原策略配对增益|相对SIEVE配对增益|
|---|---:|---:|---:|---:|---:|---:|
|stationary_shared/3271|2|173.281|173.871|173.126|-0.344%|+0.086%|
|stationary_shared/3291|2|174.960|171.542|168.755|+1.999%|+3.674%|
|moving_shared/3293|1|157.482|170.533|171.848|-7.653%|-8.359%|
|uniform/3273|1|105.560|103.025|82.639|+2.461%|+27.736%|

MiB/s=实际逻辑读取字节/前台墙钟，包含各服务层，并非TCP链路物理带宽。固定热点各2次重复，其他各1次；配对增益取同输入同轮次速率比的几何平均。已知开发输入，不是独立确认集，不估算可靠的总体显著性。

## 全部配对与保护指标

|输入|对照|速度变化|p99变化|排空吞吐变化|执行动作改变|小规模筛选|
|---|---|---:|---:|---:|---|---|
|stationary_shared-3271-r1|WindowFull|-1.324%|-2.313%|-1.326%|True|未通过|
|stationary_shared-3271-r1|PoolSIEVE1|-0.535%|-5.712%|-0.537%|True|未通过|
|stationary_shared-3291-r1|WindowFull|+2.446%|+1.435%|+2.447%|True|未通过|
|stationary_shared-3291-r1|PoolSIEVE1|+3.350%|-4.102%|+3.350%|True|通过|
|moving_shared-3293-r1|WindowFull|-7.653%|+4.822%|-7.651%|True|未通过|
|moving_shared-3293-r1|PoolSIEVE1|-8.359%|+4.307%|-8.359%|True|未通过|
|uniform-3273-r1|WindowFull|+2.461%|+4.118%|+2.461%|True|未通过|
|uniform-3273-r1|PoolSIEVE1|+27.736%|-13.461%|+27.925%|True|通过|
|stationary_shared-3291-r2|WindowFull|+1.553%|+1.481%|+1.552%|True|未通过|
|stationary_shared-3291-r2|PoolSIEVE1|+3.999%|-4.276%|+3.997%|True|通过|
|stationary_shared-3271-r2|WindowFull|+0.646%|-4.357%|+0.646%|True|通过|
|stationary_shared-3271-r2|PoolSIEVE1|+0.711%|-4.025%|+0.710%|True|通过|

预先定义：速度>0、p99不增加、排空吞吐不下降；对原策略的新增机制归因还要求执行动作改变。不设5%门槛，不删负结果。本轮5/12个比较通过，全部通过=False。

## 机制、每次速率与复制

|场景/种子|版本|每次MiB/s|热点淘汰次数|复制次数|新摘要参与计划次数|
|---|---|---|---|---|---|
|stationary_shared/3271|Full|171.707/174.855|0/0|30/30|93/93|
|stationary_shared/3271|WindowFull|174.011/173.732|4/4|34/34|0/0|
|stationary_shared/3271|PoolSIEVE1|172.630/173.621|0/0|30/30|0/0|
|stationary_shared/3291|Full|173.036/176.884|0/0|41/41|81/89|
|stationary_shared/3291|WindowFull|168.904/174.179|8/8|48/48|0/0|
|stationary_shared/3291|PoolSIEVE1|167.428/170.083|0/0|41/41|0/0|
|moving_shared/3293|Full|157.482|—|53|271|
|moving_shared/3293|WindowFull|170.533|—|49|0|
|moving_shared/3293|PoolSIEVE1|171.848|—|55|0|
|uniform/3273|Full|105.560|—|20|777|
|uniform/3273|WindowFull|103.025|—|21|0|
|uniform/3273|PoolSIEVE1|82.639|—|299|0|

热点标签仅用于固定热点结果的离线审计，没有进入策略。移动热点不能用固定key<8粗略统计，因此该列留空。复制和误淘汰减少只是机制证据，不能替代实际速率。

## 执行与复核边界

cn7连接既有cn13 NVMe/TCP存储，未使用cn14。每次576×2MiB，3个串行逻辑消费者；Full/WindowFull磁盘8/8/8MiB，SIEVE24/0/0MiB，均为24MiB磁盘与4MiB在途读缓冲。三个版本共用同一个Release程序，Full与WindowFull仅差persistent_run_reuse。O_DIRECT、SQLite FULL-WAL，未清全局缓存或改变远端存储配置。六个区组使用六种不同顺序；只有两次固定热点重复，顺序/噪声影响不能完全排除。

cn7重新编译并通过10项原生测试、106项Python测试；GitHub源提交CI36509876598成功。源提交c2c497be8975e35922715f8e16b6d81c23a0290c；程序SHA256=e78cf17c3fd8617053635dd3a4c127e96ea5b4ee21e323beb98001aa259a3a49。独立审计核对51个源文件、18组10368请求、原始SQLite、字节与复制成本守恒、后台排空、24MiB磁盘/4MiB缓冲上限和错误计数，并从原始墙钟重新计算速率/p99/全部比较。

测速没有逐请求哈希验证，不能声称本轮单独完成端到端数据完整性认证；现有原生测试及请求/成本审计通过。没有实际GPU、LLM推理、独立确认集或完整H/P/J新消融，不足以宣布整篇论文实验已完成。所有失败和负增益保留。

[草稿PR19](https://github.com/yxtmfz/tokenfs/pull/19)，未合并。复算：在同一目录解压provenance/source.tar.gz为run-reuse-source，raw/cn7-evidence.tar.gz为run-reuse-data，复制validation/review-run-reuse.py到该目录后使用Python3.12运行。
