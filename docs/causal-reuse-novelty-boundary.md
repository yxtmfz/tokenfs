# Candidate contribution and related-work boundary

The implementation now has three separately switchable mechanisms, but switches and throughput gains alone do not prove three independent original contributions.

| Mechanism | What is implemented | What should be demonstrated | What cannot be claimed |
|---|---|---|---|
| H: overdue-reuse valuation | A common request clock; observed object-specific gaps reduce stale resident value, symmetrically with admission | H/no-H speed improvement with changed decisions, including a stable negative control later | First use of recency, frequency, inter-reference gap or exponential decay |
| P: consumer-valued shared placement | Value follows all recent consumers; storage location is chosen under per-domain quotas; a surviving READY copy removes marginal coverage loss; in-flight copies coalesce | P/no-P speed improvement with real noncaller placements and fewer remote reads; beat a simpler equal-capacity pooled reference | First shared cache, first GPU affinity, or measured real GPU traffic in this logical-domain experiment |
| J: consistent admission and placement | One residual-benefit definition charges copy and all displaced shared coverage; execution rechecks and exact upper-bound pruning | HP/Independent gain; contributions of H and P persist in the full version; retain failures | A theoretical global optimum, performance guarantee, or synergy proved merely by stacking H and P |

The possible systems contribution is the consistent use of **time-aligned consumer evidence and residual shared coverage across admission, location selection and commit-time revalidation** in a changing NVMe/TCP cache workload. Whether that integration is sufficiently distinct and useful remains an empirical and related-work question. Keep the three mechanisms in the evaluation, but do not force the paper to market three innovations if only two withstand comparison.

Primary sources checked:

- [LUV, USITS 1999](https://www.usenix.org/conference/usits-99/using-full-reference-history-efficient-document-replacement-web-caches) already uses reference frequency and recency to estimate the chance of another reference. It rules out calling a general residual-reuse estimate new.
- [ARC, FAST 2003](https://www.usenix.org/conference/fast-03/arc-self-tuning-low-overhead-replacement-cache) adapts the balance of recency and frequency. Our fixed four-request minimum half-life is a heuristic, not a better-established self-tuning guarantee.
- [On Cost-Driven Collaborative Data Caching, TPDS 2019](https://grc.iit.edu/publications/wang-2019-cost-driven-f3e9/) treats shared caching, migration and replication, including an online algorithm. It rules out a broad first cost-driven joint-caching claim.
- [Preble](https://arxiv.org/abs/2407.00023) jointly considers distributed KV reuse and load balancing. Our current same-disk logical domains do not establish hardware-aware GPU locality beyond this prior setting.

The 18-run pilot is an engineering screen. Stronger publication claims still require a held-out trace family, a no-sharing/stable counterexample, and physical GPU validation if the title or conclusions concern GPU speed.
