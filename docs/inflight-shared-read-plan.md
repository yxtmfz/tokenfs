# In-flight immutable read sharing: diagnostic and bounded pilot

First replay the prior failing moving_shared seed 3241 once with AdaptiveHP and
PoolSIEVE1, same source/binary and inputs, optional monotonic request/copy trace.
These two diagnostic runs are not speed confirmation and do not replace report25.
Measure same-object remote reads selected while a completed capture is being
materialized. Overlap alone is not a causal effect; no waiting benefit assumed.

A candidate may reuse completed immutable read capture for concurrent consumers,
strictly while the same object's background placement is in flight. Never expose
partial data or publish disk READY early. Preserve source identity, capture budget,
source-change fallback, disk checksums and commit/pin/quota safety. Count memory
reads separately, pin the capture until handle release, and do not mistake these
for local-disk reads or bandwidth. Expose the same capability to SIEVE comparators.

Then freeze at most twelve speed runs before execution: old AdaptiveHP, candidate
HP, SIEVE1+candidate mechanism, SIEVE2+candidate mechanism on the known regression
seed, one new hotspot seed, and one new uniform seed. The two HP configurations
must differ by one switch; no incremental_copy_cost candidate from report26.
Same total retained storage and transient RAM cap for all arms. Detailed trace
OFF in speed runs. No reruns, seed replacement, large-scale run, or threshold
retuning. Report every outcome and remaining limits, including fairness of RAM
capacity and the absence of physical GPU/LLM inference or latest H/P/J closure.
