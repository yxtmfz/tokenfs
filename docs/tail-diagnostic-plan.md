# Six request-correlated diagnostic runs (study 23)

User approved the previously proposed six-run extension on 2026-09-28.
AdaptiveHP, PoolSIEVE2 and PoolSIEVE1 each run moving_shared seeds 3221 and 3222,
576 requests of 2 MiB, total 24 MiB cache, identical study-22 configuration except
optional request_trace_path. Keep original source policy, input generator, verification,
direct I/O and SQLite FULL-WAL durability. Use cn7 and its existing cn13 NVMe/TCP
mount. Do not contact cn14. No extra speed runs or post-result replacements.

Build/test first, then freeze source, Release binary and specification hashes.
Native tests check tracing bounds, escaping, content and handle association.
Three policies use the same monotonic-clock instrumentation. At most 32768 events,
512 bytes per path, held in memory and dumped after background drain and unmount.
A nonzero dropped count or incomplete association invalidates the diagnostic.

Open: handle, object, caller, tier, duration and layout wait. Read: each FUSE callback
and its actual pread duration/bytes, including EOF. Release: handles-lock wait,
duration and metric flush. GetAttr records lookup/lock durations. Copy pipeline:
interval after capacity admission, including copy, checksums and metadata commit;
copy/verification subdurations separately. It excludes planning and capacity eviction.
Client loader: monotonic timestamps before open, after open, after EOF and after close.
No extra per-request disk output or fsync. Trace locks/timestamps can perturb timing.

Offline checks associate every logical request with exactly one successful Open,
its reads and Release; bytes must agree with raw input and durable SQLite counters.
Inspect the slowest six requests per run (upper 1%), matched by handle. Separate
client open/read/close, actual pread, daemon control, and unaccounted FUSE/scheduling
time. Release may be asynchronous and must not be naively added to synchronous
client latency. Compare copy overlap within local/remote strata, but overlap alone
does not prove contention. No statistical significance with two seeds.

All six results, including regressions, are diagnostic only, not replacement formal
speed results. Study 22 remains authoritative for prior speed gates. Report measured
bottlenecks, remaining uncertainty and a concrete next repair/validation proposal;
do not pre-promise p99 or speed superiority.
