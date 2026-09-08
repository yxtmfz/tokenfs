# 真实 TokenFS Workload 速度实验

本目录只保留真实 NVMe-oF 挂载目录上的端到端速度结果。

旧的 `/var/lib/tokenfs/remote-sim` 开发样例已经移除，避免与论文实验混淆。重新生成结果前，必须先把远端后端挂载为 NVMe-oF：

```bash
cp config/tokenfs.nvmeof.example.yaml config/tokenfs.nvmeof.yaml
# 编辑 config/tokenfs.nvmeof.yaml，填入真实 target_ip、subnqn、device
sudo ./scripts/connect_nvme.sh --config config/tokenfs.nvmeof.yaml --backend remote0 --chown-current
TOKENFS_CONFIG=config/tokenfs.nvmeof.yaml ./scripts/real_speed_benchmark.sh
```

脚本默认会检查：

- `backends[].type` 是否为 `nvmeof`；
- 远端 `root` 是否为已挂载目录；
- 挂载源是否为 `/dev/nvme...`；
- 配置中的 `nvme_device` 是否与实际挂载源一致。

通过后会生成：

```text
real_speed_report.md
real_speed_summary.csv
figures/
nvmeof_mount_evidence.txt
```
