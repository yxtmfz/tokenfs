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


def print_files(config: TokenfsConfig) -> None:
    rows = db_rows(
        config.metadata_db,
        "select logical_path,gpu_id,tier,physical_path,size_bytes,checksum,state "
        "from files order by logical_path",
    )
    if not rows:
        print("没有文件元数据记录。")
        return
    for row in rows:
        print(
            f"{row['logical_path']} | gpu{row['gpu_id']} | {row['tier']} | "
            f"{bytes_to_mib(row['size_bytes'])} | {row['state']} | "
            f"{row['checksum'] or '-'}"
        )
        print(f"  -> {row['physical_path']}")


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
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
