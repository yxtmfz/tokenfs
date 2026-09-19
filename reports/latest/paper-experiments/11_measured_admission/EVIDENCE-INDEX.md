# 实测成本策略：证据索引与复现

主报告：[完整结果](README.md)。算法是显式启用的 AURA-adaptive（measured_policy），旧 AURA-core 默认行为保留。

| 位置 | 内容 | 解释范围 |
|---|---|---|
| raw/cn7-measured-final-evidence.tar.gz | cn7 全部 measured 系列原始 trace、输入、配置、请求、事件、结果、退出状态、冻结上下文 | 主确认、补充、开发、正确性分开标记 |
| raw/measured-cn8-correctness-evidence.tar.gz | B1 55 项内容验证 | 不作速度证据 |
| raw/measured-b2-cn8-correctness-evidence.tar.gz | B2 65 项内容验证 | 不能发现 B2 热度重置活性漏洞 |
| raw/measured-b3-cn8-validation-evidence.tar.gz | B3 65 项内容验证、B2 26 项与 B3 39 项逻辑域内容验证 | 不作物理多 GPU 或并发性能证据 |
| measured-confirm-02/ | 648 次主实验的全比较、资源/机制、交互、图表 | 每场景 12 对；主比较 21 项 Holm 家族 |
| measured-supplement-02/ | 96 次容量、长持续、窗口、到达时间补充 | 每条件 3 对，仅描述性 |
| measured-domain-supplement-01/ | 12 次逻辑域速度补充 | 相同共享架构；每场景 3 对，仅描述性 |
| development/ | 六个开发批次的完整汇总与负结果 | 不并入确认性检验 |
| validation/ | 内容审计与 B2/B3 重置饥饿正负控制 | 人工成本仅用于单元反例，不是实测速度 |
| provenance/ | 源码包、公开来源 hash、实际构建、执行冻结与结束检查 | 后续分析提交不能冒充已测版本 |

B1/B2/B3 与旧 formal-02 均保留，不择优混合。B2 的确认在任何保留集性能请求执行前撤回；冻结文件、取消记录与单元反例均可检查。B3 的测量源码 c3270ece4922818c24f32164804100cea60e050a，逻辑域运行器 502de607435f66e38842c6c87e1a88638ce74913。完整参数/窗口/统计方案在仓库 study-configs/measured-b3-freeze.json 与 docs/measured-confirmation-plan.md，实际执行前核对了源文件与二进制散列。

源码包保存实际部署的增量文件，依赖对应 Git 提交；不是完整独立发行包。归档不含 payload 本体、数据库、二进制、SSH 配置或凭据。合成 payload 可按版本、种子及 SHA256 重建。公开源 trace 全文不重新分发；按 provenance/public-traces.json 中固定 URL 下载并校验散列。归档保留所选窗口的转换事件以核对实际执行序列。

## 离线复算

需要 Python 3.10+，绘图另需 matplotlib；无需连接服务器。以下在仓库根目录执行：

```bash
REPORT=reports/latest/paper-experiments/11_measured_admission
mkdir -p work/review-measured/cn8
# cn7 归档自带 cn7/ 前缀；cn8 归档没有主机前缀。
tar -xzf "$REPORT/raw/cn7-measured-final-evidence.tar.gz" -C work/review-measured
tar -xzf "$REPORT/raw/measured-cn8-correctness-evidence.tar.gz" -C work/review-measured/cn8
tar -xzf "$REPORT/raw/measured-b2-cn8-correctness-evidence.tar.gz" -C work/review-measured/cn8
tar -xzf "$REPORT/raw/measured-b3-cn8-validation-evidence.tar.gz" -C work/review-measured/cn8
python3 scripts/measured_study.py audit --output work/review-measured/cn7/measured-correctness-03
python3 scripts/measured_study.py audit --output work/review-measured/cn8/measured-correctness-03
python3 scripts/measured_multidomain_check.py --audit --output work/review-measured/cn8/measured-multidomain-02
python3 scripts/measured_artifacts.py work/review-measured/cn7/measured-confirm-02 --figures
python3 scripts/measured_artifacts.py work/review-measured/cn7/measured-supplement-02 --figures
python3 scripts/measured_domain_study.py report --output work/review-measured/cn7/measured-domain-supplement-01
# 下载固定 Mooncake 源文件至 /path/to/public-traces 后，额外交叉核对冻结窗口：
python3 scripts/measured_freeze_audit.py --evidence-root work/review-measured/cn7 --trace-dir /path/to/public-traces
```

统计 helper 在运行前同样冻结；JSON 保留未四舍五入数值。服务器原始统计与本地复算逐字段比较：非浮点字段完全一致，浮点绝对/相对误差容限均为 1e-12，任何非零误差均在 validation/offline-statistics-reproduction.json 中逐项记录；不能将超过该容限的差异当作舍入误差。机制事件与吞吐是不同证据，不以模型分数代替速度。全部主比较必须一起读取；确认后不得再以这些数据调参而继续称其为未知测试集。

结束时 cn7 日历时钟未同步且与本地相差约 1935 秒，原始时间戳不改写；跨主机日志不能直接按日历时间对齐。吞吐使用 cn7 单机 CLOCK_MONOTONIC 差值，C++ 成本使用 steady_clock。只读检查记录在 provenance/clock-offset-check.json。

`SHA256SUMS` 覆盖此报告目录交付内容（不含其自身）。进入本目录执行 `shasum -a 256 -c SHA256SUMS` 可检查完整性。真实硬件、时间边界、缓存及逻辑域限制详见主报告。
