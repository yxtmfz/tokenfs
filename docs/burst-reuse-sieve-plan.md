# Burst reuse versus pooled SIEVE — frozen 18-run development screen

The previous full policy was 1.96% slower than PoolSIEVE2. It copied 18/24/23 one-burst objects in seeds 3001/3002/3003, just as SIEVE did; reduced remote traffic did not repay control cost. This development round preserves those results and tests one falsifiable hypothesis: cold-start admission waits for an object's own repeat even when recent completed runs already provide causal evidence of immediate reuse.

## One opt-in algorithm change

`measured_burst_reuse` learns completed contiguous runs of the same logical object across consumers, bounded by the existing 128-observation window budget. At least eight completed runs are required. For a current run of length k, forecast residual repeats as sum(max(L-k,0))/(2 + count(L>=k)), using completed runs only. The two pseudo-observations shrink the estimate; no future run length, four-request constant, seed, phase, object ID or workload label enters runtime policy. The active run is censored. When the key changes the forecast for the prior key is zero. Keep max(existing long-term value, short-term residual value), not their sum. Arrival and resident use identical values. Early admission still pays measured copy cost plus selected victim loss and rechecks physical capacity, pinning, coverage and current benefit at execution. First-read forecasts are disabled until warmed; no reuse in recent runs produces zero forecast. Defaults remain off; configuration requires causal, shared, cost-based admission.

All prior H/P/J formulas and disk topology remain. This is short-term reuse integration, not a claim that run-length prediction itself is a new invention. No change to copy checksum, durable SQLite accounting, I/O flags or baseline admission rules.

## Fixed budget, fixed comparators

Moving_shared (same generator as 18–20), seeds 3101–3103: OldHP, BurstHP, PoolSIEVE2, PoolSIEVE1 = 12 runs. OldHP/BurstHP differ only in the new flag. SIEVE1/SIEVE2 differ only in the admission threshold (1 versus 2), to prevent calling earlier admission a win over generic SIEVE. Uniform 24-key random access, seeds 3111–3112: BurstHP, PoolSIEVE2, PoolSIEVE1 = 6 negative-control runs. All runs 576 requests × 2 MiB. Seven separate 96-request full-SHA correctness runs use seeds 3099/3098. No replacements or extra performance runs after results; failed attempts are retained.

Total cache 24 MiB: measured policies 3 × 8 MiB, both shared pools 24/0/0. Same binary and trace within each block; empty application caches, real existing cn7-to-cn13 NVMe/TCP, same direct foreground I/O and async verified buffered copy. Serialized three logical callers, no physical GPU evidence. Pool geometry is explicitly different: stronger system references, not single-variable ablations. Target cache uncontrolled. Deterministic shuffled/rotated order, all order records retained; three pairs do not fully balance four positions.

## Endpoints and limits

Actual throughput = completed logical bytes/full foreground wall time. Report drained completion, CPU, p99, remote and copied MiB, forecast actions, exact source/binary/config/input hashes and all seeds. Pilot positive gate: >=5% paired geometric throughput gain and 3/3 moving pairs faster, separately versus each SIEVE. Report uniform regression and tail changes explicitly. No significance or universal superiority claim, no parameter changes after timing begins. Results are development data, not an independent final paper confirmation. If only SIEVE2 is beaten, state precisely that and retain SIEVE1.
