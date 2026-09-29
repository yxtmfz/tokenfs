# Final paper claim boundaries

The final independent batch is protocol [independent HPJ](integrated-hpj-cohort-caller-independent-plan.md). Its result determines which proposed claims survive; no positive outcome is assumed here.

1. Hotspot contribution: a bounded causal recurrence/lifetime estimator for cache admission and victim valuation. A Full versus NoHotspot comparison estimates its marginal value with placement and joint admission retained. No claim of forecasting all future demand.
2. Placement contribution: demand-aware placement across logical consumer domains in a shared storage cache. Current three consuming processes run serially on one cn7 host; all cache partitions share a disk. Caller identities in public replay are constructed. Do not call this measured physical GPU affinity, NVLink optimization, multi-GPU parallel KV sharing or inference speedup. A physical-GPU claim needs another environment and is outside this paper evaluation.
3. Integration contribution: victim-loss-aware joint admission in the implemented storage policy. NoJoint switches off that existing admission term. It supports a marginal-decision claim only when the mechanism changes actions and actual throughput improves. It is not a fair general comparison to every independently optimized H+P controller, an optimality proof, or proof of super-additive H×P interaction. Present it as the integration framework unless separate novelty arguments justify more.

The overall comparison is against the equal-capability SIEVE adapter in TokenFS, not the native optimized SIEVE implementation or every modern cache system. The three internal ablations are not external baselines. Common metadata/copy execution repairs apply to all arms and are not new strategy innovations.

Report actual completed logical bytes/wall second, all empirical p99 observations, copy/remote/control overhead and scope. Keep historical tuning data separate. Do not add percentage gains across modules. A positive mean with mixed per-input signs is mixed evidence, not universal superiority. Stable and uniform workloads are boundary controls; negative results must remain. Existing strict per-input throughput/p99/drain/mechanism checks remain visible, even if a narrower throughput-only claim is supported.

## Independent results now available

See [report66](../reports/latest/paper-experiments/66_independent_final/README.md).34 speed runs and480 request-level content checks completed. Overall public replay throughput improves20.503% with3/3 paired throughput/p99 gains; moving aggregate improves only0.251% with mixed signs. Hotspot ablation does not establish a stable marginal improvement (moving−0.511%, public+0.505%, mixed signs). Placement and victim-loss admission show limited empirical benefits under the stated logical-domain scope; strict per-input gates pass18/26 overall. Do not describe all three modules as independently established performance innovations. No statistical or physical-GPU confirmation.

## Follow-up hotspot candidate rejected

[Report67](../reports/latest/paper-experiments/67_hotspot_object_prior/README.md) investigates two already inspected report66 inputs, with24 timed runs and480 content checks. A distinct-object newcomer prior reduces copies but fails the throughput/p99 requirements: H strict0/4, all three ablations plus SIEVE4/16. The candidate is not adopted; native production code is retained. Its development outcomes do not replace or extend report66's independent claims. First-reference requests dominate the moving-input tail; lower copying alone does not establish lower p99.
