#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_file="${TOKENFS_CONFIG:-$project_root/config/tokenfs.dev.yaml}"
mount_point="${1:-}"

"$project_root/scripts/stop_tokenfs.sh" "$mount_point" >/dev/null 2>&1 || true

python3 - "$project_root" "$config_file" "$mount_point" "${TOKENFS_RESET_REMOTE:-0}" <<'PY'
import os
import shutil
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
config_file = Path(sys.argv[2])
mount_arg = sys.argv[3]
reset_remote = sys.argv[4] == "1"

sys.path.insert(0, str(project_root / "scripts"))
from tokenfsctl import parse_config  # noqa: E402

config = parse_config(config_file)
mount_point = Path(mount_arg) if mount_arg else config.mount_point

def guarded(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    forbidden = {
        Path("/"),
        Path("/home"),
        Path("/root"),
        Path("/var"),
        Path("/srv"),
        Path("/srv/tokenfs"),
    }
    if resolved in forbidden:
        raise SystemExit(f"refuse to reset unsafe path: {resolved}")
    if len(resolved.parts) < 4:
        raise SystemExit(f"refuse to reset shallow path: {resolved}")
    return resolved

def reset_dir(path: Path) -> None:
    resolved = guarded(path)
    shutil.rmtree(resolved, ignore_errors=True)
    resolved.mkdir(parents=True, exist_ok=True)

def clean_children(path: Path) -> None:
    resolved = guarded(path)
    resolved.mkdir(parents=True, exist_ok=True)
    for child in resolved.iterdir():
        if child.name == "lost+found":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except FileNotFoundError:
                pass
            except PermissionError:
                pass

for gpu in config.gpus:
    reset_dir(gpu.local_root)

metadata_db = guarded(config.metadata_db)
metadata_db.parent.mkdir(parents=True, exist_ok=True)
for suffix in ("", "-wal", "-shm"):
    try:
        Path(str(metadata_db) + suffix).unlink()
    except FileNotFoundError:
        pass

for backend in config.backends.values():
    if backend.backend_type == "directory":
        reset_dir(backend.root)
    elif backend.backend_type == "nvmeof" and reset_remote:
        clean_children(backend.root)
    else:
        backend.root.mkdir(parents=True, exist_ok=True)

mount_point = guarded(mount_point)
mount_point.mkdir(parents=True, exist_ok=True)
PY

echo "TokenFS development state reset."
