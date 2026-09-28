# Adaptive reuse control — fixed development experiment, 2026-09-28

Study21 improved throughput versus SIEVE-2hit by 5.12% but remained -0.28% versus SIEVE-1hit, approximately -4.8% under uniform access, and worsened moving-workload p99. These failures remain in the evidence tree. This round tests algorithm changes, not a promise that every gate will pass.

## Changes fixed before timing

`adaptive_reuse_control`, default off, requires immutable compact burst-aware joint admission.

1. Bounded free-headroom exploration: copy on a first access when enough physical free space exists, with no eviction, unless the measured verified-copy rate exceeds the measured remote-read rate. Unknown copy cost allows cold-start exploration. This is a deliberately bounded exploration exception to positive predicted net benefit, not a claim of proven future reuse. It stops at capacity and cannot bypass pin/unknown-file accounting.
2. Observation-based temporal strength: over the existing global 128-observation window let a be adjacent equal-key probability, c=sum(n_k(n_k-1))/(N(N-1)). With N>=8 and c<1 set strength=clamp(4(a-c)/(1-c),0,1), otherwise 0. Multiply the old survival-decay exponent by strength. No workload labels, phase markers or future requests are visible. IID-like gaps do not imply that residents lose value merely because the current incoming object was just requested.
3. When replacing victims, charge an additional noise margin (1-strength)*measured_saving_rate*(bytes_in*sqrt(count_in) + sum(bytes_v*coverage_v*sqrt(count_v))). This is a heuristic uncertainty penalty, NOT a formal confidence interval. Admission, destination selection and final commit all charge the same margin. Strong observed burst continuation restores the original responsive value test. The completed-run prediction from study21 is unchanged.
4. Collect the advisory resident/capacity snapshot under the layout lock, then evaluate destination plans and record the advisory event outside it. Commit still acquires the layout lock and independently rechecks current capacity, open objects and benefit before eviction. No snapshot is trusted as a reservation. New native tests introduce unknown physical bytes after selection to verify safe rejection.
5. Common instrumentation (`profile_control_path`) in every arm measures Open elapsed time and layout-lock wait; read latency and actual per-request p99 already exist. Timing totals overlap and must not be added as an exact wall-time decomposition. Planning time is descriptive for selected plans, not all rejected attempts.

Copy checksums, cache publication, full-WAL durable read counts, background execution, source I/O and per-domain capacities remain unchanged. No access-time simulation, weakened durability, synthetic delays, future trace inspection or baseline retuning.

## Fixed matrix and gates

3 arms (AdaptiveHP, pooled SIEVE-2hit, pooled SIEVE-1hit) × 2 scenarios × 3 seeds = 18 speed runs. Moving_shared uses the unchanged study18–21 generator with seeds3201–3203; uniform uses the unchanged 24-key random generator with seeds3211–3213. Six separate 96-request content checks use3199/3198. Each speed run576×2MiB=1152MiB. Deterministic shuffled/rotated order gives each arm every position once within each scenario. No additional/replaced seeds or modifications after this batch starts.

Primary throughput = actual bytes/full monotonic foreground wall time. Preserve background-drained time, p99, CPU, traffic, control timing, exploration and uncertainty actions. Moving workload: >=5% paired geometric throughput gain AND all three pairs faster versus each SIEVE separately. Uniform non-regression: every paired throughput at least baseline. Tail goal: every paired p99 no worse than either SIEVE in both scenarios. Keep all failed goals explicit. A positive mean alone does not close the all-pairs gates. These small samples do not establish statistical significance.

Same total24MiB; our logical domains8/8/8MiB, pooled comparators24/0/0MiB. Same binary, inputs, direct foreground I/O, asynchronous verified copy, immutable canonical data, empty per-run application cache and SQLite durability. Existing cn7→cn13 NVMe/TCP only; cn14 untouched. No actual GPUs, serialized logical consumers, same local disk, uncontrolled target page cache. The strong pools have different geometry and are system references rather than one-flag ablations.

No contemporaneous old-version arm in this 18-run matrix: do not subtract study21 means to claim a causal improvement, or reuse old H/P/J component percentages for the new version. Correctness tests isolate the mechanism, but a later causal ablation/confirmation remains separate work. All source/binary/input hashes are frozen before timing; archive raw rows, events and SQL data and independently recompute results.
