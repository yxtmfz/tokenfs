# AURA-KV 崩溃一致性设计

当前 TokenFS FUSE 原型已经实现基础迁移状态和一致性检查。AURA-KV 研究层进一步要求本地副本不是永久文件，而是带状态和租约的缓存副本。

## 副本状态机

```text
RESERVED
  -> COPYING
  -> VERIFYING
  -> READY
  -> EXPIRED
  -> DELETING
```

失败时进入：

```text
FAILED
```

## 创建流程

```text
1. 预留本地容量和重复副本预算
2. 写入临时文件
3. 校验大小和 checksum
4. atomic rename
5. 数据库事务标记 READY
6. 失败时释放预算并清理临时文件
```

## 恢复场景

需要覆盖：

```text
COPYING 状态长时间未完成
临时文件存在但无数据库记录
数据库 READY 但物理文件不存在
租约过期但文件未删除
预算预留存在但提交未完成
```

当前已有脚本：

```text
scripts/fault_injection_test.sh
scripts/replica_lifecycle_test.sh
scripts/tokenfsctl.py check
```

后续应把这些恢复逻辑进一步接入 AURA-KV `Replica` 和 `DecisionLog`。

