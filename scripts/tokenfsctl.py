#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


MIB = 1024 * 1024


@dataclass
class GpuConfig:
    gpu_id: int
    logical_root: str
    local_root: Path
    local_quota_bytes: int
    remote_backend: str


@dataclass
class BackendConfig:
    backend_id: str
    backend_type: str
    root: Path
    nvme_transport: str = "tcp"
    nvme_target_ip: str = ""
    nvme_port: str = "4420"
    nvme_subnqn: str = ""
    nvme_device: str = ""
    nvme_mount: str = ""
    nvme_filesystem: str = "ext4"


@dataclass
class TokenfsConfig:
    mount_point: Path
    metadata_db: Path
    gpus: list[GpuConfig]
    backends: dict[str, BackendConfig]


def strip_value(value: str) -> str:
    return value.strip().strip('"').strip("'")


def bytes_to_mib(value: int) -> str:
    return f"{value / MIB:.2f} MiB"


def directory_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            path = Path(dirpath) / name
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total


def is_mounted(path: Path) -> bool:
    mounts = Path("/proc/mounts")
    if not mounts.exists():
        return False
    target = str(path)
    try:
        with mounts.open("r", encoding="utf-8") as f:
            return any(line.split()[1] == target for line in f if line.split())
    except OSError:
        return False


def parse_config(path: Path) -> TokenfsConfig:
    mount_point = Path("/mnt/tokenfs")
    metadata_db = Path("/var/lib/tokenfs/metadata/tokenfs.db")
    gpus: list[GpuConfig] = []
    backends: dict[str, BackendConfig] = {}

    section = ""
    current: dict[str, str] | None = None
    current_kind = ""

    def flush_current() -> None:
        nonlocal current, current_kind
        if not current:
            return
        if current_kind == "gpus":
            quota = 0
            if "local_quota_mib" in current:
                quota = int(current["local_quota_mib"]) * MIB
            elif "local_quota_gib" in current:
                quota = int(current["local_quota_gib"]) * 1024 * MIB
            gpus.append(
                GpuConfig(
                    gpu_id=int(current["gpu_id"]),
                    logical_root=current["logical_root"],
                    local_root=Path(current["local_root"]),
                    local_quota_bytes=quota,
                    remote_backend=current["remote_backend"],
                )
            )
        elif current_kind == "backends":
            backend = BackendConfig(
                backend_id=current["id"],
                backend_type=current.get("type", "directory"),
                root=Path(current["root"]),
                nvme_transport=current.get("nvme_transport", "tcp"),
                nvme_target_ip=current.get("nvme_target_ip", ""),
                nvme_port=current.get("nvme_port", "4420"),
                nvme_subnqn=current.get("nvme_subnqn", ""),
                nvme_device=current.get("nvme_device", ""),
                nvme_mount=current.get("nvme_mount", current.get("root", "")),
                nvme_filesystem=current.get("nvme_filesystem", "ext4"),
            )
            backends[backend.backend_id] = backend
        current = None
        current_kind = ""

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if not line.startswith(" ") and line.endswith(":"):
                flush_current()
                section = line[:-1]
                continue
            stripped = line.strip()
            if stripped.startswith("- "):
                flush_current()
                current_kind = section
                current = {}
                stripped = stripped[2:].strip()
                if ":" not in stripped:
                    continue
            if ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = strip_value(value)
            if current is not None and section in {"gpus", "backends"}:
                current[key] = value
            elif section == "filesystem":
                if key == "mount_point":
                    mount_point = Path(value)
                elif key == "metadata_db":
                    metadata_db = Path(value)
    flush_current()
    return TokenfsConfig(mount_point, metadata_db, gpus, backends)


