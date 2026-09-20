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

The revision replaces the relative veto with an absolute domain/object demand
estimate in the SAME global observation window. Global object count times domain
share is exactly the domain/object count in that window. Effective reuse is the
minimum of this count and the existing domain history, preserving any H reset.
The same estimate feeds incoming benefit, victim ranking and summed victim loss;
copy cost and joint admission remain unchanged. Profitable minority replicas are
allowed, and traffic elsewhere ages stale affinity even while a domain is idle.
It is not physical GPU topology optimization and does not change the read route.
The legacy mode remains available for reproducibility; all new behavior is opt-in.

## Fixed comparisons and workloads

P-off and P-new differ ONLY in `measured_affinity_gate`; both track affinity and
select the new recent-demand mode. P-old enables the preserved legacy share gate.
The primary comparison is P-new/P-off. P-new/P-old is a separate repair comparison:
beating a defective old policy alone is insufficient to demonstrate affinity value.

Seven scenarios: the six prior semantic categories (static affinity, caller shift,
hot shift, coupled changes, public toolagent, uniform) plus domain re-entry.
The new scenario uses caller sequence 0,1,2,0 across four phases: a caller returns
after inactivity with a different six-object hot set under four-object capacity.
All methods receive the same trace; policy decisions never see phase labels.

Development: seeds 1701,1702, 42 actual speed runs. Correctness: 21 cases per host,
cn7 actual NVMe/TCP and cn8 directory backend. Intended development acceptance:
at least one meaningful improvement against disabled affinity, with particular
attention to re-entry, and no renewed caller-handover regression. If development
fails, preserve it and revise BEFORE freezing the held-out batch.

Confirmation is 7 scenarios × 3 variants × 12 new paired seeds 1801–1812 = 252
runs, 768 MiB of actual logical reads per run, 8 MiB per-domain quota. Public
windows are disjoint from B3 and round 3 and one another, outside the development
prefix. Caller IDs remain constructed source-request-index modulo 3; replay is
serialized storage access, not model serving. Empty application caches and random
strategy/block order are used, with the prior measured hardware/cache limitations.

Use paired geometric time ratios, 5000 paired bootstrap samples and exact
sign-flip p-values. Holm correct the seven primary comparisons together and the
seven repair comparisons separately. A confirmed benefit requires twelve pairs,
95% interval below 1, Holm p<.05 and actual new-mechanism activity. Report absolute
MiB/s, paired speed change, copied/read-remote bytes, queue-drain ratios, CPU and
per-run p99. Report all seven scenarios, including negatives and uncertain rows.
Five-percent elapsed reduction is a practical target, not a guaranteed outcome.
No significance-driven extension or policy change on the held-out confirmation.

Freeze exact source, binary, specs and public-window hashes after development and
both-host content checks. Audit every case, request/byte/source/caller count,
content check, quota, queue completion, monotonic timeline and paired statistic.
Do not combine different revisions or reuse the old formal samples as fresh tests.
