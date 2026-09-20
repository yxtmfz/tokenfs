# Three-factor storage experiment: frozen interpretation and comparisons

This plan precedes all round-3 confirmation runs. Development observations are
separate and may reject a defective implementation before a new freeze. They do
not count as confirmatory speed evidence. The previous B3 results are immutable.

## Executed scope and implementation

The cn7 client has an existing real NVMe/TCP mount to cn13. cn8 has no such mount
and is used for independent directory-backend content checking. Three logical
caller domains share cn7's physical local disk but have **private cache access**:
caller-local READY replica, otherwise remote canonical. An owner-local copy is
not directly addressable by another domain. This access restriction is identical
for all strategies; it is not injected latency. No physical GPU, PCIe/NVLink,
multi-node scaling or inference throughput claim follows from this topology.

The optional `private_cache_domains` switch defaults off. Existing measured/B3
behavior remains the default. The round-3 prototype is a new opt-in configuration,
not a claim that the full Python controller has been integrated.

- H: enable the already implemented conservative fast hotspot reset. Natural
  sliding history, reuse evidence, measured rates and candidate ordering remain
  present when H is disabled. Its ablation identifies **extra fast adaptation**,
  not every part of the earlier broad value-management model.
- P: enable a recent access-share gate on actual replica admission. In the last
  128 global observations, the caller's count for the object must reach half the
  largest domain count for that object. Equal sharing remains eligible. All
  compared measured variants collect the same observations, even with P off.
  There is no future request or workload-phase information in policy decisions.
- J: jointly charge the predicted loss of all selected victims and the copy cost
  against incoming repeat-read savings. With J off, the same candidate ordering,
  copy-cost admission, quota/pinning checks and execution recheck remain; the
  placement and eviction decisions do not jointly debit displacement loss.
  This is a net-gain admission controller, not complete robust optimization,
  uncertainty bounds, distributed coordination or strong copy-before-delete SWAP.

Measured service/copy rates are actual observed durations with the existing cold
start prior. No artificial I/O delay is added. Existing prior limitations remain:
one global per-byte local/remote service estimate, buffered background copies,
final visible quota instead of strict physical peak space, serialized callers.

## Matrix

Eight confirmation strategies: RemoteOnly, equal-capability LRU, LFU, exact
RecentLFU-admit, J-no-H (only fast reset removed), J-no-P (only affinity gate
removed), I (only joint loss debit removed), J (all three enabled).
Development also includes B (H/P/J off), H only and P only for diagnosis.
RecentLFU retains its standard frequency admission comparator; it is not relabeled
as B. LRU/LFU have the same per-caller two-read admission threshold and asynchronous
copy capability. All policies have identical private-domain routing and cache
quota, with RemoteOnly explicitly using zero quota.

Six scenarios: static affinity, caller shift with fixed hot objects, hot-object
shift with fixed caller schedule, simultaneous caller/object shift under capacity
pressure, Mooncake toolagent block replay, uniform random negative control.

Synthetic main runs use 384 requests, 2 MiB objects, 8 MiB quota per domain.
Public runs use 768 normalized 1 MiB blocks and the same 8 MiB quota. All runs
read 768 logical MiB. Public caller = original source-request index modulo 3;
this is a constructed domain mapping, not original GPU identities or original
serving concurrency. Source identity and order are preserved. Arrival time is
retained but not paced. The pinned Mooncake source and twelve windows are recorded
in `study-configs/affinity-joint-public-windows.json`; ranges do not overlap prior
B3 main/supplement windows or each other and lie outside the development prefix.

Correctness: 54 initial plus 12 added direct-ablation cases per host, totaling 66.
Development: 54 initial plus 18 direct-ablation comparisons; diagnostic only.
Confirmation: seeds 1601--1612, six scenarios x eight strategies x twelve paired
blocks = **576** cases. The direct full-minus-one variants were added before any
confirmation access so the four final tables attribute each module in the full
configuration. Strategy order is randomized
within each block and block order is independently randomized. Fixed n=12 does
not promise power for small effects; no significance-driven sample extension.

Each block fixes byte identity, request sequence, caller IDs, quota, replica
capability, copying/checksum/concurrency, initialization and timing boundaries.
Each run starts with empty application caches. Client foreground I/O is direct
on both tiers; target caches and other tasks are not controlled. The finite short
traces are not hour-long steady state or saturated concurrent-client scaling.

## Four deliverable tables and decisions

1. Hotspot: J/J-no-H, showing both absolute MiB/s and paired throughput changes;
   six comparisons, exactly one configuration switch differs.
2. Affinity: J/J-no-P, same reporting and six-comparison family.
3. Joint: J/I in six scenes; this is the direct test of joint versus independent
   decisions. Development-only exploratory interaction: T(I)-T(H)-T(P)+T(B),
   negative favorable; no confirmatory interaction or superadditivity claim.
4. Overall: J versus RemoteOnly, LRU, LFU, RecentLFU in every scene, twenty-four
   comparisons. Include all absolute rates and every uncertain/negative outcome.

The primary endpoint is outer monotonic time from replay start to the final read
return. Actual MiB/s = logical bytes / 2^20 / elapsed time. Queue-drain time,
per-run empirical p50/p99, copied payload, daemon CPU/RSS, and mechanism activity
are secondary. Queue drain is not full kernel writeback or durability. A speed
advantage reversing after drain must be disclosed.

Use geometric paired time ratios, 5,000-resample paired bootstrap intervals,
two-sided sign-flip p-values, and Holm correction within the four families above.
Confidence intervals are not multiplicity-adjusted. A confirmed speed claim
requires twelve pairs, interval wholly below one and Holm p<0.05. An intended
practically meaningful improvement is at least 5% elapsed reduction, not an
assumption or a guarantee. No all-workload win or literature-novelty claim is
inferred solely from these experiments.

Source/build/spec/public-window hashes must be frozen after content validation
and development. Confirmation uses the exact frozen artifact and starts only
after both hosts pass correctness. Audit every expected case, configuration,
request/byte/caller/source accounting, private-domain routing count, content
hashes in correctness runs, queue completion, final visible quotas, timeline and
finite resource measurements. Keep raw failed attempts and all development data.
Do not alter the policy after viewing confirmation outcomes.
