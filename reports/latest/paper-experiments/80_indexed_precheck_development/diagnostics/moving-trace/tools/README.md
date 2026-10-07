# Frozen80 moving74801 trace tools — prepared, not executed

This external toolkit diagnoses the remaining moving-input H gap. It runs exactly Full then NoHotspot,1152×2MiB each, using the completed80binary `f5e2981b8b4f0ce54bb2994e53998608de4cec4a3c861531e8e86e0aab031f71` and its355-file freeze. It does not change production source, the speed matrix or previous evidence. The prior public Full/NoAffinity draft remains separately preserved and is not the selected diagnostic.

The only added policy setting is request_trace_path. profile_control_path staysfalse; quota24MiB, retained capture4MiB, directI/O, the deferred submission/release fence, indexed precheck and original H ablation stay unchanged. The driver sets CPU affinity[0,2,4,6] before creating loaders/daemon and audits both environment receipts. It binds exact source, original80freeze/spec, actual binary, driver files, input and deterministic67object hashes. A new output/data directory is required, and an already-running TokenFS process blocks execution.

**No server execution has occurred.** Parent must finish reviewing80and decide whether to run these two diagnostic arms. Local selftests are not measurement results.

## Files and usage

Upload external runtime files only: tail-trace.py, tail-trace-analysis.py, collect-trace.py and tail-trace-freeze.json. Do not overwrite the frozen project. original-source-freeze.json is the downloaded receipt used in local selftests; runtime --freeze must point to the original80project receipt. planned-input.json/planned-configs.json describe the frozen intent with placeholder output paths and are not execution records.

If subsequently commissioned, an invocation can use the already observed project paths:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /PATH/TO/EXTERNAL/TOOLS/tail-trace.py run \
  --source-root /home/wjxt/projects/tokenfs-indexed-precheck80-20261007 \
  --binary /home/wjxt/projects/tokenfs-indexed-precheck80-20261007/build-release/tokenfs \
  --freeze /home/wjxt/projects/tokenfs-indexed-precheck80-20261007/study-configs/indexed-precheck-freeze.json \
  --diagnostic-freeze /PATH/TO/EXTERNAL/TOOLS/tail-trace-freeze.json \
  --output /home/wjxt/tokenfs-indexed-precheck80-moving-trace \
  --remote-root /srv/tokenfs/remote-cn7/indexed-precheck80-20261007
```

The script performs no performance-conditioned retry. Failure records and metadata remain in the new output. Successful cleanup removes only this diagnostic's newly generated remote object directory; it never deletes SQLite evidence or sidecars.

collect-trace.py is a separate explicit collector requiring --host, --remote-evidence and a new --output archive path. It refuses an active TokenFS process, streams the complete stopped directory including any WAL/SHM sidecars, and writes a hash/error receipt. It never checkpoints, removes sidecars, kills a daemon or retries. A failed partial download remains preserved. Extraction should be into a new local directory; the analyzer refuses sidecars rather than ignoring potentially uncheckpointed state. Any sidecar resolution needs an explicit separate collection decision, not unlinking files until the parser accepts them.

After download, run the driver's audit first against the extracted original80source, then the analyzer:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tail-trace.py audit \
  --source-root /PATH/TO/EXTRACTED/SOURCE80 \
  --diagnostic-freeze tail-trace-freeze.json --output /PATH/TO/RAW/DIAGNOSTIC
PYTHONDONTWRITEBYTECODE=1 python3 tail-trace-analysis.py \
  --evidence /PATH/TO/RAW/DIAGNOSTIC --output /PATH/TO/NEW/ANALYSIS
```

Audit requires exact configs,1152logical releases, complete background drain, zeroerrors, indexed-precheck activation/no fallback, and **both actual SQLite index definitions in each of the two databases**, plus input/source/binary/content/tier-byte/capture/capacity consistency. The core parser joins actual selected tier and handle to each client request using CLOCK_MONOTONIC; it rejects dropped records, bad timestamps or byte-accounting failures.

## Outputs and interpretation

analysis.json and per-arm request CSVs provide full request decomposition. same-ordinal-all.tsv compares all1152matching ordinal/key/caller tuples. same-ordinal-top12-union.json/tsv contains the union of both arms' twelve slowest requests, with each arm's actual tier/location, first/reused classification, client/daemon/pread times and clipped copy/planning overlap. Route can differ between arms and is never inferred from response time.

Each per-request physical_pread_ops/physical_pread_bytes field is explicitly null: frozen80records preadtime and logical readbytes, but not request-level physical operations/bytes/offsets. Aggregate physical metrics remain separate. Callback count is not syscall count, and aligned-tail reuse prevents equating logical/physicalbytes. Trace spans cannot isolate individual precheck SQL, allocation, Append, fsync or Rate updates. Copy/planning overlap is association; overlapping categories must not be added as disjoint causes. Release may complete after client close and is clipped explicitly.

Tracing perturbs scheduling. These two diagnostic durations must never enter80's performance tables, prove stable speedup or label the tiers of earlier untraced requests. p99rank is12thslowest for1152requests; each arm retains its own top12and the symmetric union.

## Local checks completed

selftest-result.json contains13successful checks with no SSH or TokenFS binary execution: completed80source/binary/spec binding; exact H-only configdelta; fixed1152input and67object hashes; generic parser replay on both retained77full public traces (2304requests total, strictly parser fixtures); top12union21rows; physicalIOfieldsnull; rejection of dropped traces, wrong bytes, sidecars (which remain intact), missing/wrong index definitions and mismatched requestkeys. Source80and original77evidence hashes are unchanged. No355source file was modified.

freeze_tools.py and selftest.py are local preparation/reproduction utilities; runtime must use the supplied frozen toolset, not silently regenerate its freeze after edits. The public draft resides at ../hotspot-indexed80-trace and has a separate input/config/driver freeze.
