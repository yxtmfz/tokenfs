# Object-level newcomer reuse evidence: development protocol

This campaign follows report66, whose results remain immutable. Its moving seed73501
and public source window73602 were inspected to diagnose hotspot regressions;
reusing them here is development, not independent validation.

The candidate changes only RunReuse::NewcomerDiskPrior. The prior is the number
of distinct objects observed returning in separate runs divided by retained
object count plus one. Repeated returns of the same object do not increase this
probability. First returns increment a bounded counter; eviction from history
subtracts it. Query cost remains O(1). The current unfinished burst, workload
labels, source request ids and future accesses are not policy inputs.

The prior remains a heuristic, not a calibrated probability or confidence bound.
Sparse, recently observed objects are conservatively included in the denominator.
Other valuation, placement, admission, I/O, durability and capture behavior stay
unchanged. NoHotspot disables dynamic valuation through the existing single flag.

24 timed runs: two previously inspected inputs, two reversed-order repetitions,
Full/NoHotspot/NoAffinity/NoJoint/PoolSIEVE1/OldFull. Each has1152 requests of2MiB,
24MiB disk capacity and4MiB shared retained capture. OldFull executes the retained
report64/66 binary with exactly the Full policy configuration. Both binary hashes
and each case's selected binary are recorded. All cold requests and drain times
are retained. Runs execute serially on cn7 logical domains and cn13 NVMe/TCP.

Primary outcomes: actual bytes/job-wall-time and request response p99. Compare
Full against NoHotspot to measure H's marginal effect, against OldFull to assess
absolute regression, and all other ablations/SIEVE to detect sacrificed gains.
Report both repetitions, aggregate bytes/aggregate time, and median per-run p99;
keep negative results. Do not adopt merely for higher hit rate or favorable means
that conceal direction reversals. This small diagnostic is not significance proof.

Before timing, run native/Python tests; afterwards run separate per-read content
checks and independently recompute metrics from request records and durable
SQLite counters. Preserve old sources, raw outcomes, inputs and audit receipts.
