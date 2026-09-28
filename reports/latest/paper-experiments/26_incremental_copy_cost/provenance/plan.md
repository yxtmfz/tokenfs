# Incremental copy cost: fixed development pilot

The previous estimator charges successful-copy wall time including already-paid
admission planning and capture. At the decision point these cannot be saved by
rejecting the copy. Measure full pipeline, planning, and capture separately; use
pipeline minus planning as the remaining charge when explicitly enabled. Keep
all eviction, destination write, checksum, fsync configuration, and READY metadata
publication costs. This is not a measurement of marginal foreground contention:
asynchronous overlap receives no assumed discount. Preserve full cost counters.

One binary, same request cost aggregation and captured read-fill for all policies.
IncrementalHP differs from AdaptiveHP by exactly incremental_copy_cost=true;
PoolSIEVE1/2 are unchanged strong system baselines. Safety and current-demand
rechecks remain active; no frozen plan or predicted future trace bypasses them.

Freeze before execution: moving_shared seeds 3251/3252, uniform seed 3253;
4 policies each = 12 runs, 576 requests each, 2 MiB per request, 24 MiB total
retained cache and 4 MiB transient capture budget. Use existing trace generators.
Order shuffled once with seed 3250; reverse in second moving block, rotate in
uniform. No replacements, parameter sweeps or optional stopping. Real cn7 to
existing cn13 NVMe/TCP only. No cn14, physical GPUs, or large-scale experiments.

Gate for another development step: moving paired geometric throughput gain >=5%
and both moving seeds faster against each SIEVE baseline; no per-seed p99
regression; uniform speed/tail no regression against each baseline. Also report
all treatment/old pairs. These n=2/n=1 checks are exploratory, not significance.
Retain failures and examine exact copy cost identities, remote bytes, copies,
execution rejections and throughput including drain. Latest component ablations
are a separate unmet requirement, not established by this system comparison.
