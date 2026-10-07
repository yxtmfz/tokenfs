# Frozen 77 public74802 tail diagnosis

Prepared locally; not executed on a server. It must run only after the original 24 speed runs and their correctness checks finish. This diagnosis has exactly two arms, Full then NoHotspot, each replaying all 1,152 original requests. It uses binary `6334375577555abe6886db40a49f55f379f8291993880fdf6f8d5c4cdd2cf8cb` and the same 340 source files as 77. Only request tracing and control-path profiling are enabled. Per-request SHA remains disabled; `run_case` still validates retained replica contents after timing. This is not performance evidence and must never enter the four performance tables.

Upload only `tail-trace.py`, `tail-trace-analysis.py`, and `tail-trace-freeze.json` into a new directory outside the frozen source tree. Do not overwrite any source or prior evidence. The output path must not already exist; the remote parent must be the already verified cn13 NVMe/TCP mount. The driver refuses a live TokenFS process, wrong binary/source/build type, altered driver, or altered trace/configuration. It does not retry failed arms or select favorable runs.

Example invocation after serial execution is confirmed (replace `/home/wjxt/tokenfs-trace77-tools` with the actual tools directory):

```sh
python3 /home/wjxt/tokenfs-trace77-tools/tail-trace.py run \
  --source-root /home/wjxt/projects/tokenfs-object-cohort77b-20261007 \
  --binary /home/wjxt/projects/tokenfs-object-cohort77b-20261007/build-release/tokenfs \
  --freeze /home/wjxt/projects/tokenfs-object-cohort77b-20261007/study-configs/object-cohort-freeze.json \
  --diagnostic-freeze /home/wjxt/tokenfs-trace77-tools/tail-trace-freeze.json \
  --output /home/wjxt/tokenfs-object-cohort77-tail-diagnostic \
  --remote-root /srv/tokenfs/remote-cn7/object-cohort77-20261007
```

After downloading the diagnostic directory, extract the original source archive to a temporary local directory and perform the source/configuration audit and analysis. The audit does not execute the binary or access a remote mount. Use absolute paths or paths relative to the actual working directory:

```sh
python3 tail-trace.py audit --source-root /PATH/TO/EXTRACTED/77 \
  --diagnostic-freeze tail-trace-freeze.json --output /PATH/TO/EVIDENCE
python3 tail-trace-analysis.py --evidence /PATH/TO/EVIDENCE --output /PATH/TO/NEW/REVIEW
```

`analysis.json`, per-arm request CSVs, and `tail-top12.md` separate first accesses from reused objects and report client open/read/close, daemon open/read/release, physical pread, clipped asynchronous release, and copy/plan overlap. Overlap is not proof of causality. Categories overlap and must not be added together. The final nonempty read callback and its non-pread residual are explicitly reported.

The frozen source places `RecordLatency` and `AccountRequestReadCost` before capture completion and `ScheduleSharedPlacement`. `SubmitBackground` synchronously increments `background_submitted` even with background metric batching. End-to-end response and the full read trace span include this tail, while read cost samples/histograms omit it. There is no independent Submit/Append trace timestamp in 77; read-minus-pread is an upper bound containing allocation, copying, counters, capture, scheduling, and possible synchronization. It cannot establish that all residual time is a submitted-counter fsync. A future implementation change must preserve submitted/completed accounting and the durable drain fence.

Local checks: compile both Python files; verify all 340 source hashes from the actual source archive; fixed 1,152-event trace and 864 deterministic object SHAs; exact Full/NoHotspot policy delta only `measured_static_reuse_value`; replay analyzer on both existing report-73 public diagnostic traces (2,304 requests total); reject dropped traces and byte-accounting tampering. See `tail-trace-selftest.json`. Old report-73 timings were only parser tests and must not be used to claim new performance.
