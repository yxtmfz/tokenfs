# 76：公共读取路径开发批次——未通过，含 SIEVE 语义公平性缺陷

**本批不构成最终论文证据。** 数据完整性审计通过，但16个主比较轮次中只有5个同时提高吞吐并降低p99；更重要的是，RAM-first 路由改变了共享 SIEVE 的 `visited` 更新语义，整体比较存在公平性缺陷。原始数据和失败结果完整保留，用于诊断及后续修复对照，不与其他批次拼接“通过”单元格。

## 实验、实现及已知缺陷

- cn7 客户端上的三个逻辑 GPU/缓存域，共用本地磁盘；cn13 为 NVMe/TCP 远端存储。调用串行，没有物理GPU共享、NVLink或真实LLM推理速度主张。
- 固定两个已检查输入：`moving_shared-74801`、`public_toolagent-74802`。每臂1152次请求、每请求2 MiB；磁盘缓存共24 MiB、保留捕获RAM共4 MiB。
- 六臂 × 两输入 × 两个反向执行顺序轮次，共 **24次测速、27648次请求**。另有六臂各96次独立内容检查，共 **576次SHA校验**，与测速分开。
- 六臂为 `Full`、`NoHotspot`、`NoAffinity`、`NoJoint`、`PoolSIEVE1`、`NoRAMFirst`。前三个消融分别仅关闭对应H/P/J策略机制；SIEVE为整体对照；NoRAMFirst是单独的公共路径诊断，不是第四项策略创新。
- 所有臂启用读取尾片复用 `reuse_direct_read_tail=true`；除NoRAMFirst外全部启用 `ram_first_routing=true`；所有臂的 `disk_opportunity_value=false`，使用原retained H。所有臂采用相同O_DIRECT、完整请求成本采样及容量预算。
- 尾片缓冲每个非capture打开句柄额外占4 KiB载荷。本批峰值为4096字节，在4 MiB保留捕获RAM之外单列；指标不含C++对象元数据。

**为什么审计通过仍不能称为公平的整体证据：** 76的RAM-first命中会提前把 `meta.tier` 设为 `inflight`，并跳过普通磁盘副本路由；后面的 `sieve_.Hit(...)` 仅在 `meta.tier == "local"` 时触发。因此，原本会给SIEVE设置visited的逻辑访问，在RAM提前命中后不再设置visited。虽然公共开关对所有主臂相同，这仍然改变了SIEVE替换策略看到的访问历史；“相同开关”不等于“策略语义保持不变”。本批只有Full的NoRAMFirst诊断，没有SIEVE的对应开关对照，不能从中量化或排除该偏差。

这一缺陷由后续77修复工作单独处理；77的修复与新实验不回写76的原始记录。本档案不宣称77已经通过，也不把76结果解释为修复后的SIEVE比较。数据内容正确、算术可复核，与研究设计公平是不同层面的要求。

## 实测结果及未达标项

以下仅概览本批原始四类比较；完整四表在 `validation/results/four-tables.md`，未四舍五入的逐轮及聚合值在 `pairs.json`、`aggregates.json`。这份生成表保留了历史名称，**不表示最终验收通过，SIEVE行尤其受上述语义缺陷限制**。

吞吐为两轮总逻辑字节/总前台墙钟时间，单位MiB/s；p99为两轮各自nearest-rank请求响应p99的中位数，单位ms，不是合并请求的p99。百分比为正表示改善。

|负载|对照|Full/对照吞吐|吞吐变化|Full/对照p99|p99降低率|同轮双指标改善|
|---|---|---:|---:|---:|---:|---:|
|移动热点|NoHotspot|351.549 / 353.423|−0.530%|27.010 / 26.767|−0.910%|0/2|
|公开轨迹|NoHotspot|86.691 / 86.502|+0.218%|29.677 / 29.034|−2.213%|0/2|
|移动热点|NoAffinity|351.549 / 333.846|+5.303%|27.010 / 27.058|+0.176%|1/2|
|公开轨迹|NoAffinity|86.691 / 85.808|+1.029%|29.677 / 29.534|−0.485%|0/2|
|移动热点|NoJoint|351.549 / 308.605|+13.915%|27.010 / 27.034|+0.086%|1/2|
|公开轨迹|NoJoint|86.691 / 85.199|+1.751%|29.677 / 29.486|−0.646%|0/2|
|移动热点|PoolSIEVE1（语义缺陷）|351.549 / 331.248|+6.129%|27.010 / 26.485|−1.984%|1/2|
|公开轨迹|PoolSIEVE1（语义缺陷）|86.691 / 74.728|+16.009%|29.677 / 32.704|+9.257%|2/2|

