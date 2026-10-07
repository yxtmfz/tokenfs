# Read-only review: repeated measured-policy calculations after candidate80

Conclusion: **a small, exact-output optimization inside one `PlanImpl` call is
plausible, but it is not a demonstrated next bottleneck or a way to establish H's
I/O benefit. Do not introduce it while candidate80 is being measured.** Reuse of
values between the current separate `PlaceShared` domain calls is not automatically
output-equivalent: those calls can observe different history and cost snapshots.

This review reads candidate80 source and existing frozen79 JSON only. It does not
change production code, build a policy candidate, access a server, or start a
performance run. `evidence.json` identifies the source and all input files.
`python3 work/hotspot-index80/planning-cost-review/analyze.py` reproduces the
20 descriptive rows from the four frozen79 cases and five measured/control arms.

## Where there is genuine repeated work

Source locations are in `src/measured_policy.h` at the recorded hash.

- `PlanImpl` lines 242–313 holds `mu_` for its entire call. `Observe`, `ReadSample`
  and `CopySample` cannot mutate its inputs during that interval.
- Lines 249–261 calculate effective count, survival and persistent/recent values
  for diagnostics. Later admission (277), scoring (458–481), victim value and
  uncertainty (293–294), and incoming value (297) repeat some of those pure
  calculations.
- `Survival` (393–413) can traverse recent positions to compute between-run gaps
  and then evaluate `exp2`; `PersistentEstimate` (437–442) can perform run-history
  lookup, square root and `exp2`. `CohortDiskReuse` (451–456) can evaluate a
  separate newcomer survival. Memoizing the exact result within one lock can
  avoid repeated work without modifying the estimators.
- The large sort-comparison duplication is **already fixed**: with
  `efficient_planning && value_victim`, `Sort` (484–500) evaluates `Value` once
  per resident and sorts stored scores. Frozen79 measured arms enable this flag.
  The remaining duplicate is that selected victims are evaluated again at
  line 293 and their effective counts are re-read for uncertainty.
- `PersistentEstimate` and other run-history helpers are O(1) bounded summary
  lookups; they do not replay the entire trace. The burst-interval survival scan
  is bounded by the request window (128 in the experiment). The experiment has
  at most four 2 MiB SSD objects per logical domain, twelve total, before pins
  and protected objects are removed. An expensive general-purpose cache would
  be disproportionate to these small per-plan vectors.

For the current dynamic-H retained-capture path, after diagnostics and scoring
are reached, the following are **source-level evaluation counts**, not measured
CPU instructions. Compiler inlining, early returns and missing history can make
many of them cheap.

| Item in a non-early-return plan | EffectiveCount | Survival | PersistentEstimate | Full Value |
| --- | ---: | ---: | ---: | ---: |
| Incoming | 3 | 3 | 2, plus at most 1 admission check | 1 |
| Resident ranked but not selected | 3 | 3 | 2 | 1 |
| Selected victim | 5 | 4 | 3 | 2 |

Incoming `CohortDiskReuse` may be evaluated once for the result and again inside
`Value`. A pure per-item facts object could reduce repeated component evaluations
to one, and retaining the already computed raw resident `Value` would avoid the
second full estimate for selected victims. This is a constant-factor reduction,
not an asymptotic breakthrough over the currently enabled efficient sorter.
NoHotspot's static branch is much cheaper already and must keep that property.

## Safest possible implementation boundary, if later justified

The smallest useful step would extend the existing scored resident representation
with its **raw value**, retaining it through sort and victim selection. Use the
raw value directly for displacement; do not recover it by multiplying the
normalized sort score back by size. Division followed by multiplication can alter
floating-point values and threshold decisions.

A broader but still local step would give the incoming item and each resident a
lazy evaluation record owned by that one `PlanImpl` invocation. Reuse the exact
results of EffectiveCount, Survival, PersistentEstimate, RecentValue, cohort,
burst and Value as their existing branches request them. Avoid a persistent
unordered-map cache: it adds allocation/hash costs and invalidation complexity
for four or fewer resident items. Reuse the existing scored vector where possible.

