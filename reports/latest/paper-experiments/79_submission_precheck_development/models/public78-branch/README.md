# Frozen 78 public branch decomposition

Read-only local analysis of `hotspot-submission78/evidence/development`. This uses frozen **78** policy headers copied from `audit-source`; it does not use the current **79** prefilter implementation. No server run or repository edit was performed. Input hashes and header identity are recorded in `analysis.json` / `source-identity.json`.

## What the raw records establish

| Arm | Round | Remote reads | SHARED_PLACE | ADMIT | Completed READY actions |
|---|---:|---:|---:|---:|---:|
| Full | 1 | 967 | 33 | 33 | 33 |
| Full | 2 | 997 | 36 | 25 | 25 |
| SyncSubmission | 1 | 997 | 23 | 23 | 23 |
| SyncSubmission | 2 | 967 | 33 | 33 | 33 |

Full r2 has 11 `measured_commit_victim_loss` and 11 `cross_gpu_replica_skip_no_space` events. Its 25 ADMITs correspond to 8 PROMOTE_READY plus 17 REPLICATE_READY, so the current collected data does **not** show two missing completed copies. The 23 completed copies belong to SyncSubmission r1.

Before request index 60 (zero-based), the only repeated object is key 7 at index 34; it was included in initial capacity exploration. Keys 45 and 46 occur first at indices 46/47 and again at 60/61, giving a 14-observation return gap. Their first full-cost H decisions therefore occur when local-read calibration plausibly still rests on only that first local reuse. The response of index 34 is 21.408 ms (Full r1), 23.408 ms (Full r2), 25.679 ms (Sync r1), and 21.659 ms (Sync r2). These are client responses, **not** the internal read-cost samples, so they cannot identify the local cost estimator by themselves.

## Separating forecast from cost

At the second visit, original78 `RunReuse` gives `128/14 × 1/2 = 4.57142857` predicted opportunities. All adjacent requests differ, so the temporal strength is zero, the retained-capture disk scale is one, cohort value is zero for a recurring key, and the recent frequency value is only one. Persistent reuse therefore wins the max. Its immediate-decay setting multiplies the estimate by `2^(-1/14)` after one subsequent observation, producing **4.35060641**. A single count-one victim plus count-two incoming object gives uncertainty coefficient `1 + sqrt(2) = 2.41421356`.

The independent `forecast_components.cpp` replay uses artificial unit cost **only to isolate these dimensionless terms**, and reproduces the exact coefficients from frozen78. It is not speed evidence.

| Observed first count-two ADMIT | Incoming, µs | Uncertainty, µs | Inferred saving per 2 MiB object, µs | Incoming / inferred saving |
|---|---:|---:|---:|---:|
| Full r1, key45 | 17,905.4 | 9,935.97 | 4,115.614 | 4.350603 |
| Full r2, key46 | 12,520.5 | 6,947.82 | 2,877.881 | 4.350596 |
| Sync r2, key45 | 17,296.8 | 9,598.24 | 3,975.721 | 4.350607 |

Printed fields have limited precision. Within that precision, the H forecast factors are identical, while Full's inferred `SavingRate × bytes` differs by approximately **30.07%**. This is stronger than saying the incoming value merely changed: its change can be separated algebraically from recurrence and temporal strength at these observed decisions. It still does not reveal how much came from remote EWMA, local EWMA, or their sampling order.

## A one-observation selection-to-commit boundary

For early accepted keys in Full r1 and Sync r2, SHARED_PLACE incoming becomes ADMIT incoming multiplied by `2^(-1/14)`, while copy cost and uncertainty stay unchanged. This is consistent with the next Open advancing global demand once between preliminary selection and the final capacity/benefit recheck. The code intentionally rechecks current evidence in `EnsureLocalCapacity`; the `persistent_reuse_immediate_decay` estimate ages on every logical observation.

Full r2 key45 has a SHARED_PLACE margin of only **+607.268 µs**. Holding the other printed fields fixed, one observation of H decay costs **617.215 µs**, making the margin approximately **−9.947 µs**. It has no ensuing ADMIT at that occurrence. Key46's analogous predicted margin is **+150.377 µs**, closely matching its actual ADMIT score **+150.375926 µs**. The following keys' hypothetical one-observation margins are also negative. Together with the 11 commit rejections, this is strong evidence of sensitivity at the final recheck.

The log does not record rejected decisions' full fields, observation clock, request ID or timestamp. Thus the negative key45 calculation remains a clearly labelled counterfactual, not an exact reconstruction of its rejection. Nor can the +30 remote-read difference be assigned to cost sampling alone: asynchronous execution, changed early admissions, later residence/copy decisions and subsequent cost samples form a feedback loop.

## What is still unidentified

- Individual early local/remote request-cost samples, their exact sample counts, EWMA means and update order at the first branch.
- The precise request observation and rates at each rejected final decision; aggregate `request_cost_*` totals cannot reconstruct them.
- A lower-level cause for a slower sample (storage, network, scheduling, allocation, or overlapping work). Client response time includes additional work and is not a replacement for internal samples.
- Whether forcing the same rates would eliminate the full-run branch difference. That requires a faithful event-order replay; there is insufficient timing/state in current logs.
- Whether a proposed modification improves speed or p99. No threshold, input, capacity or estimator parameter was changed in this diagnostic.

## Smallest additional diagnostic, if 79 remains ambiguous

Do not retune the estimator or disable its final recheck. Prefer a diagnostic-only bounded decision/sample ring buffer, dumped after shutdown, on one fixed public Full/Sync pair with unchanged workload/configuration. Record all preliminary and final decisions, including rejects: key, global observation index, request/read sample sequence, selected domain, reason, recent/persistent/cohort/temporal/disk-scale components, cost means and sample counts, incoming/victim uncertainty, copy cost and victim keys. Record raw `RequestReadCost` samples with their tier/bytes/µs and update sequence; capture cost samples similarly. This allows an offline replay to hold either sample values or observation order fixed as separate counterfactuals.

Logging should avoid per-event SQLite transactions and should have an explicit overflow counter. The diagnostic run must not be merged into the performance table. First inspect all existing 79 outcomes; this proposal does not authorize or start a new server run. If its bounded history answers the early branch, no broad sweep or new seed set is needed.

Current 79 changes only submission timing through the prefilter. Even if it changes the outcome, that does not by itself prove or repair an H estimation defect.

## Frozen diagnostic provenance

This artifact was prepared after frozen78 completed and while candidate79 measurements were running/being collected; it does not use candidate79 performance outcomes. It is diagnostic/development evidence, not a new performance validation run. The first physical copies arose from the original bounded capacity warmup; subsequent early resident reuse supplies the first local cost samples, so both first-copy selection and completion timing can affect later online estimates. The current raw records cannot uniquely separate online cost sampling from asynchronous scheduling effects. The RAM replay uses fixed costs and immediate copies and cannot answer that timing question.