即使暂不考虑SIEVE语义缺陷，原始方向计数也仅 **5/16**；H为0/4、P为1/4、J为1/4、整体对照为3/4。这个计数是描述性算术结果，不是研究有效性认证。两轮已知输入也不能支持统计显著性或独立泛化结论。

单独的Full/NoRAMFirst公共路径诊断只有1/4轮次同时改善：移动热点聚合吞吐−0.283%、p99降低−0.686%；公开轨迹聚合吞吐+0.044%、p99降低−1.012%。因此，本批同样没有证明RAM-first让全局吞吐与尾延迟稳定改善。完整数据见 `validation/results/ram-first-diagnostic.md`。

不比较76与75、74的跨批绝对速度来推导因果提升；环境负载、执行时刻及策略状态差异可能影响结果。不能通过保留某批的吞吐、另一批的p99或单独的有利轮次构造最终表。

## 冻结与档案清单

|对象|SHA256|
|---|---|
|冻结源码 `provenance/source.tar.gz`|`eae13270658c478eb436ce027361f5aca04972fe0401886bcfc5fb44574e9c66`|
|原始元数据归档 `provenance/evidence.tar.gz`|`aad8685fb86ea5742477afc8ce3cd5a618780800a75a5d16af2e8ab38e093feb`|
|运行二进制凭据|`d2d078e1c3747f4ebaa72bd7c6bea8ab8a4b035c3ea36a8764d79966ea198758`|

- `data/`：完整290个原始元数据文件，逐字节复制，无重新写表或更改数据库；包括逐请求时序、配置、事件、SQLite、执行哈希及退出状态。
- `provenance/source-hashes.json` 和 `data/provenance/freeze.json`：336个冻结源码文件的哈希与运行冻结记录。
- `provenance/archive-hashes.json`：源码/原始归档大小和哈希；`provenance/data-hashes.json`：290个原始文件逐文件哈希。
- `provenance/evidence.tar.gz`：与 `data/` 内容完全相同的290个元数据文件；不含运行二进制实体或保留载荷。
- `validation/verify76.py`：可移植离线复核器；`validation/results/`：本批原审计结果、逐轮比较、四表及机制记录。
- `provenance/build.log`、`data/provenance/native-tests.log`、Python/standalone日志：12项原生测试与154项Python测试通过。构建阶段额外预检不计入正式576次独立内容检查。

离线审计的 `passed: true` 表示：336个源码哈希、30份运行二进制哈希凭据、24次测速/6次内容检查、源报表重算、输入载荷哈希重建、SQLite指标及访问计数、反向执行顺序、原始证据未改动等检查通过。`binary_file_verified=false`，因为本归档没有二进制实体；不把哈希凭据一致表述为已离线重建同字节二进制。上述审计不包含SIEVE语义等价证明，所以不会自动拒绝该实验设计缺陷。

## 可移植复核

在仓库根目录进入本报告目录。先核对压缩包、原始文件及归档中的元数据完全一致；只读取文件，不修改 `data/`：

```sh
cd reports/latest/paper-experiments/76_common_readpath_development
python3 - <<'PY'
from pathlib import Path
import hashlib, json, tarfile
sha = lambda data: hashlib.sha256(data).hexdigest()
archives = json.loads(Path('provenance/archive-hashes.json').read_text())['archives']
for name, receipt in archives.items():
    blob = (Path('provenance') / name).read_bytes()
    assert len(blob) == receipt['bytes'] and sha(blob) == receipt['sha256'], name
expected = json.loads(Path('provenance/data-hashes.json').read_text())
actual = {str(p.relative_to('data')): sha(p.read_bytes())
          for p in Path('data').rglob('*') if p.is_file()}
assert actual == expected and len(actual) == 290
with tarfile.open('provenance/evidence.tar.gz') as archive:
    stored = {m.name: sha(archive.extractfile(m).read())
              for m in archive.getmembers() if m.isfile()}
assert stored == expected
print('Archive SHA256 and all 290 raw files agree.')
PY
```

再复算速度、p99、内容校验和源脚本报表。输出必须放在原始证据目录之外；以下只进行离线读取和临时复制，不连接服务器、不再测速：

```sh
review_dir=$(mktemp -d)
python3 validation/verify76.py --evidence data --source provenance/source.tar.gz --output "$review_dir"
```

`$review_dir/review.json` 应显示 `passed: true`、`strict_both_improved_primary: 5`、`strict_both_improved_ram_first: 1`。这些是本次失败开发批次的可复核记录，不是全部指标通过的最终结果。
