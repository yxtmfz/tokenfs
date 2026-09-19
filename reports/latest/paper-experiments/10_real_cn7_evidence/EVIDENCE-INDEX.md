# 证据索引与复现

主结果：[实测报告](README.md)。[原始整批审计](formal-02/batch-audit.json)。仅 formal-02 进入性能结论，400次，种子201–210。

| 归档 | 内容 | 用法 |
|---|---|---|
| raw/cn7-final-evidence.tar.gz | formal-02原始manifest/trace/请求/动作/配置/结果；formal-01失效批次；pilot与correctness-01至06；fio基线；版本环境 | 仅formal-02用于正式速度，其他用于排错与正确性 |
| raw/cn8-validation-evidence-v2.tar.gz | matrix-01失败、matrix-02全72通过、safety-01/02、GetAttr正负控制、构建环境 | 独立正确性，不代表NVMe/TCP性能 |
| formal-02/ | 由原始数据重算的主表、配对检验、交互、资源与机制报告 | JSON保留未四舍五入值 |
| figures/ | 吞吐主图与消融区间；PNG/PDF/SVG | 图中均值/区间不替代配对检验 |
| signed-score-cn8-check.log | 归档后日志符号修复的C++回归 | 不属于正式测量版本 |

程序版本：67d219d2372bedf7a32e0ef882dafd555c5f92f2，统一Release。二进制、src/main.cpp、测量入口SHA256见manifest和build-and-storage-context.json；CMake flags含-O3 -DNDEBUG，回归目标另启用断言。最新分支含后续审计/文档/日志符号修复，不假装正式批次运行了这些后续提交。

归档不包含大数据文件本体、SQLite或二进制。对象生成器、种子和对象SHA256支持重建；完整原始请求/动作和结果保留。精确数据来源、NQN与设备身份在manifest；数据隔离不代表独占物理性能。

在仓库根目录执行以下命令（分析不需要服务器，绘图需要matplotlib）：

```bash
mkdir -p work/review-evidence
# 按实际归档位置替换目录
REPORT=reports/latest/paper-experiments/10_real_cn7_evidence
tar -xzf "$REPORT/raw/cn7-final-evidence.tar.gz" -C work/review-evidence
tar -xzf "$REPORT/raw/cn8-validation-evidence-v2.tar.gz" -C work/review-evidence
python3 scripts/evidence_audit.py work/review-evidence/formal-02
python3 scripts/evidence_report.py work/review-evidence/formal-02
python3 scripts/evidence_mechanisms.py work/review-evidence/formal-02
python3 scripts/evidence_figures.py work/review-evidence/formal-02 work/review-figures
python3 scripts/evidence_audit.py work/review-evidence/correctness-06
python3 scripts/evidence_audit.py work/review-evidence/matrix-02
```

其中 formal-01 具有 INVALIDATED.json，审计必须拒绝；不删除该标记来重用其中成功轮次。旧批次与正式数据不得合并。

全144组内容验证分别来自cn7 Release和cn8非Release固定版本，不能误称144组均为同一Release二进制。96并发读是同一逻辑域，SIGKILL发生于复制排空之后；不构成复制中断/断电/多GPU并发安全证明。

`SHA256SUMS`覆盖本目录中所有交付文件（不含其自身）。在本目录执行`shasum -a 256 -c SHA256SUMS`检查传输完整性。
