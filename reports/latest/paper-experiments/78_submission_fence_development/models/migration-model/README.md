# Candidate 78 parallel mechanism diagnostic

This directory contains local policy replay only. It is not server throughput or p99 evidence. No repository source or frozen experiment was changed.

The baseline uses the frozen 77 policy headers with object-weighted cohort prior, the same ten existing inputs, three four-object disk domains (24 MiB total), a two-object shared RAM cache, and fixed costs of 21 ms remote read, 10.5 ms disk hit and 8 ms copy. Copies complete instantly in this model. It preserves the original replay's cache timestamp behavior, not the entire asynchronous daemon. `build.py` reconstructs model headers from `work/hotspot-object77/capacity-boundary/native`; `run.py` retains all 360 arms and decision records. No input, seed, capacity or cost was selected after outcomes.

## Main conclusion

No newly tested H value change warrants a server experiment. A common RAM replan mechanism is implementable and reduces a few remote reads, but its apparent H advantage disappears when NoH receives the same execution opportunity. It must not be presented as H contribution.

For moving74801, the baseline Full and NoH both perform 84 remote reads and 28 copies. More strongly, all remote `(observation,key)` pairs and all admitted `(observation,key)` pairs match exactly, while destinations and victims differ. See `sequence-comparison.json` and the two arms in `baseline/moving_shared-74801.tsv`. The 12-object shared disk capacity can hold the eight hot objects of each phase. There are 67 distinct objects, so 17 repeated remote reads remain, but that upper bound does not mean those reads can all be prevented by a causal admission policy without extra useless copies.

## Mechanisms tested

| Mode | Change | Interpretation |
|---|---|---|
| baseline | Frozen77 policy and remote-only planning | Exact 40-arm reproduction |
| original_ram | Replan non-disk RAM hits for H-enabled arms | Diagnostic only: asymmetric executor opportunity |
| common_ram | Same RAM-hit opportunity for all four arms | Fair common executor candidate |
| spill | H-enabled admission delayed until a real RAM eviction | Cross-tier timing experiment; public regressions |
| conditional_ram | RAM replan plus newcomer prior conditioned on already-observed run length, using completed first-run peers | No improvement over original_ram |
| bootstrap | Stop headroom exploration after all cost classes are calibrated, all arms | Common calibration diagnostic |
| common_ram_bootstrap | Calibration stop plus common RAM replanning | Mixed; worsens H-versus-NoH public comparison |
| censored | Newcomer value trained only from objects whose full 128-request observation horizon has elapsed, counting non-RAM distinct returns | Causal H estimator; excessive copies outweigh saved reads |
| common_ram_censored | Censored estimator plus equal RAM replanning | Same copy problem |

The censored estimator does not call an event frequency a probability: it predicts a count of future disk opportunities from completed historical cohorts. Training pending labels never contribute, and observed RAM returns add zero. This fixes a plausible estimation defect but still fails because cold newcomers are hard to distinguish from one-off objects. A larger cohort forecast changes which objects displace residents and can invalidate the assumed residence opportunity.

## Selected results, with all results in tables.md

All pairs are remote reads / copies. The last column is an additive storage-cost difference, not measured wall time or throughput.

| Input | Mode | Full | NoH | Saving by Full versus NoH, ms |
|---|---|---:|---:|---:|
| moving73501 | baseline | 79 / 29 | 79 / 28 | -8 |
| moving73501 | common_ram | 76 / 28 | 76 / 28 | 0 |
| moving73502 | baseline | 83 / 28 | 85 / 28 | 21 |
| moving73502 | common_ram | 80 / 28 | 80 / 28 | 0 |
| moving73503 | baseline | 78 / 28 | 79 / 28 | 10.5 |
| moving73503 | common_ram | 76 / 28 | 76 / 28 | 0 |
| moving74801 | baseline | 84 / 28 | 84 / 28 | 0 |
| moving74801 | common_ram | 81 / 28 | 81 / 28 | 0 |
| moving74801 | spill | 83 / 28 | 84 / 28 | 10.5 |
| moving74801 | censored | 78 / 72 | 84 / 28 | -289 |
| public74802 | baseline / common_ram / censored | 967 / 33 | 1002 / 25 | 303.5 |
| public74802 | spill | 974 / 35 | 1002 / 25 | 214 |

All four moving inputs have negative net storage-cost changes under censored H. Public remains unchanged for that estimator, but existing negative public73602 is still negative. Spill harms two public inputs, so it is not a safe replacement. Common RAM replanning increases Full plan opportunities on moving74801 from 84 to 252 for only three fewer remote reads; asynchronous scheduling, metadata checks and queue overhead could exceed the 31.5 ms additive I/O saving. It is a mechanism candidate, not a performance promise.

## Concrete code explanation / possible implementation

In the repository version examined for this diagnostic:

- `src/main.cpp:1901` updates measured demand even for retained RAM hits, while `:1948` schedules immediate shared placement only for a remote tier. The completion dispatch at `:2038` and release fallback at `:2122` concern the original fill. Reusing an already-completed capture does not create a new admission opportunity. A possible common repair is to make a validated non-disk capture eligible for a new plan only when the current measured benefit can cross the normal cost gate, retaining inflight deduplication and final capacity/source validation. Apply it to Full, NoH, NoP and NoJ equally. Do not submit one background job for every RAM read.
- `src/measured_policy.h:271` admits initial free headroom under bounded calibration independently of H. Both arms therefore make the same twelve initial copies in moving74801. Stopping that exploration once calibrated saves copies but also loses useful first admissions; the combined model does not resolve the H distinction.
- `src/measured_policy.h:458` versus `:472` distinguishes static observed count from H's survival/persistent forecasts. On the principal moving input, different resident ranking chooses different domains/victims, but neither choice alters any admission time or ensuing remote read. Optimizing score arithmetic cannot by itself manufacture a disk-I/O gain when decisions already have identical service outcomes.
- `src/measured_policy.h:456` supplies cold newcomer evidence. Even replacing it with fully matured causal disk-return cohorts increases copies too much. Do not reintroduce aggressive newcomer extrapolation merely to reduce remote-read count.

## Verification and boundaries

`verification.json` records baseline reproduction and same-input accounting. `prefix-verification.json` contains 54 replay-prefix checks (216 verification arms): every decision record from truncated inputs at 127, 401 and 806 observations equals the corresponding prefix of the full run, for moving74801 and public74802 in every mode. This checks that the implementation never consumes future input records. The synthetic fixed costs and instant copies remain material limitations; no confidence intervals, real rates or tail latencies are inferred.

The existing 24 MiB primary workload must remain reported. Separate 12/18/48 MiB boundary evidence is available under `work/hotspot-object77/capacity-boundary`; favorable capacities must not replace this negative/equal main result. The present evidence supports a limited H benefit on some recurrence/pressure cases, not an unconditional gain on every moving-hotspot input.
