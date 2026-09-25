# Compact planning closeout — frozen small experiment

This is a fixed 18-run small closeout screen, not a promise of favorable data or formal significance. Source, executable and all inputs are hashed before timing. Preserve study 19 and all previous negative results unchanged.

## Changes and causal scope

The residual-reuse formula, observation window, four-request minimum half-life, copy path, checksum, per-domain capacity and joint cost formula are unchanged from study 19. This round addresses implementation overhead:

1. An opt-in compact planner uses one SQL resident snapshot across destinations, with physical-file existence, known-location and open-handle checks. It derives marginal shared coverage from actual readable copies. Each final admission still rechecks the current capacity and current value; the selected victims of THAT recheck are used directly, without a second full query/sort. Fail safely on missing or changed victim metadata. Unknown files still count in DirectoryBytes and cannot silently escape quota accounting.
2. All six policies use lean logical-read accounting. Full-WAL synchronous durability remains enabled. The selected replica's timestamp is updated in the same transaction as the logical count and GPU access order instead of committing a second transaction on peer hits. Only the unused legacy affinity classifier/event-history calculation is omitted, with configuration guards requiring immutable readers without legacy affinity or prefetch consumers. Read counts, share counts, access order, replica timestamps, policy events and content checks remain. This common engineering improvement is NOT attributed to H/P/J algorithmic novelty.

The compact planner is enabled in all five measured-policy arms. PoolSIEVE2 retains its own simpler eviction implementation but receives the same lean accounting and durability settings. H/P comparisons differ only in their respective mechanism flags; HP/Independent differs only in the joint victim-loss flag. Execution-time quotas, checksum verification, pin protection and single-copy coalescing remain.

## Fixed matrix

6 policies × 3 new paired seeds 3001–3003 = 18 speed runs. Separate correctness checks: all 6 policies, seed 2999, 96 requests with per-request SHA256. No added seeds, cherry-picked repetitions or algorithm retuning after viewing this batch. Same moving_shared generator as studies 18/19, 576 × 2 MiB = 1152 MiB per speed run. Three equal phases, changing 8-object hot sets and final caller shift, 85% hot draws, four-request bursts. Same serialized three logical domains and real cn7 → existing cn13 NVMe/TCP path. cn14 remains untouched.

First five policies have 8 MiB per domain (24 MiB total). PoolSIEVE2 has a shared 24 MiB owner cache and zero elsewhere: equal total capacity, deliberately stronger freedom from partition fragmentation. Same binary, input bytes, O_DIRECT foreground reads, asynchronous verified copy path and empty application cache for each arm. Target-side page cache remains uncontrolled. Order is shuffled then rotated so each policy appears once in early/middle/late positions.

## Endpoints and decision rules

Primary endpoint: actual bytes / full monotonic foreground wall time. Also report background-drained time, per-request p99, daemon CPU, remote read bytes, copied payload, shared placement actions, compact snapshot counts and batched replica touches.

Preserve the prior pilot screen: paired geometric throughput improvement >=5%, all 3 pairs faster, plus an active mechanism and changed executed actions. Report H/Shared, P/Shared, HP/H, HP/P, HP/Shared, HP/Independent and HP/PoolSIEVE2. The joint and strong-reference screens are separate from the overall combined gain. For the remaining tail-latency claim require HP p99 no worse than PoolSIEVE2 in every pair; report failure if not met. Three pairs cannot provide conventional two-sided statistical confirmation. Never turn a failed screen into a pass by changing its threshold after results.

Correctness covers original and compact paths, equal planning on valid resident state, multiple victims, pinned objects, real replica publication, duplicate coverage, stale/unconfigured copies, batched durable access counts/timestamps and unsupported configuration rejection. Runtime audit requires exact logical/remote/local/peer bytes, per-domain quota, correct request timelines, completed background jobs, unchanged source/config hashes and zero copy errors. Recompute all derived data from raw records. Failed runs are reported, not silently replaced.

## Interpretation

This round can finish the requested bounded run and show whether the fixes close the observed gaps. It cannot guarantee the desired performance outcome, three original research contributions, generality outside one synthetic workload family, or physical-GPU inference acceleration. If a gate fails, it remains an explicit unclosed claim rather than a reason to fabricate an ideal final table.
