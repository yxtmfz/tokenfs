# cn7 正式批次预先固定方案

本方案在 formal-01 首次运行前固定。开发数据为 pilot-01（种子 7、11、17）；不进入正式区间/检验。正确性批次单独保存，不作为速度证据。

- 客户端 cn7，目标 cn13，独立 remote-cn7 namespace；不使用 cn14。
- 二进制与主测量入口：正式 manifest 中记录 SHA256；全批次不改算法、不改参数。
- 入口：`evidence_benchmark.py --profile paper --scenarios stable scan mixed shared_shift uniform sequential --seeds 101 102 103 104 105 106 107 108 109 110 --requests 96 --shard-mib 4 --quota-mib 8 --backend-direct`。
- 每场景每种子一个配对块，块内策略顺序随机；40 个策略×场景组合，每组10个独立块，共400次。合成 trace、单请求流、三个逻辑缓存域。
- 各域配额8 MiB；普通对象4 MiB；mixed 的大对象16 MiB，超过单域配额，因此该场景也检验大对象绕过，不应单独解释为大小感知淘汰的纯效应。
- 组件和场景选择以入口 PAPER_MATRIX 为准：稳定/扫描/变长/热点迁移/均匀随机/顺序预取。四格协同在 scan 和 shared_shift。
- 主结果：完整任务 `job_wall_s`、有效 MiB/s；后台 drain、含 drain 时间、p95/p99、源字节、复制/淘汰计数作为附属证据。
- 主比较 AURA-core 对 LRU-equal、LFU-equal 跨五场景共10项为一个 Holm 家族。其余每个组件跨所选场景分别一个家族；RemoteOnly 自成跨场景家族。家族内控制 alpha=.05，不声称论文级错误率控制。
- 配对 log 时间比作双侧符号翻转检验（零假设下配对差对称），块 bootstrap 95%区间。显著提速要求 Holm p<.05 且区间上界<1；退化同样报告。区间未经多重校正。
- n=10 是固定资源预算下的确认批次，并非经功效分析保证检测任意小差异。不能因接近显著追加种子；不确定即未得到支持。
- 交互项 T11−T10−T01+T00 的区间仅为探索性证据，不能称完整统一模型的协同已证实。
- 不按输赢排除轮次。短读、字节不符、后台错误、校验失败、容量超配均保留失败记录并终止该批；修复后全新批次，不拼接版本。
- 未实际淘汰时不评价淘汰贡献；配置开关有效不等于机制产生不同决策。组件未产生动作差异必须披露。
- 保留全部负结果。吞吐没有提升，不能以命中率提高替代性能结论。

环境边界：客户端双层前台 O_DIRECT；目标 loop/backing 缓存未受控；本地和远端不是独占物理 NVMe。背景资源争用、单客户端和合成 trace 限制外推。formal-01 只检验 C++ AURA-core，不代表 Python RobustBenefit、需求置信区间、真实 GPU 或推理 TTFT。
