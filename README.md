# TokenFS

TokenFS is a FUSE-based tiered filesystem prototype for large machine-learning token files.

The current prototype implements:

- `/gpu0` and `/gpu1` logical namespaces.
- Local-first storage under `/var/lib/tokenfs/local/gpu*`.
- Simulated remote storage under `/var/lib/tokenfs/remote-sim`.
- SQLite metadata recording each file's logical path, tier, backend, physical path,
  checksum, state and size.
- Automatic spill from local to remote when a write/truncate would exceed a GPU quota.
- A v2 write lifecycle with `CREATING` and `COMMITTED` file states.
- Startup recovery for incomplete file records and temporary files.
- Optional `fnv1a64` checksum recording for committed files.

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
./scripts/reset_dev_state.sh
./scripts/start_tokenfs.sh
./scripts/smoke_test.sh
./scripts/stop_tokenfs.sh
```

## V2 Integration Test

The v2 test resets the development backend, builds the binary, mounts TokenFS,
checks local writes, remote spill, checksum metadata, delete cleanup and startup
recovery for incomplete files.

```bash
./scripts/v2_integration_test.sh
```

Expected final line:

```text
TokenFS v2 integration test passed.
```

## Metadata State Model

TokenFS records each file with a simple lifecycle:

- `CREATING`: the file exists physically, but the write has not been committed.
- `COMMITTED`: the file has been synced and its metadata has been finalized.

On startup, TokenFS removes stale `CREATING` files and metadata rows. This keeps
crashed or half-written token files from becoming visible as valid data.

## Current Scope

This is a development prototype, not a production distributed filesystem yet. It is intentionally single-host and directory-backed so that FUSE behavior, metadata, quota and spill policy can be validated before connecting real NVMe-oF storage.

## NVMe-oF Deployment Path

For real NVMe-oF deployment, keep the TokenFS data path unchanged and replace the
simulated remote backend:

```text
/var/lib/tokenfs/remote-sim
```

with a mounted NVMe-oF namespace such as:

```text
/srv/tokenfs/remote0
```

The connection and mount steps belong in deployment scripts:

```bash
export TOKENFS_NVME_TARGET_IP=<SSD_TARGET_IP>
export TOKENFS_NVME_SUBNQN=<SUBSYSTEM_NQN>
export TOKENFS_NVME_DEVICE=/dev/nvmeXnY
export TOKENFS_NVME_MOUNT=/srv/tokenfs/remote0

./scripts/connect_nvme.sh
```

To unmount and disconnect:

```bash
./scripts/disconnect_nvme.sh
```

The helper scripts deliberately do not run `mkfs`; formatting a real namespace
must be a separate explicit operation.
