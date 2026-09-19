# Measured-policy confirmation plan

Drafted before any performance access to the held-out application records or seeds
501--512. Execution requires completion of B2 development and a committed freeze
record identifying the source revision, binary hashes, and final specification.
Development outcomes are retained separately and cannot be pooled with confirmation.

## Question and scope

Does the executable, measured-cost admission policy reduce real storage-replay wall
time relative to equally provisioned LRU/LFU and the recent-frequency admission
reference? Which implemented components cause a speed change?

This is a read-only, immutable-object FUSE storage study on cn7 -> cn13 NVMe/TCP.
The client and target do not constitute dedicated bare NVMe hardware. Foreground
reads use O_DIRECT on both tiers; buffered copy and target caches are disclosed.
It is not an inference, physical multi-GPU, robust-optimization, or crash-safety
experiment. The new policy does not inherit those claims from the Python design.

## Fixed main matrix

`study-configs/measured-confirm-01.json` is authoritative. There are 12 paired
blocks per scenario, seeds 501--512. Each block uses exactly the same requests,
payload identities, quota, copy verification, and background concurrency across
strategies; fresh application caches and randomized strategy order are used.
The complete block order is independently randomized with seed 91571.

- Five synthetic scenarios: stable, shifting hotspots, hotspot plus scan, variable
  object sizes with every object individually fitting, and uniform random. Each
  run has 384 requests, 2 MiB base objects, and an 8 MiB cache per logical domain.
- Two public datasets: Mooncake conversation and toolagent at pinned revision
  97030cacfbf8db7d0098e35da46c58abbae04593. The first 20% of source requests is
  development-only. Divide the remaining 80% into 12 equal request-index bins;
  replay the first 2048 blocks at each bin start. Check and record that adjacent
  selected request ranges do not overlap before execution. Do not select windows
  according to observed reuse or performance. Each block is normalized to 1 MiB,
  with 16 MiB quota. Preserve identity and order; primary replay is saturated.
- Primary references in every scene: LRU-equal, LFU-equal, RecentLFU-admit.
  RemoteOnly is an additional no-cache control. The first two share a two-open
  admission threshold and asynchronous copying; RecentLFU is an exact bounded
  frequency reference, not a claimed reproduction of W-TinyLFU.
- Component allocation is explicitly listed in the JSON: admission and value
  victim selection in stable/scan, their two-factor combination in stable/scan,
  aging and shift detection in shifting/stable workloads, shift detection in
  uniform random, size in mixed_fit, measured cost in shift/mixed_fit/uniform/
  toolagent, and asynchronous execution in stable. Untested component/scene
  combinations are not implicit successes.

All decision parameters are frozen together. No confirmation-result-based parameter
selection, scene removal, baseline weakening, sample extension, or winner selection
is allowed. A later redesign requires a new development/confirmation separation.

## Endpoints, uncertainty, and practical significance

Primary endpoint: externally measured monotonic time to complete all foreground
requests. Actual MiB/s equals identical logical bytes divided by that time. Timing
excludes mount/setup/data generation and post-run retained-copy verification;
all strategies share those boundaries. Report absolute seconds and MiB/s as well
as paired log time ratios. Also report total time including background drain,
request p50/p99, daemon CPU seconds, RSS, local bytes, and copied payload bytes.
Payload bytes are not NIC traffic or physical device writes.

The sampling unit is an entire paired run/window, not an individual read. For each
scene/reference report a geometric mean time ratio, 5000-resample paired bootstrap
95% interval, and two-sided paired sign-flip p-value (symmetric-null assumption).
The 21 primary comparisons (7 scenes x 3 references) form one Holm family. Each
component and RemoteOnly have their own across-scene Holm family; this does not
control the error rate of every statement in the paper. Bootstrap intervals are
not multiplicity-adjusted. The minimum exact two-sided p with 12 pairs is 2/4096;
this permits, but does not guarantee, resolution after 21-way correction.

There is no defensible pilot variance for every public window. The fixed n=12
budget is declared in advance, not described as a universal power guarantee.
Small effects may remain uncertain. Do not extend the sample to obtain significance.

A confirmed speed claim requires n=12, Holm p<0.05, and the interval entirely
below one. A headline practical improvement additionally requires at least 5%
lower geometric mean time in the stated target scene, against all three primary
references. Report smaller effects accurately without calling them substantial.
An equal-weight aggregate over all seven scenes may be reported descriptively;
it is not a production workload-weighted estimate or a new significance test.

For the uniform negative control, an upper 95% time-ratio bound below 1.05 versus
RemoteOnly is the stated descriptive non-inferiority criterion; absence of a
significant slowdown alone is insufficient. If including background drain reverses
a speed advantage, disclose both and do not claim total-work acceleration.

## Mechanism evidence and limits

Check actual admissions/rejections, evictions, shift resets, local read bytes and
copy costs. An untriggered ablation cannot establish the necessity of its component.
The stable/scan four-cell interaction is exploratory:
T(full) - T(no-admission) - T(no-value) + T(no-joint); negative favors interaction.
Report its paired interval rather than inferring synergy from four means.

Capacity, longer-duration, timestamp-paced and parameter-window checks are separate
supplementary experiments. Their smaller replication counts are descriptive;
do not pool them into the fixed primary family or use them to tune this version.
Per-request content hashing runs are separate from all performance evidence.

## Failure and evidence retention

Require complete matrix/config/trace/byte/source/queue/content/capacity audits.
Capacity audit means final visible cache bytes; it does not prove a strict peak
physical-space bound including temporary or unlinked-but-open files.
Preserve all attempted runs and failure records. A harness or correctness defect
invalidates the affected batch; document the cause and replacement before another
freeze. Do not discard slow but valid runs. Every archive records input, source,
configuration and binary hashes. Preserve B1/B2 development results and the earlier
formal-02 negative results. Conclusions follow the measurements, including a
possible failure to establish an advantage.
