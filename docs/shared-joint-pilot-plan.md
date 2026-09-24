# Consumer-valued shared placement with hotspot adaptation: bounded pilot

New exploratory revision; preserve reports14–17. User asks to improve affinity
and joint performance, still using a small pilot and reporting gains first.
Budget fixed before timing:18 speed runs (6 arms x3 seeds), plus6 short content
checks. No expansion, post-result tuning or workload removal in this batch.

## Candidate and falsifiable contribution

The same shared copy may serve several consumer domains, but the old measured
policy values it using only the resident domain's demand. A full caller partition
also does not compare a peer partition's opportunity cost. Candidate P:

1. Value a resident/arrival using the sum of actual recent per-consumer demand,
   independent of storage location. H's existing per-consumer reset immediately
   changes this value symmetrically for both incoming and resident objects.
2. Charge the loss of shared coverage, not the loss of an individual duplicate:
   an evicted object costs zero saved-read benefit if another READY copy remains.
3. On a miss, compare feasible destinations under their ORIGINAL individual
   quotas. Choose the largest positive gain = saved read time - measured copy
   time - summed lost coverage of victims. Prefer the caller on ties. J-off
   omits victim loss from both admission and destination score.
4. Coalesce queued copies per object, recheck coverage when the job executes,
   and reuse existing verified copy/commit quota and benefit checks.

All consumers see the same physical local-disk path here. Therefore this is a
shared-storage specialization, not a model of asymmetric CUDA/NVLink costs.
The hypothesis is improved placement/retention under consumer skew and changing
hot data. It is NOT asserted to be the first collaborative or cost-aware cache.
Prior cost-driven cache/migration/replication and OmniCache already exist:
https://grc.iit.edu/publications/wang-2019-cost-driven-f3e9/
https://www.usenix.org/conference/fast24/presentation/zhang-jian
Potential paper contribution is the tested interaction of observed demand change,
marginal shared coverage and online placement under partition quotas. Novelty
still needs a detailed prior-art comparison; a faster pilot alone cannot prove it.

## Six same-binary arms

All have READY peer reads and same actual physical storage, checksums, async copy,
O_DIRECT foreground reads and total24MiB capacity, initially empty.
- Shared: simple READY sharing, H off, P off, existing victim-loss admission on.
- H: Shared plus H only.
- P: Shared plus consumer-valued placement P only.
- HP: H and P with joint victim-loss controller on.
- Independent: HP with only victim-loss accounting disabled; retain victim ranking.
- PoolSIEVE2: ordinary SIEVE with a two-hit admission filter, one shared24MiB pool
  at domain0, other quotas zero. Every caller can request/cache through that pool.
  It uses the same data path/copy queue and no private-domain read barrier.

The first five have8MiB per domain, total24MiB. PoolSIEVE2 is a strong reference
allowed to pool the whole budget, not an extra-capacity reference. All SIEVE hits
must update the actual resident partition, not the reader ID. That shared-mode
bookkeeping correction is present in the SAME binary for every arm.
P is a compound policy; this small pilot does not isolate each of its four parts.

## Input, measurement, scope

One targeted synthetic moving/shared scenario, fresh seeds2801–2803. Each run
576 requests x2MiB=1152MiB, three phases192requests each. Every four-request burst
chooses one object:85% choose a phase-specific eight-object hot set,15% a fresh
cold object; object ID changes by phase, not bytes, and no future labels reach the
policy. Consumer is80% dominant plus20% uniformly selected. Dominant consumer0
in the first two phases and1 in the last. This tests skewed consumption, sharing,
hot-set replacement and consumer movement; it is not representative production
KV inference or a negative-control/generalization study.
Block order randomized once; arm order fixed by a shuffled Latin rotation so each
arm occurs in early/middle/late positions across the three blocks. No runtime
policy gets phase labels, the seed, future keys or a synthetic latency.
Content checks:seed2799,96requests, all six arms, every request checksummed.
All speed runs validate retained copies, config, actual quota, bytes, timeline and
background completion. Freeze source/build/spec before performance.

Report actual bytes/full monotonic foreground time, with-drain sensitivity,
remote/copy/peer bytes, CPU,p99,H resets, placement/relocation counts and per-seed
paired changes. Primary pilot contrasts:HP/H (P conditional on H),HP/P (H conditional
on P),HP/Independent (joint controller),HP/PoolSIEVE2 (strong overall reference).
Also report HP/Shared, P/Shared, H/Shared and all four factorial times.
Interaction T(HP)-T(H)-T(P)+T(Shared) is descriptive; never add percentages or
claim statistically established super-additivity from three pairs.

Promising for affinity requires HP/H positive in all3 pairs with>=5% geometric
throughput gain and actual P activity. For hotspot-in-joint and controller, apply
the same direction/5% descriptive gate to HP/P and HP/Independent respectively,
and require their mechanisms to act. A strong overall claim additionally needs
HP to beat PoolSIEVE2; record a loss honestly. CPU/p99 costs and slowdowns remain.
Stop after18 regardless of outcome; no formal significance, all-workload,
GPU/inference or journal-acceptance claims. Any later wider confirmation needs
user agreement. Absence of a no-sharing control and long-run/concurrent workloads
is explicit; this pilot selects research direction, not final paper evidence.
