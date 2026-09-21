# Minimal-study interpretation notes

These notes correct terminology discovered during code review while the fixed
confirmation batch was running. They do not change its frozen source, binary,
samples, comparisons, stopping rule or statistical thresholds. The historical
plan and its hash remain intact. No formal aggregate results were used for these
clarifications.

## What “affinity off” actually removes

All five experimental affinity flags are false in every arm:
`measured_track_affinity`, `measured_affinity_gate`,
`measured_affinity_recent_demand`, `measured_affinity_handover_epoch`, and
`affinity_placement`. Thus the measured controller's cross-domain affinity history, weighting,
handover reset and placement decisions are disabled.

The frozen plan's phrase “all affinity tracking/decisions off” is too broad if
interpreted as removing every legacy metadata update. `TokenFS::Open` still calls
`MetadataStore::IncrementReadCount` on reads. That common path updates per-domain
access order, counts, the legacy event table and `UpdateAffinityLocked`. These
legacy statistics remain in **every** tested strategy, including RemoteOnly and
LRU. They do not enable the disabled affinity policy, but their CPU/metadata cost
is still part of the measured storage implementation. In strategies that invoke
`MeasuredPolicy::Observe`, per-domain activation/epoch bookkeeping also remains
even when affinity decisions are disabled; no zero-bookkeeping claim is made.

The valid claim is therefore “H/J without enabled affinity decisions and without
measured-controller cross-domain affinity-history tracking, on a shared TokenFS metadata path.” This
round does **not** measure a zero-affinity-metadata implementation, prove that all
affinity collection costs have been eliminated, or add independent affinity
performance evidence. Keeping this common path preserves the declared fair
within-version comparisons; removing it now would require a new runtime and new
correctness/performance study, which this task does not silently introduce.

## LRU ordering check

An initial concern about seconds-resolution `last_access_at` was resolved by
following the complete candidate path. `LocalEvictionCandidates` replaces that
field with `gpu_access.access_order`; `IncrementReadCount` assigns a monotonically
increasing sequence. Current private-domain LRU therefore sorts on observed
access order, not second-resolution wall time. No experimental correction or
rerun is required. The main change from older reports remains first-miss demand
admission instead of the older two-hit filter.

## Descriptive phase accounting

Four-phase hotspot summaries, computed after the measurements, are explicitly
descriptive. Offline phase boundaries are never supplied to the policy. The
first phase starts at the full foreground timer, intermediate phases start at
the previous phase's final completion, and the last phase includes the remaining
foreground tail. The four byte counts and elapsed times must sum to the complete
run. These summaries neither create extra independent samples nor change the
predeclared confirmatory verdicts.
