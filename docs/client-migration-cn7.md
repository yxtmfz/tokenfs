# cn7 客户端迁移记录

> 本页下文是 2026-09-18 的部署快照。2026-09-19 评估在隔离目录 `/home/wjxt/projects/tokenfs-eval-20260919` 进行，使用 `build-release/tokenfs`、每次独立输出/缓存/SQLite；cn8 也已部署用户目录工具并运行正确性验证。当前方案见 [evidence-experiments.md](evidence-experiments.md)。原项目和 cn14 均未作为本轮执行目录。

日期：2026-09-18。用户因 cn14 将被他人占用，要求改用 cn7/cn8。已将主客户端迁至 cn7；cn8 已确认可登录及访问 cn13:4420，作为备用，未部署完整环境。未运行性能或消融实验。

## 当前拓扑

cn7（28.10.10.7，wjxt，SSH 22）运行 TokenFS，模拟 gpu0/gpu1/gpu2。cn13（28.10.10.13:4420）继续提供真实 NVMe/TCP 容量层。管理连接为公网跳板 121.46.19.2:20866 → 内网跳板 172.16.29.120:5566 → cn7；数据面直连 cn13，不经过 SSH 隧道。

cn14 仍挂载旧 ext4 namespace，不能让 cn7 同时读写挂载那块旧盘。因此为 cn7 建立了独立 64 GiB namespace，旧环境未改动。

| 项目 | 当前值 |
|---|---|
| cn7 项目 | /home/wjxt/projects/tokenfs |
| 部署代码 | 8481695a5cfdc46baaba4919ac8964a4b298c471；源码快照，无 .git；DEPLOYED_COMMIT 记录版本 |
| 实际配置 | /home/wjxt/projects/tokenfs/config/tokenfs.cn7.yaml |
| 本地缓存 | /home/wjxt/aura-kv-cn7/local/gpu0、gpu1、gpu2 |
| 基础配额 | 每个逻辑 GPU 1024 MiB；未来实验覆盖配额需另行记录 |
| SQLite | /home/wjxt/aura-kv-cn7/metadata/tokenfs.db |
| FUSE 挂载点 | /home/wjxt/aura-kv-cn7/mnt/tokenfs |
| 远端挂载点 | /srv/tokenfs/remote-cn7 |
| 当前远端设备 | /dev/nvme1n1；设备名重启后可能改变 |
| NQN | nqn.2026-09.local.aura-kv:remote-cn7 |
| Host NQN | nqn.2026-09.local.aura-kv:host-cn7 |
| Host ID | 使用 UUIDv5(DNS namespace, aura-kv-cn7-migration-2026-09-18)，连接时显式指定，不更改主机全局身份 |
| ext4 UUID | dfa976ba-7037-432e-93bd-1632a1f9bfeb |
| cn13 backing file | /home/wjxt/aura-kv-nvmeof-cn7/remote-cn7.img |
| cn13 loop 设备 | /dev/loop1，64 GiB；旧环境继续使用 /dev/loop0 |
| 新远端可用容量 | 约 60 GiB |

## 磁盘与物理环境边界

- cn7 的 /dev/nvme0n1 是 4K 逻辑/物理扇区，已有 Ceph/XFS 分区，未修改、格式化或挂载它。
- 新导出的远端设备为 512B 逻辑/物理扇区，ext4 block size 为 4096B。这两个数不是同一概念。
- cn7 的逻辑 GPU 本地缓存位于 /home 的现有 LVM 文件系统，底层为 sda；不能标注成直接使用本机 NVMe 裸盘。
- cn13 新 backing file 同样位于 /home 的现有文件系统，后端是 loop 文件，并非直接导出物理 NVMe。真实的是服务器分离与 NVMe/TCP 数据链路。
- cn7 有 80 个在线逻辑 CPU、约 251 GiB 内存；后续需要明确页缓存控制，不能因工作集远小于内存而忽略缓存影响。

## 软件与安装方式

cn7、cn8 的 apt 自动更新占用安装锁，且 cn7 无法解析外部 Ubuntu 源域名。没有终止系统更新或修改 DNS、sudoers；仅停止了本次自行启动后卡住的 apt download。

通过本机从 Ubuntu 官方 HTTPS 软件源下载 34 个依赖包，并按 cn7 apt 元数据逐个核验 SHA512，上传后仅解包至 /home/wjxt/aura-kv-tools/root，不执行系统 dpkg 安装。

使用前需要加载：

```bash
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs
export TOKENFS_CONFIG="$PWD/config/tokenfs.cn7.yaml"
```

工具包括 CMake 3.28.3、Ninja 1.11.1、NVMe CLI 2.8/libnvme 1.8、fio 3.36、FUSE3 3.14.0、SQLite 3.45.1、yaml-cpp 0.8.0。env.sh 设置用户目录 PATH、库搜索路径及 pkg-config/CMake 前缀；实际包校验表在 /home/wjxt/aura-kv-tools/package-sha256.txt。

sudo 使用密码验证，未增设通用免密权限。原实验脚本依赖 sudo -n 清页缓存的缺陷仍需在实验设计阶段处理；此轮没有清理全机页缓存。

## 已完成验证

- cn7/cn8 登录及 cn13:4420 TCP 可达。
- cn7 NVMe 控制器真实 transport=tcp，traddr=28.10.10.13、src_addr=28.10.10.7，NQN 与新 namespace 一致。
- 新盘挂载前核对唯一 UUID 和 ext4 类型；未格式化客户端任何已有盘。
- C++ 编译链接通过，动态依赖可解析。
- 32 个 Python 单元测试通过。
- check_environment.sh：ok=19、warn=0、fail=0。
- FUSE 短暂启动、列出 gpu0/gpu1/gpu2 后立即卸载并停止；没有执行读写 workload、fio 或消融实验。
- 当前 TokenFS 处于停止状态，新 NVMe/TCP/ext4 存储挂载保留。

## 后续注意

1. 当前是运行时 NVMe Target/连接/挂载，未配置开机自动恢复或修改 fstab。重启后需恢复 namespace、以相同 Host NQN/Host ID 重连，并按 UUID 核对设备；不要重复格式化。
2. 初次自定义 Host NQN 连接失败的根因为与默认 Host ID 已有映射冲突。为本连接指定独立 Host ID 后成功，与扇区大小无关。
3. cn7 系统 UTC 时间与本机观察相差约半小时；未擅自调整时间。未来实验记录需检查时钟同步，耗时使用单调时钟。
4. 原 cn14 实验报告保持历史含义，不能改名当作 cn7 新结果。迁移改变了客户端与 backing file，新实验必须重新记录环境和基线。
5. 先讨论并修复计时、缓存控制、强基线能力、快路径统计与实际淘汰触发，再开始性能实验。
