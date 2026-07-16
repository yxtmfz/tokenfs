# TokenFS

TokenFS is a FUSE-based tiered filesystem prototype for large machine-learning token files.

The first milestone implements:

- `/gpu0` and `/gpu1` logical namespaces.
- Local-first storage under `/var/lib/tokenfs/local/gpu*`.
- Simulated remote storage under `/var/lib/tokenfs/remote-sim`.
- SQLite metadata recording each file's logical path, tier, backend and physical path.
- Automatic spill from local to remote when a write/truncate would exceed a GPU quota.

This version uses ordinary directories as storage backends. Later, the simulated remote directory can be replaced by an NVMe-oF mounted filesystem such as `/srv/tokenfs/remote0`.

## Build

```bash
cmake -S . -B build -G Ninja
cmake --build build
```

## Run

```bash
./build/tokenfs --config config/tokenfs.dev.yaml -f /mnt/tokenfs
```

In another terminal:

```bash
mkdir -p /mnt/tokenfs/gpu0/demo
echo hello > /mnt/tokenfs/gpu0/demo/a.tokens
cat /mnt/tokenfs/gpu0/demo/a.tokens
find /var/lib/tokenfs -maxdepth 4 -type f -o -type d
sqlite3 /var/lib/tokenfs/metadata/tokenfs.db 'select logical_path,tier,physical_path,size_bytes from files;'
```

Unmount:

```bash
fusermount3 -u /mnt/tokenfs
```

Or use the helper scripts:

```bash
./scripts/start_tokenfs.sh
./scripts/smoke_test.sh
./scripts/stop_tokenfs.sh
```

## Current Scope

This is a development prototype, not a production distributed filesystem yet. It is intentionally single-host and directory-backed so that FUSE behavior, metadata, quota and spill policy can be validated before connecting real NVMe-oF storage.