def db_rows(db_path: Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


def db_has_column(db_path: Path, table: str, column: str) -> bool:
    if not db_path.exists():
        return False
    conn = sqlite3.connect(db_path)
    try:
        return any(row[1] == column for row in conn.execute(f"pragma table_info({table})"))
    finally:
        conn.close()


def print_status(config: TokenfsConfig, config_path: Path) -> None:
    print("TokenFS 状态")
    print("=" * 60)
    print(f"配置文件: {config_path}")
    print(f"挂载点:   {config.mount_point} ({'已挂载' if is_mounted(config.mount_point) else '未挂载'})")
    print(f"元数据库: {config.metadata_db} ({'存在' if config.metadata_db.exists() else '不存在'})")
    print()

    total = db_rows(config.metadata_db, "select count(*) as n from files")
    committed = db_rows(
        config.metadata_db,
        "select count(*) as n from files where state='COMMITTED'",
    )
    incomplete = db_rows(
        config.metadata_db,
        "select count(*) as n from files where state!='COMMITTED'",
    )
    print("元数据概览")
    print(f"- 文件记录: {total[0]['n'] if total else 0}")
    print(f"- 已提交:   {committed[0]['n'] if committed else 0}")
    print(f"- 未完成:   {incomplete[0]['n'] if incomplete else 0}")
    print()

    print("GPU 存储配额")
    for gpu in config.gpus:
        local_used = directory_bytes(gpu.local_root)
        percent = (local_used / gpu.local_quota_bytes * 100) if gpu.local_quota_bytes else 0
        local_rows = db_rows(
            config.metadata_db,
            "select count(*) as n, coalesce(sum(size_bytes),0) as bytes "
            "from files where gpu_id=? and tier='local'",
            (gpu.gpu_id,),
        )
        remote_rows = db_rows(
            config.metadata_db,
            "select count(*) as n, coalesce(sum(size_bytes),0) as bytes "
            "from files where gpu_id=? and tier='remote'",
            (gpu.gpu_id,),
        )
        print(f"- GPU {gpu.gpu_id} ({gpu.logical_root})")
        print(f"  本地目录: {gpu.local_root}")
        print(f"  本地配额: {bytes_to_mib(gpu.local_quota_bytes)}")
        print(f"  本地已用: {bytes_to_mib(local_used)} ({percent:.1f}%)")
        print(
            f"  元数据: local {local_rows[0]['n'] if local_rows else 0} 个/"
            f"{bytes_to_mib(local_rows[0]['bytes'] if local_rows else 0)}, "
            f"remote {remote_rows[0]['n'] if remote_rows else 0} 个/"
            f"{bytes_to_mib(remote_rows[0]['bytes'] if remote_rows else 0)}"
        )
    print()

    print("远端后端")
    for backend in config.backends.values():
        used = directory_bytes(backend.root)
        print(f"- {backend.backend_id}: {backend.backend_type}")
        print(f"  根目录: {backend.root} ({'存在' if backend.root.exists() else '不存在'})")
        print(f"  已用:   {bytes_to_mib(used)}")
        if backend.backend_type == "nvmeof":
            print(f"  NVMe-oF: {backend.nvme_transport} {backend.nvme_target_ip}:{backend.nvme_port}")
            print(f"  NQN:     {backend.nvme_subnqn or '-'}")
            print(f"  设备:    {backend.nvme_device or '-'}")
            print(f"  挂载点:  {backend.nvme_mount or backend.root}")


def print_files(config: TokenfsConfig) -> None:
    read_count_expr = "coalesce(read_count,0)" if db_has_column(
        config.metadata_db, "files", "read_count"
    ) else "0"
    rows = db_rows(
        config.metadata_db,
        "select logical_path,gpu_id,tier,physical_path,size_bytes,checksum,state,"
        f"{read_count_expr} as read_count "
        "from files order by logical_path",
    )
    if not rows:
        print("没有文件元数据记录。")
        return
    for row in rows:
        print(
            f"{row['logical_path']} | gpu{row['gpu_id']} | {row['tier']} | "
            f"{bytes_to_mib(row['size_bytes'])} | {row['state']} | "
            f"reads={row['read_count']} | {row['checksum'] or '-'}"
        )
        print(f"  -> {row['physical_path']}")


def metric_value(metrics: dict[str, int], name: str) -> int:
    return metrics.get(name, 0)


def print_metrics(config: TokenfsConfig) -> None:
    rows = db_rows(config.metadata_db, "select name,value from metrics order by name")
    if not rows:
        print("没有 metrics 记录。先启动 TokenFS 并执行读写测试。")
        return
    metrics = {row["name"]: int(row["value"]) for row in rows}
    read_ops = metric_value(metrics, "read_ops")
    write_ops = metric_value(metrics, "write_ops")
    read_local = metric_value(metrics, "read_local_ops")
    read_remote = metric_value(metrics, "read_remote_ops")
    write_local = metric_value(metrics, "write_local_ops")
    write_remote = metric_value(metrics, "write_remote_ops")
    read_total = read_local + read_remote
    write_total = write_local + write_remote
    read_local_rate = (read_local / read_total * 100) if read_total else 0
    write_local_rate = (write_local / write_total * 100) if write_total else 0
    avg_read_us = metric_value(metrics, "read_latency_us_total") / read_ops if read_ops else 0
    avg_write_us = metric_value(metrics, "write_latency_us_total") / write_ops if write_ops else 0

    print("TokenFS Metrics")
    print("=" * 60)
    print(f"读请求:   {read_ops} 次，{bytes_to_mib(metric_value(metrics, 'read_bytes'))}")
    print(f"写请求:   {write_ops} 次，{bytes_to_mib(metric_value(metrics, 'write_bytes'))}")
    print(f"本地读:   {read_local} 次，{bytes_to_mib(metric_value(metrics, 'read_local_bytes'))}")
    print(f"远端读:   {read_remote} 次，{bytes_to_mib(metric_value(metrics, 'read_remote_bytes'))}")
    print(f"本地写:   {write_local} 次，{bytes_to_mib(metric_value(metrics, 'write_local_bytes'))}")
    print(f"远端写:   {write_remote} 次，{bytes_to_mib(metric_value(metrics, 'write_remote_bytes'))}")
    print(f"本地读命中率: {read_local_rate:.1f}%")
    print(f"本地写命中率: {write_local_rate:.1f}%")
    print(f"平均读耗时:   {avg_read_us:.1f} us")
    print(f"平均写耗时:   {avg_write_us:.1f} us")
    print(f"溢写次数:     {metric_value(metrics, 'spill_count')}")
    print(f"溢写数据量:   {bytes_to_mib(metric_value(metrics, 'spill_bytes'))}")
    print(f"远端初始放置: {metric_value(metrics, 'remote_place_count')} 次")
    print(f"远端打开读取: {metric_value(metrics, 'remote_read_open_count')} 次")
    print(f"热点提升次数: {metric_value(metrics, 'promote_count')}")
    print(f"热点提升数据: {bytes_to_mib(metric_value(metrics, 'promote_bytes'))}")
    print(f"提升空间不足: {metric_value(metrics, 'promote_skip_no_space')} 次")
    print(f"提升失败次数: {metric_value(metrics, 'promote_error_count')} 次")
    print(f"预取请求次数: {metric_value(metrics, 'prefetch_request_count')}")
    print(f"预取成功次数: {metric_value(metrics, 'prefetch_count')}")
    print(f"预取数据量:   {bytes_to_mib(metric_value(metrics, 'prefetch_bytes'))}")
    print(f"预取本地已有: {metric_value(metrics, 'prefetch_skip_local')} 次")
    print(f"预取目标缺失: {metric_value(metrics, 'prefetch_skip_missing')} 次")
    print(f"预取空间不足: {metric_value(metrics, 'prefetch_skip_no_space')} 次")
    print(f"预取失败次数: {metric_value(metrics, 'prefetch_error_count')} 次")
    print(f"预分配次数:   {metric_value(metrics, 'fallocate_ops')}")
    print(f"预分配数据量: {bytes_to_mib(metric_value(metrics, 'fallocate_bytes'))}")
    print()
    print("原始计数")
    for name in sorted(metrics):
        print(f"- {name}: {metrics[name]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="TokenFS 管理工具")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parents[1] / "config/tokenfs.dev.yaml"),
        help="TokenFS 配置文件路径",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="查看挂载、配额、后端和元数据状态")
    subparsers.add_parser("files", help="列出 SQLite 中记录的 TokenFS 文件")
    subparsers.add_parser("metrics", help="查看读写、命中率、溢写和预分配指标")
    args = parser.parse_args()

    command = args.command or "status"
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"配置文件不存在: {config_path}", file=sys.stderr)
        return 1
    config = parse_config(config_path)
    if command == "status":
        print_status(config, config_path)
    elif command == "files":
        print_files(config)
    elif command == "metrics":
        print_metrics(config)
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
