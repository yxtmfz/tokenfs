# 75：读取尾片与热点估值的因子诊断及负面模型证据

本批没有达到“四张最终表中每个比较项的吞吐和 p99 均改善”的目标。读取尾片复用确实减少了冗余 `pread`，在移动热点中改善了吞吐与 p99；公开轨迹的 p99 却回退。热点估值 H 的独立收益仍未稳定成立。全部实测、候选模型、反例和复算材料在本目录保留，没有用模型收益替代真实速率，也没有拼接不同版本的有利单元格。

这里的表格是 **尾片开关 × H 开关的 2×2 诊断**，不是 H/P/J/SIEVE 最终四表。本批没有执行 NoAffinity、NoJoint 或共享 SIEVE 服务器测速，不能据此宣布 P、J 或整体比较已重新验证。

## 冻结版本与环境

- 客户端 cn7，三个串行调用的逻辑 GPU/缓存域，共享同一块本地磁盘；远端为 cn13 的 NVMe/TCP 存储。没有物理 GPU、NVLink 或真实 LLM tokens/s 证据。
- 两个已经检查过的输入：`moving_shared-74801`、`public_toolagent-74802`；每臂 1152 次请求，每请求 2 MiB；磁盘缓存总额 24 MiB，保留捕获 RAM 为 4 MiB。
- 每输入两个反向顺序轮次，四臂，共 **16 次测速、18432 次请求**。另行执行四臂各 96 次内容检查，共 **384 次逐请求 SHA 校验**，不混入速度统计。
- H 使用原 retained 策略；四臂均 `disk_opportunity_value=false`，没有把报告74的失败候选悄悄替换进来。所有臂均使用 O_DIRECT、完整请求成本采样及相同缓存预算。
- 尾片复用只使用同一个打开句柄前次对齐读取已经获得的尾部字节，不增加预读；每个非 capture 句柄额外分配 4 KiB 尾缓存。本批该载荷峰值为 4096 字节，**在 4 MiB capture 之外单独计费**；峰值指标不含 C++ 对象元数据。
- 本批源码包 SHA256：`e4e55350628c185bca23aa4ed68953624ddd70aae8ec9969c3825f4aea849e32`。
- 运行二进制 SHA256：`b595240006f07bad4f727392a593c92be9888d904178f640651b240110829a4f`。

| 臂名 | H 热点估值 | 读取尾片复用 | 用途 |
|---|---|---|---|
| Full | 开 | 开 | 处理组 |
| NoTail | 开 | 关 | 在 H 开启时隔离公共读取路径优化 |
| NoHotspot | 静态估值消融 | 开 | 相同新读取路径上的 H 消融 |
| NoHotspotNoTail | 静态估值消融 | 关 | 相同旧读取路径上的 H 消融 |

源码冻结及每个臂的完整配置见 `data/provenance/freeze.json`、`data/development/*/*/config.json`。独立复核确认两个轮次按冻结的反向顺序执行，无相互重叠。

## 实测速率与结论

吞吐使用两轮总逻辑字节除以两轮完整前台墙钟时间；p99 使用两轮各自 nearest-rank 请求响应 p99 的中位数，**不是合并全部请求后的 p99**。两列百分比为正才表示改善。“双指标改善轮数”要求同一轮吞吐严格提高且 p99 严格下降。完整逐轮值见 `validation/results/pairs.json`，未四舍五入的聚合值见 `aggregates.json`。

|负载|比较|吞吐：处理/对照 MiB/s|吞吐变化|p99：处理/对照 ms|p99降低率|双指标改善轮数|
|---|---|---:|---:|---:|---:|---:|
|移动热点|Full / NoTail|344.894 / 337.506|+2.189%|27.003 / 27.777|+2.789%|2/2|
|移动热点|NoHotspot / NoHotspotNoTail|346.729 / 344.856|+0.543%|27.080 / 27.465|+1.402%|2/2|
|移动热点|Full / NoHotspot|344.894 / 346.729|−0.529%|27.003 / 27.080|+0.286%|0/2|
|移动热点|NoTail / NoHotspotNoTail|337.506 / 344.856|−2.131%|27.777 / 27.465|−1.136%|0/2|
|公开轨迹|Full / NoTail|86.897 / 86.443|+0.525%|29.763 / 28.528|−4.327%|0/2|
|公开轨迹|NoHotspot / NoHotspotNoTail|86.158 / 84.879|+1.507%|29.406 / 29.009|−1.370%|0/2|
|公开轨迹|Full / NoHotspot|86.897 / 86.158|+0.858%|29.763 / 29.406|−1.211%|1/2|
|公开轨迹|NoTail / NoHotspotNoTail|86.443 / 84.879|+1.842%|28.528 / 29.009|+1.658%|2/2|

