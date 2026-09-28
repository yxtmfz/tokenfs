# 两组原失败种子时序重放：数据可复算，原报告器失败保留

固定种子3241，AdaptiveHP和PoolSIEVE1各一次，使用上一轮已校验二进制
7b724487dc5e4454f98d5d2598b12a9aa51b76491a269d18614f2639f3210ba9。
仅增加请求时序记录；源码冻结提交de7e0bc。没有物理GPU、策略改动或种子替换。

|策略|诊断吞吐 MiB/s|远端打开次数|同对象复制重叠的远端请求|Open结束时复制已启动且未结束|执行前copy_cost拒绝|
|---|---:|---:|---:|---:|---:|
|AdaptiveHP|131.45|98|49|1|0|
|PoolSIEVE1|129.53|108|54|52|0|

没有复现报告25同一种子的25次拒绝和明显降速。调度/时序依赖仍存在，不能宣称已经修复了原失败。重叠支持研究“完整捕获已有但READY尚未完成”期间的请求共享，不能直接推算等待或共享的因果提速。这里的诊断速率不替代无探针性能实验。

## 原报告生成失败及修复

两组run_case完成，原批次审计通过；但analyze_case使用mode=ro&immutable=1
读取仍可能存在已提交WAL的SQLite，报告阶段访问计数断言失败，driver exit为1。
原退出码和完整日志保留在raw归档内，不改为0，也不重跑这两组。

进程结束并归档后，离线数据库每组576次访问与请求逐项匹配，全部1152次请求、
分层字节、完整时序和最终指标的独立复核通过。修复版本改用只读mode=ro，并显式关闭
benchmark的SQLite连接；新增持有已提交WAL的测试，证明旧immutable读漏记录、新读法正确。
该修复不修改原始记录、不关闭WAL、不放松持久化。

复现：将source.tar.gz/cn7-evidence.tar.gz解压为work/readiness-diagnostic-source
和work/readiness-diagnostic-data，把validation/review-readiness-diagnostic.py放到work运行。
诊断使用原冻结代码离线重放也通过，说明不能将原运行时的审计异常当作数据损坏。
