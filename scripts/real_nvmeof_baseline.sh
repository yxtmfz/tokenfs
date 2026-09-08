#!/usr/bin/env bash
set -euo pipefail

result_root="${AURA_REAL_RESULT_ROOT:-reports/latest/real-nvmeof}"
remote_device="${AURA_REMOTE_DEVICE:-}"
local_read_device="${AURA_LOCAL_READ_DEVICE:-}"
local_file="${AURA_LOCAL_FILE:-/tmp/aura-kv-local-fio.bin}"
remote_offset="${AURA_REMOTE_OFFSET:-4G}"
test_size="${AURA_TEST_SIZE:-1G}"
seq_bs="${AURA_SEQ_BS:-1M}"
rand_bs="${AURA_RAND_BS:-4k}"
iodepth="${AURA_IODEPTH:-32}"
runtime="${AURA_RUNTIME:-15}"

usage() {
  cat <<EOF
Usage:
  AURA_REMOTE_DEVICE=/dev/nvmeXnY $0

Optional:
  AURA_LOCAL_READ_DEVICE=/dev/nvme0n1   # read-only local NVMe baseline
  AURA_LOCAL_FILE=/path/to/local.bin    # writable local file baseline
  AURA_REAL_RESULT_ROOT=reports/latest/real-nvmeof
  AURA_TEST_SIZE=1G
  AURA_REMOTE_OFFSET=4G

Safety:
  - local NVMe device tests are read-only.
  - remote write tests write only to AURA_REMOTE_DEVICE at AURA_REMOTE_OFFSET.
    Use this only with a dedicated NVMe-oF test namespace/backing file.
EOF
}

if [[ -z "$remote_device" || ! -b "$remote_device" ]]; then
  usage >&2
  exit 2
fi

mkdir -p "$result_root/fio-json"

capture_env() {
  {
    echo "time=$(date -Is)"
    echo "host=$(hostname)"
    echo "kernel=$(uname -r)"
    echo "remote_device=$remote_device"
    echo "local_read_device=${local_read_device:-none}"
    echo
    nvme list || true
    echo
    lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL || true
  } > "$result_root/env.txt"
}

run_fio() {
  local name="$1"
  local filename="$2"
  local rw="$3"
  local bs="$4"
  local size="$5"
  shift 5

  echo "perf: $name"
  sudo fio \
    --name="$name" \
    --filename="$filename" \
    --rw="$rw" \
    --bs="$bs" \
    --size="$size" \
    --iodepth="$iodepth" \
    --ioengine=libaio \
    --direct=1 \
    --numjobs=1 \
    --group_reporting \
    --runtime="$runtime" \
    --time_based \
    "$@" \
    --output="$result_root/fio-json/$name.json" \
    --output-format=json
}

summarize() {
  python3 - "$result_root" <<'PY'
import csv
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
rows = []
for path in sorted((root / "fio-json").glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    job = data["jobs"][0]
    op = "read" if job["read"]["io_bytes"] else "write"
    stats = job[op]
    lat = stats.get("clat_ns", {}).get("percentile", {})
    rows.append([
        path.stem,
        op,
        round(stats.get("bw_bytes", 0) / 1024 / 1024, 2),
        round(stats.get("iops", 0), 2),
        round(lat.get("50.000000", 0) / 1e6, 3),
        round(lat.get("95.000000", 0) / 1e6, 3),
        round(lat.get("99.000000", 0) / 1e6, 3),
    ])

with (root / "summary.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["case", "op", "bandwidth_mib_s", "iops", "p50_ms", "p95_ms", "p99_ms"])
    writer.writerows(rows)

report = ["# Real NVMe-oF Baseline", "", "| Case | Op | Bandwidth MiB/s | IOPS | P50 ms | P95 ms | P99 ms |", "|---|---|---:|---:|---:|---:|---:|"]
for row in rows:
    report.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} |")
(root / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

print(f"summary: {root / 'summary.csv'}")
print(f"report:  {root / 'report.md'}")
PY
}

capture_env

run_fio local_file_seq_write "$local_file" write "$seq_bs" "$test_size"
run_fio local_file_seq_read "$local_file" read "$seq_bs" "$test_size"

if [[ -n "$local_read_device" && -b "$local_read_device" ]]; then
  run_fio local_nvme_seq_read "$local_read_device" read "$seq_bs" "$test_size" --readonly
  run_fio local_nvme_randread_4k "$local_read_device" randread "$rand_bs" "$test_size" --readonly
fi

run_fio remote_nvmeof_seq_write "$remote_device" write "$seq_bs" "$test_size" --offset="$remote_offset"
run_fio remote_nvmeof_seq_read "$remote_device" read "$seq_bs" "$test_size" --offset="$remote_offset"
run_fio remote_nvmeof_randread_4k "$remote_device" randread "$rand_bs" "$test_size" --offset="$remote_offset"

summarize