16 个“负载×轮次×诊断比较”中只有 **7 个同时改善两项指标**。不能根据聚合均值把未通过的轮次计为通过；两个已知输入、两个轮次也不足以作统计显著性或独立泛化结论。

机制证据与限制：

- 开启尾片复用后，每轮移动热点物理 `pread` 从 1160 次降到 696 次；公开轨迹从 5750 次降到 3450 次，均减少 40%。这些包含基准程序的 EOF 读取调用。逻辑读取总字节、完整请求计数和逐请求内容检查均保持正确。
- 移动热点 Full 两轮合计 145 次复制，NoHotspot 合计 56 次；Full 仅少 12 次 2 MiB 远端读取，额外复制成本仍是 H 的主要缺口。少做对齐读取没有消除该策略差异。
- 移动热点 Full 每轮最慢的12个请求中，有11–12个是该输入中首次访问对应对象的请求。该事实提示后验迁移对这些请求的直接作用有限，但不构成 p99 不可改善的理论证明。
- 公开轨迹开启尾片后 p99 回退；Full 的两轮 daemon CPU 总时间为10.45秒，对照 NoTail 为9.27秒。身份校验等额外路径可能贡献开销，但没有函数级剖析，不能把全部回退归因于某一条调用。
- 公共读取优化必须同样供 Full、各消融与 SIEVE 使用才能进入最终四表；其收益不能直接算作 H、P 或 J 的独立创新收益。本次候选不构成“所有指标达标”的默认晋升依据。

## 本地模型：保留全部失败方向与适用边界

六个模型目录共 **1840 个模型臂，包含重复基线**；这是开发筛选量，不是1840次服务器测速，也不是独立确认样本。每个模型使用同一组已知10输入：四个移动热点种子、四个公开轨迹窗口/种子、一个固定热点和一个均匀随机输入。固定成本为远端21 ms、本地10.5 ms、复制8 ms，复制即时完成；没有真实队列、并发写入、CPU规划或物理GPU成本。任何 `cost_proxy` 或 `algebraic_*` 字段都只是这些常数的代数换算，不能当作真实吞吐或延迟。

|目录|模型臂数|机制与结果边界|
|---|---:|---|
|`models/disk-model`|400|非RAM访问的独立磁盘/逻辑时钟、噪声口径、持久返回间隔。持久磁盘时钟在 moving74801 仅从NoH的84/28改善到83/28，公开74802保留967/33对1002/25；其它种子仍反例明显。纯短窗口频率丢失公开长复用。|
|`models/feedback-model`|280|RAM命中时重新规划、真实磁盘/准入触发的竞争衰减、驻留租期估值。部分移动输入少1–2次远端读取，公开窗口无改善，仍有既有反例；模型不计真实RAM pin和异步开销。|
|`models/capacity-model`|320|固定12/18/24/48 MiB容量敏感性，retained及74两版本全部保留。74移动四种子18 MiB少29次远端且只多1次复制，24 MiB只少4次；公开轨迹反而在48 MiB更有利。不能说越紧越好，更不能把改容量结果冒充原24 MiB达标。|
|`models/outcome-model`|120|按已完成新人副本驻留的真实磁盘命中校准cohort先验。Beta反馈减少移动无用复制，但 moving74801退至84/28，与NoH相同；命中次数均值仍容许过多复制。公开轨迹保留原正负结果。末尾居民被右删失，且eviction闭合存在信息性删失，不能声称Beta是无偏总体成功率。|
|`models/ram-value-model`|240|将H估值扩展到固定4 MiB RAM的victim选择，新对象必须捕获、只在旧两个对象间淘汰。公开74802 RAM命中从2增加到Full30、NoH31，是共同缓存收益；移动74801略退，均匀随机绝对成本也可能退化。这是模块扩展，不是原H原样验证。真实pin保护未在串行模型中验证。|
|`models/calibration-model`|480|原headroom规则、首个CopySample后停止探索、完整读/复制校准后停止；预热和真正无样本冷启动全部对照。原规则每臂仅有12次headroom复制，额外H复制主要不在该分支。限制探索让74移动冷启动从84/28退为91/24或88/24；公开74802改copy门控主要帮助NoH（949/15），而Full为968/23，暴露初始布局依赖。|

表中诸如 `84/28` 均为“远端读取次数/复制次数”，不是速率。模型候选没有部署到服务器。NoH保持各机制设计规定的对照：H专属反馈/估值模型保持原static路径；RAM淘汰和校准门控作为公共机制时，对Full/NoH/NoP/NoJ同等应用，并同时报告各自对原公共机制的绝对变化，避免仅靠对照变差获得相对收益。

