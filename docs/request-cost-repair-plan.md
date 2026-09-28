# Study25: six small repair checks, after preserving all twelve study24 runs

The user requested continued small-scale fixes before larger validation. Study24
is a failed development attempt and must remain visible: the second AdaptiveHP-fill
run fell to 86.24 MiB/s with 848 MiB remote reads. No rerun replaces that result.

Code inspection and study23 raw traces expose a definite sampling bug: each FUSE
callback's us/byte was fed equally into an EWMA. A 48-byte tail and a roughly 1 MiB
chunk received equal weight. In study24 the first SHARED_PLACE's estimated 2 MiB
copy prior became 1.45–1.57 seconds; such per-byte estimates do not represent a
whole request. Fragment size can reverse the local/remote ordering even when
the complete local read is substantially faster. The native regression reproduces
that false rejection and verifies the fix. This is a cost-estimator correction,
not a new reuse heuristic or evidence that this bug explains every slowdown.

Accumulate actual positive read bytes and callback durations within a logical
open. Emit once on complete sequential coverage; partial/reordered requests emit
once at EOF/Release. No tiny sample is deleted, no fabricated bandwidth or minimum
speed advantage. Same collection on all three policies, same verified read-fill
path and 4 MiB transient budget, same 24 MiB retained capacity. Detailed telemetry
stays off. Do not change admission thresholds or the workload.

Also correct evidence snapshots: some final buffered decision metrics were flushed
only at daemon shutdown, after result.json had been written. Preserve study24's
original file and enumerate that discrepancy. Future results use the final durable
metrics after unmount, assert that I/O/request/background completion counters did
not change, and leave measured times untouched. This does not change runtime
SQLite durability or add a performance-path fsync.

Exactly six NEW development runs: AdaptiveHP, PoolSIEVE1, PoolSIEVE2 on seeds3241,
3242 in unchanged moving_shared, 576 x 2 MiB each. Shuffle three variants with3240,
reverse order for the second seed. One Release binary, source/spec hashes frozen
after tests. Native tests cover sample fragmentation invariance, false-admission
regression, EOF/partial/reordered accounting, and the actual TokenFS read path.
The original12 plus this6 are eighteen small development runs, no large-scale
study. Do not replace failures or compare different seeds/versions as causal gains.

Primary gate remains paired throughput >=5% and 2/2 wins against EACH equally
optimized SIEVE baseline, with every p99 no higher. Record all failed gates.
Additionally verify exactly one read-cost sample per full logical request and
matching bytes per tier, source-fill bytes/limits, durable SQL and final counters.
No same-seed broken-estimator timed arm is included: timing alone cannot quantify
the isolated estimator correction, despite its deterministic native reproduction.
No statistical significance, latest H/P/J proof, uniform robustness, or physical
GPU inference claim follows from these two synthetic seeds.
