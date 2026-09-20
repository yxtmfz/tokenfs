# Measured-policy evidence

Stage: development. Batch: measured-dev-05. All expected runs passed audit.

Time ratio = AURA-adaptive/reference; less than one is faster. Actual throughput is logical MiB / outer wall time.

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Reference | n | Time ratio [95% CI] | Holm p | Verdict |
|---|---:|---:|---:|---:|---|---|---:|---|---:|---|
| stable | 8 | 384 | 2 | 128 | False | AURA-no-cost | 2 | 0.9989 [0.9839, 1.0140] | 1 | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-shift | 2 | 0.9949 [0.9913, 0.9985] | 1 | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 1.0050 [1.0000, 1.0100] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | AURA-no-cost | 2 | 1.0343 [1.0088, 1.0604] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | AURA-no-shift | 2 | 0.7725 [0.7721, 0.7729] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 0.7807 [0.7804, 0.7811] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-no-cost | 2 | 1.0294 [1.0131, 1.0460] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-no-shift | 2 | 1.0227 [1.0085, 1.0372] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 1.0347 [1.0241, 1.0453] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | AURA-no-cost | 2 | 1.0177 [1.0028, 1.0328] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | AURA-no-shift | 2 | 0.9980 [0.9943, 1.0017] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 1.0172 [1.0003, 1.0343] | 1 | development / no confirmatory claim |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | AURA-no-cost | 2 | 1.0087 [1.0003, 1.0172] | 1 | development / no confirmatory claim |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | AURA-no-cost | 2 | 1.0202 [1.0088, 1.0317] | 1 | development / no confirmatory claim |

## Absolute performance and resource cost

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Strategy | n | Mean wall s | Mean MiB/s | Copied MiB | Daemon CPU s | Peak RSS KiB |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| stable | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 5.8603 | 131.076 | 8.00 | 2.125 | 12148.0 |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-cost | 2 | 5.8690 | 130.968 | 8.00 | 2.150 | 12470.0 |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-shift | 2 | 5.8908 | 130.413 | 8.00 | 2.120 | 12468.0 |
| stable | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 5.8317 | 131.742 | 8.00 | 2.110 | 12472.0 |
| shift | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 6.6624 | 115.275 | 33.00 | 2.445 | 12154.0 |
| shift | 8 | 384 | 2 | 128 | False | AURA-no-cost | 2 | 6.4442 | 119.277 | 34.00 | 2.315 | 12150.0 |
| shift | 8 | 384 | 2 | 128 | False | AURA-no-shift | 2 | 8.6246 | 89.048 | 38.00 | 2.555 | 12148.0 |
| shift | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 8.5334 | 90.001 | 39.00 | 2.565 | 12152.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 22.4697 | 83.217 | 102.00 | 4.600 | 12470.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-no-cost | 2 | 21.8226 | 85.648 | 49.00 | 4.240 | 12470.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-no-shift | 2 | 21.9659 | 85.091 | 62.00 | 4.275 | 12470.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 21.7133 | 86.087 | 43.00 | 4.075 | 12470.0 |
| uniform | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 10.4235 | 73.681 | 60.00 | 2.720 | 12476.0 |
| uniform | 8 | 384 | 2 | 128 | False | AURA-no-cost | 2 | 10.2441 | 74.998 | 63.00 | 2.690 | 12792.0 |
| uniform | 8 | 384 | 2 | 128 | False | AURA-no-shift | 2 | 10.4447 | 73.536 | 59.00 | 2.810 | 12796.0 |
| uniform | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 10.2498 | 74.962 | 64.00 | 2.650 | 12796.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | AURA-adaptive | 2 | 29.6264 | 69.130 | 1.00 | 7.545 | 10414.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | AURA-no-cost | 2 | 29.3698 | 69.732 | 1.00 | 7.285 | 10926.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | AURA-adaptive | 2 | 26.5643 | 77.134 | 31.50 | 7.590 | 12014.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | AURA-no-cost | 2 | 26.0343 | 78.675 | 31.50 | 7.310 | 10332.0 |

## Interpretation

The primary family comprises LRU, LFU and RecentLFU comparisons across the scenes in this batch; other families are per-component. Intervals are unadjusted paired bootstrap intervals; p-values use Holm correction within each family. No component is necessary merely because its point estimate is favorable. Inspect mechanisms.json and component-evidence.json for actual activity and changed actions; untriggered components have no identified necessity even if timing differs.

Report paired-comparisons.json with_drain_ratio alongside foreground time. mechanisms.json contains p50/p99 of individual object reads, CPU, RSS and copying for every run. In paced replay it also reports block arrival-to-issue and arrival-to-completion p99, including loader backlog; these are not inference TTFT. segments.json partitions time by request-index quarter, including boundary idle gaps; quarters are not independent replication units. interactions.json is an exploratory four-cell comparison, not a full RobustBenefit test.

Foreground timing excludes initialization and post-run verification. Copy payload is not physical wire/disk traffic. Logical cache domains are not physical GPUs. Public traces preserve block identity/order with synthetic normalized bytes; saturated replay is not full inference or the original concurrency. Small-n development/supplementary runs do not support confirmatory claims. Negative and uncertain results are retained.
