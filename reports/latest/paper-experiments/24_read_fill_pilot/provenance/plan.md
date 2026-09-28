# Read-fill pilot, study 24: twelve fixed development runs

The user requested continued small-scale repair and validation before any large
study. Follow the study-23 proposal: three policies (AdaptiveHP, PoolSIEVE1,
PoolSIEVE2) x old/source-copy or foreground-read-fill x seeds 3231 and 3232.
Exactly 12 timed runs, moving_shared unchanged, 576 x 2 MiB, 24 MiB total retained
cache. Shuffle six variants with seed3230, reverse order for the second seed.
This balances early/late order only, not all six possible positions.

Keep immutable canonical storage, foreground O_DIRECT both tiers, verified target
copies and SQLite FULL-WAL. No request telemetry or aggregate control profiling
in any arm. Only the foreground_read_fill flag differs within a policy's old/new
pair. Same Release binary, fresh application caches, matched requests, background
drain, retained-cache hashes and fixed source/spec hashes. No reruns, replacement
seeds, or selecting only positive cases after observing results. cn7 with existing
cn13 NVMe/TCP only. Target OS caches uncontrolled, serialized logical consumers,
no physical GPU/LLM claim. These are development results, not confirmation.

Read fill captures sequential remote bytes in bounded memory after the physical
read. It never serves this transient memory to another request. A complete capture
with unchanged inode/size/mtime/ctime is offered to the existing shared-placement
controller; incomplete or rejected capture falls back to ordinary source copying.
No early READY. Existing live quota, admission, victim-value and pin checks remain.
The background worker writes a temporary local file, hashes the captured source
bytes and independently rereads/hashes the target, rechecks source identity and
then commits. Capture allocation/copy time is included in successful measured
copy-cost samples. Rejected-capture overhead still counts in job throughput.

All three policies receive identical fill machinery. The new path changes both
source reuse and launch time (placement after complete data rather than Open);
it is a combined execution optimization, not a pure source-I/O causal experiment.
An extra shared transient payload budget of 4 MiB applies to every fill variant;
this memory is separate from the 24 MiB retained cache, must be reported, and is
not a zero-memory improvement over old variants. The pool is bounded and refuses
additional allocation. Source/fill-policy headers are not retuned by workload.

Before freezing, native tests cover capture bounds, duplicate allocation, partial
and reordered requests, EOF, source replacement, checksums/corrupt target,
capacity rejection, peer READY and all three policies. Python checks cover matrix,
configuration equality and accounting. These functional tests are not speed runs.

Primary comparisons: AdaptiveHP-fill against BOTH SIEVE-fill variants. Each must
win in both seeds, paired geometric throughput gain at least 5%, and every paired
p99 no higher. Separate engineering comparisons: each policy's fill versus old
path uses the same gates. Full old versus old SIEVE is retained. Drain-inclusive
rates, CPU, peak RSS, remote bytes, copied bytes, captured-copy bytes and staging
peak are reported. A gain common to all policies does not establish controller
novelty. No significance claim from n=2. Preserve every failed gate. Latest H/P/J
ablation and uniform/real-trace robustness still require separate verification.