Required semantic details:

1. Cache context includes `gpu`, all Options, the incoming/resident role, key,
   bytes and coverage. The current EffectiveCount ignores its role argument,
   but an implementation should not silently discard the API distinction.
   `Value` is not a key-only property: duplicate keys with different sizes or
   coverage need different values. Per-input-item records naturally preserve
   these distinctions and the existing per-item diagnostic multiplicity.
2. Count diagnostics remain separate from shared effective frequency: even in
   shared causal mode, `incoming_count` and `affinity_adjusted_items` compare
   domain-local Count. A shared incoming value is not a whole shared Decision.
3. All Decision fields, reasons, early-return states, victim order and the order
   of floating-point additions stay unchanged. Diagnostics currently include
   all input residents before admission, even when no victim is later needed.
   Reusing calculations must not drop those counters.
4. The static branch still skips dynamic survival/persistent diagnostics. However,
   its no-reuse admission condition can still call `PersistentEstimate`; do not
   replace that with zero merely because `static_reuse_value` is enabled.
5. The disk-opportunity branch uses `DiskOpportunity / DiskReuseScale` for its
   persistent diagnostic and a separate direct opportunity value in Value.
   Algebraically cancelling or reordering these operations is not guaranteed
   bit-identical. Cache the primitive result, then retain each original arithmetic
   expression if supporting this option.
6. Cache lazy values rather than eagerly calculating every estimator. Headroom,
   no-reuse, pinned-capacity, static, LRU-victim and admission-disabled paths have
   different needs. Eager dynamic evaluation could slow precisely the cold and
   static baselines the change is intended to help.
7. `Ranked` is a separate lock-scoped API. Its own efficient sorter already needs
   only a Value per item; it should not start computing Plan-only diagnostics.
8. Preserve score division and score/recency/key tie-breaking. No reassociation,
   cheaper approximate exponentials, altered thresholds or compile-time fast-math.

Within that boundary, reuse is compatible in principle with all existing options:
causal and legacy windows, shared and domain-local counts, recent-demand affinity,
aging/reset, static H, value/LRU victims, size-awareness, joint/independent
admission, cost on/off, retained and unretained capture, burst survival, immediate
persistent decay, newcomer priors and disk opportunity. Some yield no reuse
benefit. A simpler first step can deliberately cover only the existing efficient
value-victim sort while preserving the unchanged fallback for other options.

## Why three-domain reuse is a different proposition

`PlaceShared` in `src/main.cpp` calls `PotentiallyProfitable` once per allowed
domain at lines 3089–3094, then `MeasuredPlan` at 3110; each enters and leaves the
policy mutex independently. The layout mutex does **not** freeze policy history
or measured rates. Foreground Observe and ReadSample can run between these calls;
adaptive placement also explicitly releases the layout mutex before the later
Plan loop. Final `EnsureLocalCapacity` performs another live Plan before eviction.

Therefore neither reusing the first domain's value nor moving the whole loop
under one large policy lock is an exact implementation replacement for the
current sequence. The former can use stale data; the latter changes which
observations are visible and delays foreground work. Removing the final recheck
would be incorrect.

For a fixed single snapshot with shared causal options and affinity gate off,
common incoming value, copy cost and incoming uncertainty can be shared across
locations; permitted capacity/headroom and resident losses remain distinct.
`NoAffinity` still permits only its caller. `NoJoint` does not acquire Full's
victim/noise charge. General options with domain-local effective counts or the
legacy affinity rejection are location-dependent. Even under the narrow common
bound, domain-local diagnostic counts prevent reuse of the complete Decision.

A future version-checked reuse scheme could preserve each existing lock's
linearization point: increment a generation on every history/rate mutation,
reuse only after checking the same generation and context under the next lock,
and otherwise recompute. That adds updates to hot foreground paths, invalidation
and option-fingerprint tests, and still saves only a few calls. It is not the
minimal follow-up and is not recommended without evidence of material cost.

