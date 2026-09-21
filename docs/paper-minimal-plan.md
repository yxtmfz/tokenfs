# Minimal storage-paper closeout, 2026-09-21

This is a new, narrower H/J study requested after the affinity work. It neither
extends the failed affinity confirmation nor retunes the H/J algorithm. Reports
12–15 remain historical, revision-specific evidence. No physical GPU or LLM
inference contribution will be inferred from these storage replays.

## Questions and fixed scope

1. Does H+J without affinity outperform reasonable cache baselines on real I/O?
2. Does H help hotspot changes, and does J help hotspot changes/public replay?
3. Do the measured gains pay the copying/control cost, and where do they fail?

Four main scenes are selected BEFORE new measurements: stable affinity (previous
overall weakness), hotspot changes (intended target), public tool-agent trace
(external validity), uniform random (negative control). Prior caller-shift and
handover affinity failures remain explicitly reported; their omission from this
new H/J-only matrix does not turn them into successes.

Six main arms: RemoteOnly, demand-on-first-miss LRU, SIEVE, SIEVE plus domain-local
two-hit admission, RecentLFU, Full (H+J, all affinity tracking/decisions off).
The original LRU reference required two hits; this round clearly relabels LRU as
ordinary demand admission. SIEVE follows the insertion queue, visited bit and
persistent hand in the NSDI 2024 paper. It shares TokenFS's asynchronous verified
copy and capacity checks; this is a policy adapter, not the original optimized
lock-free application. Pinned files are skipped. Empty caches are required;
persisted SIEVE queue recovery is not claimed. The extra two-hit arm prevents
confusing all of the gain with rejection of first-time objects.

Source: https://www.usenix.org/conference/nsdi24/presentation/zhang-yazhuo
Algorithm: https://cachemon.github.io/SIEVE-website/blog/2023/12/17/sieve-is-simpler-than-lru/

At hotspot changes also run no-H, no-J, no-HJ. At public replay also run no-J.
H/J toggles differ in exactly one configuration field. Other common measured
history, cost estimation, victim ranking, copies and constraints remain enabled.
no-J only removes victim loss from admission; it is a component ablation, NOT an
established external competitor. A favorable comparison is not proof of novelty.

## Size and execution

- 4 scenes × 6 main arms × 12 paired seeds + 4 targeted ablation arms × 12 =
  **336 formal runs** (42% fewer than rerunning the previous 576-run matrix).
- 28 content cases per host (cn7 real storage, cn8 directory backend); 28 small
  development/preflight speed runs. No policy tuning based on their speed.
- 12 fixed sensitivity runs: hot shift at quota 16 MiB and at 1536 requests,
  Full versus RecentLFU, 3 new seeds each. Descriptive only, not confirmatory.
- Main seeds 2101–2112; 768 MiB logical read bytes/run, 8 MiB/domain; 3 logical
  private domains on one client/disk. No claim of independent GPU topology.
- Public 12 windows disjoint from B3, round 3, affinity D/E and one another;
  preserve identities/order and source timestamps, normalize object bytes,
  caller = source request index modulo 3. This is a trace proxy, not inference.
- Randomized block and arm order; empty application cache each time; two-layer
  direct foreground I/O, existing buffered verified copying. Remote NVMe/TCP
  namespace targets cn13; do not use cn14 or alter shared storage setup.
- Before formal execution, freeze source, Release binary, specs, public windows,
  content references and this plan. No outcome-based sample additions, scene
  deletions, parameter changes or repeat-until-significant confirmation.

## Analysis and stopping

Primary metric: actual logical MiB divided by full foreground monotonic elapsed
time. Report mean rates, paired geometric elapsed ratios, bootstrap 95% intervals
(5000 resamples), exact paired log-ratio sign-flip p-values and Holm corrections.
Primary overall family: Full versus four cache references in all four scenes
(16 tests). Mechanism family: H at hot shift, J at hot shift/public (3 tests).
RemoteOnly references are a separate diagnostic family (4 tests). Alpha .05 in
each declared family; intervals are unadjusted. This does not claim global error
control across the prior adaptive research process or across the whole paper.
Require 12 complete pairs and actual mechanism/action differences for component
attribution. A 5% elapsed reduction is a practical reference, not a guarantee or
a publication threshold. Report failures and uncertain effects unchanged.

Also report user-space background drain, copied/remote logical bytes, CPU/RSS and
per-run empirical p99. Queue drain is not physical persistence; logical copy bytes
are not physical network/write amplification. Main synthetic runs are short;
the longer sensitivity is a limited check, not a full endurance study. Shared
target cache and unrelated workloads are not fully isolated.

H×J interaction in hot shift is exploratory. We make no super-additivity claim.
Prior mechanism and affinity numbers are not added to this round's gains. If
Full cannot outperform external references, close the evidence honestly and
narrow or reject the performance claim instead of changing the winner criterion.

## Verification

SIEVE unit tests independently match an array reference over 80,000 accesses;
real metadata tests exercise verified owner/replica insertion and eviction.
Content verification remains outside speed samples. Independent offline audit
must check source/build/spec hashes, complete traces/bytes/configuration/quotas,
public-window origin, same-client monotonic timing, copying completion, statistics,
and rejection of deliberately corrupted copies of evidence.

Deliver one report with overall rates, H/J ablations, overhead/sensitivity and a
claim-to-evidence ledger. This closes the scoped storage experiment; it does not
prove paper novelty, journal acceptance, physical GPU gains or real inference.
