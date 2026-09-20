# Affinity demand revision: diagnostic and held-out speed study

This study concerns affinity alone. H (fast hotspot adaptation), J (joint copy
and victim-loss admission), private routing, quotas, copying, direct foreground
I/O, queues and trace identities stay fixed in all arms. The old round-3 evidence
is retained and is diagnostic training material, not the new test set.

## Failure and revision

The old relative share gate (`own * 2 >= peak`) has no economic justification:
a profitable minority caller can be rejected simply because another domain used
the object more often. After caller handover, the old domain stays dominant in
the 128-event global history. Meanwhile the base value estimate uses 128 accesses
PER DOMAIN: it stops aging during inactivity and can overvalue obsolete residents.

The initial common-window count revision was tested only on the development set
and was rejected: gains were small and uniform/public results regressed. Its 42
runs and per-host correctness checks are retained separately as development A.
At that development checkpoint there had been no held-out confirmation access.

The second development candidate borrowed demand for incoming objects only. In
the additional handover case it was 7.05% slower than disabled affinity and copied
116 versus 64 MiB per run: newly admitted replicas immediately became cheap
victims under their smaller local counts. All 48 development runs and 48 content
checks of this candidate B are retained. No confirmation was run.

Candidate C made incoming and resident estimates symmetric but still regressed
by 2.28% in handover (70 versus 65 MiB copied). The detector stopped borrowing
abruptly as local share caught up, causing another value discontinuity. Its
48 development and 48 content checks are retained; no confirmation was run.

The final candidate D replaces the relative veto with **handover-aware reuse
transfer** consistently for incoming and resident objects. In the last four observed accesses, the
current domain must account for at least three and have at least twice its share
in the long 128-event window. The object must have at least eight observations
in that long window, with other-domain count at least twice the current domain's
count. Only then may incoming reuse borrow global object demand multiplied by
the newly observed destination share. Use the maximum of this estimate and the
original local estimate. Apply the same forecast to the incoming object and eligible residents, avoiding
the valuation discontinuity seen in B. Objects removed from domain history by
aging or hotspot reset cannot be resurrected by global evidence. Copy cost, summed victim loss,
Borrowed forecasts now decay linearly over one global affinity window instead of
disappearing when the short-window detector turns off. They are refreshed only
by observed handover evidence, erased when local history removes the object, and
ignored after expiry. P-off tracks the same forecasts but does not apply them.
Capacity and execution-time rechecks remain unchanged. No speculative prefetch:
only the object actually requested is eligible. No workload phase labels or
future requests enter this decision.

Without a prior unexpired handover forecast, stationary, balanced and single-domain access retain the baseline estimate.
Profitable minority readers no longer face a relative-popularity veto. This does
not solve every idle-domain history issue; the domain re-entry case remains as a
boundary check. The legacy share gate remains available. Behavior is opt-in and
the same recent-demand option selects this final implementation in the new binary.

## Fixed comparisons and workloads

P-off and P-new differ ONLY in `measured_affinity_gate`; both track affinity and
select the new recent-demand mode. P-old enables the preserved legacy share gate.
The primary comparison is P-new/P-off. P-new/P-old is a separate repair comparison:
beating a defective old policy alone is insufficient to demonstrate affinity value.

Eight scenarios: the six prior semantic categories (static affinity, caller shift,
hot shift, coupled changes, public toolagent, uniform) plus domain re-entry and affinity handover under cache pressure.
The new scenario uses caller sequence 0,1,2,0 across four phases: a caller returns
after inactivity with a different six-object hot set under four-object capacity.
A separate handover scenario adds eight phases in four pairs: each pair retains a four-object hot set while the caller changes, and later destinations already have a different resident set. This fills a coverage gap: re-entry with entirely new objects cannot test reuse transfer. It was added during development BEFORE any confirmation access; all seven existing scenarios remain. All methods receive the same trace; policy decisions never see phase labels.

Final-candidate development D: seeds 1701,1702, 48 speed runs in one batch,
separate from rejected A, B and C using the same development-only traces. Correctness: 24 cases per host,
cn7 actual NVMe/TCP and cn8 directory backend. Intended development acceptance:
at least one meaningful improvement against disabled affinity, with particular
attention to re-entry, and no renewed caller-handover regression. If development
fails, preserve it and revise BEFORE freezing the held-out batch.

Confirmation is 8 scenarios × 3 variants × 12 new paired seeds 1801–1812 = 288
runs, 768 MiB of actual logical reads per run, 8 MiB per-domain quota. Public
windows are disjoint from B3 and round 3 and one another, outside the development
prefix. Caller IDs remain constructed source-request-index modulo 3; replay is
serialized storage access, not model serving. Empty application caches and random
strategy/block order are used, with the prior measured hardware/cache limitations.

Use paired geometric time ratios, 5000 paired bootstrap samples and exact
sign-flip p-values. Holm correct the eight primary comparisons together and the
eight repair comparisons separately. A confirmed benefit requires twelve pairs,
95% interval below 1, Holm p<.05 and actual new-mechanism activity. Report absolute
MiB/s, paired speed change, copied/read-remote bytes, queue-drain ratios, CPU and
per-run p99. Report all eight scenarios, including negatives and uncertain rows.
Five-percent elapsed reduction is a practical target, not a guaranteed outcome.
No significance-driven extension or policy change on the held-out confirmation.

Freeze exact source, binary, specs and public-window hashes after development and
both-host content checks. Audit every case, request/byte/source/caller count,
content check, quota, queue completion, monotonic timeline and paired statistic.
Do not combine different revisions or reuse the old formal samples as fresh tests.

## Completed confirmation

All 288 frozen runs and 48 content checks passed the independent evidence audit.
No primary new/disabled comparison met the predefined significance rule. Caller
shift was +0.84% and handover -0.90%; these are uncertain point estimates, not
confirmed gains. The legacy repair was supported in caller shift and handover.
Do not use this batch to claim an independent affinity speed contribution or
retune and relabel the same samples. Results: report 14_affinity_refinement.