All exact-output claims here are conditional on the same observation/sample order.
Faster execution can change real concurrent interleavings and online cost samples;
therefore algorithmic equivalence alone does not promise identical measured I/O
counts or final speed, as the prior runtime diagnosis already showed.

## Existing data bound the expectation, not a predicted speedup

The following are frozen79 Full, before candidate80's indexes. They are included
as stage-cost envelopes, not mixed with candidate80 results.

| Case | Full wall + drain (s) | Entire foreground precheck (ms) | Fraction of wall | Successful copy capacity/planning wrapper (ms) | Shared selector Plan calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| moving r1 | 6.570772 | 12.352 | 0.188% | 29.519 | 60 |
| moving r2 | 6.597865 | 12.912 | 0.196% | 30.935 | 60 |
| public r1 | 26.395006 | 223.943 | 0.848% | 25.218 | 219 |
| public r2 | 25.991969 | 217.377 | 0.836% | 48.807 | 186 |

Policy memoization affects only a subset of the precheck, which also contains
SQLite, path validation, locks, allocation and telemetry. Even erasing that whole
recorded foreground segment would remove only the listed service time; the
proposed reuse cannot achieve that. Candidate80 specifically removes a dominant
scan from that same stage, so its new profile must not be inferred from79.
The copy planning counter also includes directory/metadata/snapshot work, not
just Value, and is recorded only for successful capacity checks. Selector Plan
counts are not all PlanImpl calls (prechecks and final checks are additional).

The frozen speed runs have profile_control_path=false and do not isolate
PlanImpl CPU or mutex hold/wait time. Even when enabled, the current shared-plan
latency counter omits early rejected tasks. Thus there is **no honest numerical
whole-run or p99 upper bound for this proposal** from existing counters. The
stage numbers show why an expected several-percent guaranteed speedup would be
unsupported. The plausible target is a small constant CPU/lock-hold reduction;
it cannot by itself create fewer SSD/remote accesses for an equal policy snapshot.

## Minimal tests and decision gate

If candidate80 results and existing offline diagnosis later justify another
implementation, begin with one lock-local change and a local exact differential
test, not a new server workload or concurrent second candidate.

- Compare the old and new headers on identical fixed prefixes and sample updates;
  assert every Decision field exactly, including persistent_reuse_adjusted_items,
  exploration_reads and cohort_disk_reuse. The existing
  `tests/planning_equivalence_test.cpp::equal` omits those three fields and needs
  extension for such a change. Assert full victims and Ranked item tuples, not
  just allowed or order of key names.
- Exercise cold/partial/full cost calibration, remote savings zero, windows
  2/8/128 and live window changes, burst and irregular gaps, disappeared/reappeared
  keys, all relevant option combinations, static H and original P/J ablations.
- Test incoming key also present among residents; duplicate keys with different
  bytes/coverage, zero-size items, coverage 0/0.5/1, exact score/recency ties,
  oversized input, headroom, full/pinned/overquota capacity, no-reuse rejection,
  disabled admission/cost, both optimistic and full plans.
- Ensure repeated calls without mutation return exactly the same outputs and
  history/rate updates between calls are visible. Do not reuse context across
  calls or strengthen lock duration by accident. Run ASan/UBSan and existing
  native policy tests. A local fixed-prefix helper-call/count diagnostic can
  confirm less work, but is not a real throughput result.
- Retain the same baseline code path and options; static H must not be forced
  through expensive dynamic computations. Any eventual real comparison must
  include all intended arms and full-run throughput/p99, not planner microseconds
  reported as the paper's performance gain.

Recommendation now: finish candidate80 first. If its common implementation cost
improves but H is still weak with equal I/O, treat that as an H evidence limitation,
not a reason to assume this small memoization will solve the gap. Keep cross-domain
snapshot redesign out of the current closure work.
