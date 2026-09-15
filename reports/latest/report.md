# AURA-KV 最新报告入口

本文件不再单独维护历史双 VM 性能基线，避免和当前真实实验结果混在一起。

当前最新、最完整的中文总报告请看：

```text
reports/latest/final-report.md
```

当前论文实验主目录请看：

```text
reports/latest/paper-experiments/09_real_cn14_nvmeof/
```

该目录对应的真实环境是：

```text
cn14 单客户端
  ├── 模拟 gpu0/gpu1/gpu2 多逻辑 GPU 本地缓存
  ├── 运行 TokenFS / AURA 策略
  └── /srv/tokenfs/remote0
          ↑
          └── cn13:4420 Linux NVMe/TCP Target
```

请优先引用：

```text
reports/latest/paper-experiments/09_real_cn14_nvmeof/01_environment_gap/storage_gap_summary.csv
reports/latest/paper-experiments/09_real_cn14_nvmeof/02_single_run_speed/real_speed_summary.csv
reports/latest/paper-experiments/09_real_cn14_nvmeof/03_repeat_speed/repeat_summary.csv
```
