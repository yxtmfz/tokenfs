# Report76 independent audit and repair brief

审计通过：336个冻结源文件、24次测速（27648请求）、6组独立内容检查（576 SHA）、30份执行/配置凭据、SQL指标/访问次数、反向执行顺序及源码报告精确复算。源包和原始证据未修改。二进制核验为执行SHA凭据，未取得实际可执行文件。

## 严格主比较：5/16通过

通过条件为吞吐增加、端到端p99降低、含后台排空耗时不退化，且机制真实触发；消融另要求动作变化。H 0/4、P 1/4、J 1/4、SIEVE 3/4。不是全部通过。

|负载/轮次|对照|吞吐变化%|p99降低%|drain变化%|机制/动作|通过|
|---|---|---:|---:|---:|---|---|
|moving_shared-74801-r1|NoHotspot|+0.456|-0.735|+0.455|True/True|否|
|moving_shared-74801-r1|NoAffinity|+3.153|-1.268|+3.154|True/True|否|
|moving_shared-74801-r1|NoJoint|+9.884|-0.645|+9.884|True/True|否|
|moving_shared-74801-r1|PoolSIEVE1|+0.701|-4.352|+0.701|True/True|否|
|public_toolagent-74802-r1|NoHotspot|-0.555|-2.697|-0.551|True/True|否|
|public_toolagent-74802-r1|NoAffinity|+0.098|-0.950|+0.101|True/True|否|
|public_toolagent-74802-r1|NoJoint|+1.845|-0.583|+1.849|True/True|否|
|public_toolagent-74802-r1|PoolSIEVE1|+16.603|+9.362|+16.685|True/True|是|
|moving_shared-74801-r2|NoHotspot|-1.579|-1.089|-1.578|True/True|否|
|moving_shared-74801-r2|NoAffinity|+7.591|+1.606|+7.589|True/True|是|
|moving_shared-74801-r2|NoJoint|+18.206|+0.820|+18.201|True/True|是|
|moving_shared-74801-r2|PoolSIEVE1|+11.905|+0.322|+11.901|True/True|是|
|public_toolagent-74802-r2|NoHotspot|+0.990|-1.735|+0.991|True/True|否|
|public_toolagent-74802-r2|NoAffinity|+1.959|-0.026|+1.958|True/True|否|
|public_toolagent-74802-r2|NoJoint|+1.657|-0.709|+1.657|True/True|否|
|public_toolagent-74802-r2|PoolSIEVE1|+15.416|+9.152|+15.409|True/True|是|

## 创新一：局部节省被复制和控制开销抵消

移动热点 Full 的两轮远端读取为154/152 MiB，NoH为168/168 MiB；确实少读14/16 MiB。但Full复制71/74次，NoH仅28/28次，增加43/46次2 MiB写入。Full planning为208/205次，NoH为38/38次；snapshot为147/149对56/56；乐观拒绝仅7/7对176/176。Full比NoH每轮CPU多0.19s。RAM读取两者均1840 MiB、920个RAM请求，新的磁盘复制没有增加这部分收益。不能仅据复制数判断每个副本无效，76未采逐副本生命周期trace。

公开回放Full每轮比NoH少读70 MiB远端，多8次复制。复用请求累计响应时长改善约0.265/0.462s，但首次请求累计时长增加约0.417/0.199s，净吞吐一轮负一轮正，p99两轮均负。说明估值有局部服务收益，当前后台/控制开销把冷读尾部推高。不要退回全局关闭cohort或一刀切提高阈值；此前74已证明那会丢掉有用复用。下一轮应按因果证据约束仍在RAM中对象的磁盘迁移价值，并对copy/plan预算进行可归因诊断。

## RAM-first：会纠正虚假disk-touch，但不是已证实的全面加速

移动r1 Full与NoRAMFirst远端/本地/RAM字节、复制次数、placement plans完全相同。路由计数peer_cache_hit从425降至75，cross_gpu_local_replica_hit从145降至23，replica_touch_batched从570降至98；真正peer_cache_read_bytes仍同为150 MiB。故修复确实去除了RAM命中上的无用探测和磁盘touch，不是减少真实peer读取。移动r2也类似（435→76、139→21、574→97）。公开回放只有2个RAM请求，故收益上限很小。

RAM-first独立四对比仅1/4双指标且drain通过：moving r1吞吐+2.234%、p99降低+0.865%；r2为−2.961%、−2.317%；public r1为−0.917%、−0.956%；r2为+1.004%、−1.067%。原study对NoRAMFirst沿用动作改变门槛会把r1标False，但实现优化可在动作完全相同时有效；主16消融门槛维持不变，此实现对照独立解释。

## SIEVE公平性缺口必须先修

RAM-first在Open中先把tier改为inflight，从而跳过后续仅在tier==local时执行的sieve_.Hit。旧路径在RAM覆盖选择前已标记SIEVE resident visited。与此同时MeasuredPolicy::Observe仍收到全部逻辑请求，包括RAM命中。因此这次“公共读路径修复”实际也改变了SIEVE输入命中流，不能把它造成的基线退化归作Full算法收益。

应在RAM已命中时仅查询SIEVE已有resident map，按照旧路由优先级和peer/private权限标记实际READY resident的visited位；不创建resident、不增加disk-hit或peer-read指标、不访问磁盘。这样RAM快速返回与SIEVE原始逻辑命中语义可以同时保留。76数据保留为历史开发诊断，不改冻包、不重写结果。该修复进入77后应重新同批比较。

## 其余失败与下一步优先顺序

P在moving吞吐两轮均正，但r1冷读p99反向；公开回放吞吐均正但p99均负。J在moving少复制（Full71/74 vs NoJ120/120）并减少远端读取（154/152 vs240/240），局部价值明确；公开NoJ本地请求平均成本约10.35/10.39ms，Full约8.41ms，符合减少复制干扰的解释，但仍不足以保证Full p99降低。

最慢12条中moving Full两轮均12条首次访问；公开Full为10/12、5/12，NoH均12/12。公共p99并不全部由固定冷读底线决定，已有重用请求进入尾部。76没有逐函数trace，不能给未测的锁、fstat或SQL各自分摊精确责任。

1. 先修SIEVE逻辑Hit公平性并跑语义回归。
2. 77 aligned tail的冗余fstat优化已有本地单测和sanitizer，尚无服务器测速，不提前声称有性能收益。所有arms共同启用。
3. 对H优先检查RAM已满足连续需求时的迁移估值与后台计划放大；保留公开回放长期复用，不全局禁cohort。需要一个冻结候选与小规模配对，不按正负结果挑选运行。
4. 若进一步实测，增加极小的独立trace诊断拆出公共回放Full慢请求的open/read/release/排队位置，性能正式批次继续关闭trace。

与75只比较机制：tail仍正确削减物理pread；RAM-first去除了RAM上的副本touch。75和76任何速率/p99均不跨批补齐正向表格。