归档核对：六目录的211个源码/文本文件与工作目录逐字节一致，缺失、变化、额外文件均为0。只纳入 `.cpp/.h/.py/.json/.md/.txt`，不含模型可执行文件。各目录的历史 `manifest.json` 可能记载原工作目录中的可执行文件；这些属于构建记录，不能直接当成这个源码裁剪归档的完整文件列表。所有有 `inputs/` 的副本逐字节相同；feedback模型使用同一份 `disk-model/inputs`，也与报告74原输入相同。

## 审计范围与复现

`validation/results/review.json` 确认：332个冻结源码文件、20个运行二进制哈希凭据、16次测速、384次内容校验、全部SQL计数/指标、反向执行顺序、输入载荷哈希重建及源脚本报表复算均通过。原始证据未被复算修改。

运行二进制实体没有纳入此精简归档，故 `binary_file_verified=false`；已核验的是20份运行哈希凭据与冻结记录一致，不能表述为离线重建了同字节二进制。输入载荷按固定种子可重建；远端原归档包含保留载荷，其哈希见 `provenance/remote-archive.json`，本交付保留审计元数据与源码而不携带这些大载荷。远端构建日志记录12项原生测试、153项Python测试通过；构建阶段额外预检不计入正式384次独立内容检查。

从仓库根目录运行离线实测复核（不连接服务器、不重跑测速；输出放在临时目录）：

```sh
cd reports/latest/paper-experiments/75_read_path_diagnostic
review_dir=$(mktemp -d)
python3 validation/verify.py --evidence data --source provenance/source.tar.gz --output "$review_dir"
```

读取 `$review_dir/review.json` 应看到 `passed: true`；`factorial-tables.md`、`pairs.json` 和 `aggregates.json` 为重新计算的诊断表。

模型目录中的 `run.py` 等记录当时生成候选的方法，部分引用历史工作目录或当时仓库源码。**归档复现应直接编译已冻结的 `replay.cpp` 与同目录头文件**，不要在当前新版本源码上重新生成候选后声称复现旧结果。以下命令同样在本报告目录运行，仅需要C++17编译器和Python标准库，临时构建所有模型并逐行核对保存的输出：

```sh
python3 - <<'PY'
from pathlib import Path
import json, subprocess, tempfile
root = Path('models').resolve()
shared_inputs = root / 'disk-model' / 'inputs'
compiled = {}
checked = 0
with tempfile.TemporaryDirectory(prefix='tokenfs75-model-replay-') as tmp:
    for group in sorted(p for p in root.iterdir() if p.is_dir()):
        for result_file in sorted(group.glob('*results.json')):
            result = json.loads(result_file.read_text())
            for row in result['rows']:
                for variant, expected in row['variants'].items():
                    source = group / variant
                    identity = (group.name, variant)
                    if identity not in compiled:
                        exe = Path(tmp) / (group.name + '-' + variant)
                        subprocess.run(['c++', '-std=c++17', '-O2', '-I', str(source),
                                        str(source / 'replay.cpp'), '-o', str(exe)], check=True)
                        compiled[identity] = exe
                    inputs = group / 'inputs' if (group / 'inputs').is_dir() else shared_inputs
                    command = [str(compiled[identity]), str(inputs / (row['input'] + '.txt')), 'prior']
                    if group.name == 'capacity-model':
                        command.append(str(row['capacity_objects_per_domain']))
                    actual = subprocess.run(command, capture_output=True, text=True, check=True).stdout
                    assert actual == expected['stdout'], (group.name, row['input'], variant)
                    checked += len(expected['arms'])
assert checked == 1840, checked
print('All 1840 model arms exactly reproduced; these are not server speed measurements.')
PY
```

上述归档重放命令已实际执行：1840个模型臂的输出与保存结果逐字节一致。构建使用临时目录，没有改写原始结果。

模型的额外边界测试见各目录的 `verify.cpp`、`verify-persistent.cpp` 与 `verification.json`。例如校准门控测试可在临时位置单独编译运行：

```sh
model_test=$(mktemp -d)
c++ -std=c++17 -O2 -I models/calibration-model/retained_copy_calibrated_cold models/calibration-model/verify.cpp -o "$model_test/verify"
"$model_test/verify" copy_calibrated
```

本档案支持继续定位问题和收紧论文主张，不支持“热点、亲和、联合、整体四项已全部双指标改善”或“可用这些模型替代未通过的真实消融”。报告70与74的历史证据继续独立保留。
