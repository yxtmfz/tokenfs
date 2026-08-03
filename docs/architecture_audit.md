# 当前仓库架构审计

## 已有可复用模块

```text
src/main.cpp
  FUSE 主程序
  SQLite 元数据
  本地/远端目录后端
  本地优先、远端溢写
  代价驱动淘汰
  GPU 访问统计
  本地缓存副本
  QoS 工程观测

scripts/
  启停脚本
  NVMe-oF 连接脚本
  功能测试
  策略测试
  性能报告

config/tokenfs.dev.yaml
  当前开发配置
```

## 主要缺口

```text
缺少独立研究策略模块
缺少 trace-driven simulator
缺少 15 个 baseline/策略
缺少替代来源解析器
缺少共享拓扑分类器
缺少资源影子价格
缺少论文实验输出统一入口
```

## 本次最小侵入实施

新增：

```text
aura_kv/
scripts/aura_kv_sim.py
scripts/aura_kv_test.sh
tests/aura_kv_unit_test.py
config/aura_kv.example.yaml
docs/aura_kv_*.md
```

不改动 FUSE 主路径，避免破坏已经可运行的 TokenFS。

