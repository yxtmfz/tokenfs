# Affinity handover context: second independent confirmation protocol

Round 14's frozen 288 runs remain a failed independent-contribution test: D repaired
legacy behavior but did not beat disabled affinity significantly. Its code, raw
records, negative development candidates, freeze and full statistics remain in
report 14 and commit d0a02dd5f086e90ca9ad4cd6ed3b12c74c8fac93. They are NOT fresh
validation for this revision. This is a new study, not a replacement of that test.

## Mechanism

The receiving domain can retain popularity from an earlier task while another
domain has already observed the transferred task. D's borrowed prediction alone
does not remove that stale incumbent advantage. Revision E adds an observed
handover epoch: a domain must return after at least max(8, affinity_window/4)
global observations of inactivity (32 at the frozen 128 window). During its first
eight observations, the established handover detector must recognize the current
object as hot elsewhere and the current caller as newly concentrated. Only then
may stale pre-activation local counts be discarded. Keep EVERY local observation
since reactivation, leave actual files/capacities unchanged, and separately count
this affinity context reset. Cold unfamiliar objects and inactivity alone cannot
trigger it. The existing H reset is unchanged and has a different metric.

Borrowed forecasts retain D's symmetric incoming/resident values, copy-cost and
summed-victim-loss checks, gradual decay and execution-time rechecks. Neither
future phase labels nor peer-domain reads, speculative prefetch, extra capacity,
artificial delays or alternative I/O paths are introduced.

P-off and P-new have exactly the same configuration except measured_affinity_gate;
both track the same epoch boundaries and forecasts. The new handover-epoch option
is true in all arms; legacy P-old retains its original relative gate and does not
apply the new demand mode. H and J remain enabled and all physical paths fixed.
The measured effect is the incremental affinity contribution conditional on H/J.

## Fixed evaluation and stopping rule

Development: 48 runs, old development-only seeds 1701/1702, all eight scenarios.
Content: 24 cases each on cn7 NVMe/TCP and cn8 directory backend. New meaningful
regressions test returning-domain reset, disabled control, and cold-no-transfer
negative cases. A fixed-cost local replay is diagnostic only, never speed evidence.
Development must show actual handover speed gain without extra copying before
freezing this candidate. Retain failures. Do not view new confirmation speed
results before the code/build/spec freeze.

Second confirmation: the same eight semantic scenarios, P-off/P-old/P-new, twelve
new seeds 1901–1912 = 288 actual runs. Each run reads 768 MiB with 8 MiB per-domain
capacity. Public trace windows are disjoint from B3, round 3, round 14, and one
another and outside the development prefix. Keep all scenarios, including null
and negative results. Empty application caches, randomized block/strategy order,
O_DIRECT foreground reads, same copy implementation and hardware limitations.

Use paired geometric time ratios, 5000 paired bootstrap draws, exact two-sided
sign-flip p-values under a symmetric-null assumption and Holm correction across
eight primary new/disabled comparisons. The eight legacy-repair comparisons are
a separate family. To account conservatively for TWO successive confirmation
attempts in this affinity optimization task, require Holm p < 0.025 per study,
95% interval below 1, all twelve pairs and actual mechanism activity before a
positive contribution claim. Round 14 has no positives even at its original .05
threshold; it is retained. Do not claim a paper-wide error bound including older
unrelated studies. No third confirmation attempt, sample extension, scenario
removal or policy tuning on this second confirmation is part of this protocol.
A 5% elapsed-time reduction remains a practical target, not a guaranteed finding.

Report real MiB/s, paired changes, intervals, copy/remote bytes, H and affinity
reset counts, forecast activity, CPU, empirical p99 and queue-drain time. Byte,
caller, source, timing, configuration, quotas and content audits must pass. Publish
one complete eight-row table, including any lack of improvement. Measurements
concern logical domains on one client disk, not physical GPU/inference performance.
