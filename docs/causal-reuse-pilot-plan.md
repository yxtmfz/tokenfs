# Causal reuse pilot — frozen before timing

This is a development experiment, not confirmation or a claim of priority.
Previous studies remain immutable. No post-hoc exclusions or seed replacement.

## Hypothesis and implementation

The old controller summed each consumer's last 128 accesses, whose real time spans differ. It valued long-past benefits as future victim losses. The new opt-in `measured_causal_window` collects a single 128-request global window for all measured arms. P uses all consumers in that window; without P, only the requesting domain's events inside that same window count. Idle consumers therefore expire without needing their next access.

Within this experimental mode H replaces the legacy missed-run reset with an overdue-reuse forecast. For an object with n >= 2 observations, mean observed gap is (last-first)/(n-1); h=max(4,gap), in global request units. Its residual evidence is max(n-1,0) * 2^(-age/h). H-off has survival factor 1. The 4-request floor is an explicit heuristic, fixed before this experiment; sensitivity is NOT validated. There is no phase, seed, future request, or synthetic service delay in the controller. The exact same value applies to arrivals and residents; only observed recency differs.

P retains shared marginal coverage valuation, bounded per-domain destination selection, and in-flight duplicate suppression. J charges the sum of lost residual shared benefits along with measured copy cost. The independent arm disables only the victim-loss charge, including its destination score. Same victim ordering, data checks, and quota protection remain.

Two exact planning optimizations are enabled for all new measured arms: reject an incoming object before scanning residents if even free space cannot repay its copy; stop searching destinations after zero charged victim loss reaches the upper bound. This upper bound is valid only for this implementation's location-independent I/O cost estimate on a shared-host backend. Future heterogeneous per-link costs must change that bound.

Novelty is a hypothesis about integrating consumer-clock alignment, residual shared coverage and admission/placement, not a claim that exponential aging or shared caching is new. Existing cost-driven collaborative caching and distributed KV reuse preclude such a broad claim. No theoretical optimality is asserted.

## Fixed small matrix and controls

Exactly 18 speed runs: Shared, H, P, HP, Independent, PoolSIEVE2; three new seeds 2901–2903. Same moving_shared generator as study 18: 576 requests, 2 MiB each, 3 equal phases, 8 hot objects per phase, 85% hot draws, four-request bursts, predominant caller changes on the final phase. Six shorter content checks use seed 2899 and 96 requests. Algorithm and all seeds are frozen before any speed result. No scale expansion.

All policies run the same Release binary. Each paired trace, foreground O_DIRECT, remote source, copy/checksum implementation and total 24 MiB capacity are identical. First five arms keep 8 MiB per partition. PoolSIEVE2 has 24 MiB on the canonical owner and zero elsewhere; it is a strong equal-total-capacity reference, not a one-field per-domain ablation. Same old simple baseline, not intentionally slowed. Empty application cache, serialized callers, existing cn7 to cn13 NVMe/TCP. Target page cache is not controlled. No cn14 access, no disk configuration change.

H/P four-cell comparisons differ by one flag. HP/Independent differs by the joint-admission flag. Report all seven paired comparisons from study 18. The within-current-round comparisons are causal ablations of these switches; comparisons to prior study means are not matched measurements.

## Endpoint and small-pilot gate

Primary: actual logical bytes / complete monotonic foreground wall time (MiB/s). Also report wall with background drain, remote bytes, copied payload, daemon CPU, p99, plans, residual discounts, placement and relocation. A promising component contrast requires all three paired gains positive and geometric mean throughput gain >=5%, plus active mechanism and changed executed actions. This is not statistical confirmation. H standalone, P standalone, H conditional on P, P conditional on H, J versus Independent, HP versus Shared and HP versus PoolSIEVE2 all remain visible, even if negative. An all-components success requires the component gates and strong-reference gate; otherwise state which did not pass.

Source/binary/config hashes, all request rows and policy actions, checksums, quota/byte accounting, drain completion, and a separate offline arithmetic recomputation are required. Do not use functional-check timings as performance evidence. On positive evidence report it before proposing any larger study; on failure retain the result and state the remaining issue.

## Scope

Three logical cache partitions, no usable CUDA GPUs. This measures real storage I/O and controller overhead, not GPU inference or inter-GPU transfer. Shared copies and pooled capacity have no intrinsic topology advantage here. This single targeted trace family cannot establish production generality, publication novelty, or improvement on every workload.
