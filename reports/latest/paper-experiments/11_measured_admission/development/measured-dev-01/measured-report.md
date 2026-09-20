# Measured-policy evidence

Stage: development. Batch: measured-dev-01. All expected runs passed audit.

Time ratio = AURA-adaptive/reference; less than one is faster. Actual throughput is logical MiB / outer wall time.

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Reference | n | Time ratio [95% CI] | Holm p | Verdict |
|---|---:|---:|---:|---:|---|---|---:|---|---:|---|
| stable | 8 | 384 | 2 | 128 | False | RemoteOnly | 1 | 0.6023 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | LRU-equal | 1 | 0.8623 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | LFU-equal | 1 | 0.9071 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 1.0055 [unavailable] | unavailable | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | RemoteOnly | 1 | 0.8919 [unavailable] | unavailable | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | LRU-equal | 1 | 1.1132 [unavailable] | unavailable | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | LFU-equal | 1 | 0.9724 [unavailable] | unavailable | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 1.0061 [unavailable] | unavailable | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | RemoteOnly | 1 | 0.6733 [unavailable] | unavailable | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | LRU-equal | 1 | 0.8972 [unavailable] | unavailable | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | LFU-equal | 1 | 0.9380 [unavailable] | unavailable | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 1.0111 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | RemoteOnly | 1 | 0.9618 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | LRU-equal | 1 | 0.9173 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | LFU-equal | 1 | 0.9155 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 0.9855 [unavailable] | unavailable | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | RemoteOnly | 1 | 0.9955 [unavailable] | unavailable | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | LRU-equal | 1 | 0.9072 [unavailable] | unavailable | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | LFU-equal | 1 | 0.9182 [unavailable] | unavailable | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 1.0147 [unavailable] | unavailable | development / no confirmatory claim |

## Absolute performance and resource cost

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Strategy | n | Mean wall s | Mean MiB/s | Copied MiB | Daemon CPU s | Peak RSS KiB |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| stable | 8 | 384 | 2 | 128 | False | RemoteOnly | 1 | 10.0169 | 76.670 | 0.00 | 1.880 | 10872.0 |
| stable | 8 | 384 | 2 | 128 | False | LRU-equal | 1 | 6.9969 | 109.763 | 126.00 | 3.040 | 12184.0 |
| stable | 8 | 384 | 2 | 128 | False | LFU-equal | 1 | 6.6513 | 115.466 | 94.00 | 2.880 | 14072.0 |
| stable | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 6.0006 | 127.988 | 8.00 | 2.180 | 12796.0 |
| stable | 8 | 384 | 2 | 128 | False | AURA-adaptive | 1 | 6.0334 | 127.292 | 8.00 | 2.180 | 12152.0 |
| shift | 8 | 384 | 2 | 128 | False | RemoteOnly | 1 | 9.8398 | 78.050 | 0.00 | 1.690 | 11512.0 |
| shift | 8 | 384 | 2 | 128 | False | LRU-equal | 1 | 7.8838 | 97.415 | 206.00 | 3.130 | 12152.0 |
| shift | 8 | 384 | 2 | 128 | False | LFU-equal | 1 | 9.0258 | 85.089 | 340.00 | 4.230 | 14068.0 |
| shift | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 8.7231 | 88.043 | 34.00 | 2.540 | 12152.0 |
| shift | 8 | 384 | 2 | 128 | False | AURA-adaptive | 1 | 8.7764 | 87.508 | 32.00 | 2.530 | 12156.0 |
| scan | 8 | 384 | 2 | 128 | False | RemoteOnly | 1 | 10.1940 | 75.338 | 0.00 | 2.070 | 11504.0 |
| scan | 8 | 384 | 2 | 128 | False | LRU-equal | 1 | 7.6497 | 100.396 | 200.00 | 3.450 | 12784.0 |
| scan | 8 | 384 | 2 | 128 | False | LFU-equal | 1 | 7.3173 | 104.957 | 176.00 | 3.330 | 12144.0 |
| scan | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 6.7881 | 113.139 | 8.00 | 2.190 | 12788.0 |
| scan | 8 | 384 | 2 | 128 | False | AURA-adaptive | 1 | 6.8633 | 111.900 | 8.00 | 2.170 | 12216.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | RemoteOnly | 1 | 23.1129 | 82.032 | 0.00 | 3.700 | 13172.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | LRU-equal | 1 | 24.2362 | 78.230 | 1474.00 | 11.750 | 15532.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | LFU-equal | 1 | 24.2832 | 78.079 | 1472.00 | 11.610 | 13172.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 22.5573 | 84.053 | 48.00 | 4.380 | 13172.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-adaptive | 1 | 22.2309 | 85.287 | 30.00 | 4.060 | 13812.0 |
| uniform | 8 | 384 | 2 | 128 | False | RemoteOnly | 1 | 10.1749 | 75.480 | 0.00 | 2.050 | 12152.0 |
| uniform | 8 | 384 | 2 | 128 | False | LRU-equal | 1 | 11.1654 | 68.784 | 582.00 | 5.830 | 12152.0 |
| uniform | 8 | 384 | 2 | 128 | False | LFU-equal | 1 | 11.0318 | 69.617 | 582.00 | 5.690 | 14072.0 |
| uniform | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 9.9822 | 76.937 | 54.00 | 2.490 | 12796.0 |
| uniform | 8 | 384 | 2 | 128 | False | AURA-adaptive | 1 | 10.1290 | 75.822 | 28.00 | 2.510 | 12796.0 |

## Interpretation

The primary family comprises LRU, LFU and RecentLFU comparisons across the scenes in this batch; other families are per-component. Intervals are unadjusted paired bootstrap intervals; p-values use Holm correction within each family. No component is necessary merely because its point estimate is favorable. Inspect mechanisms.json and component-evidence.json for actual activity and changed actions; untriggered components have no identified necessity even if timing differs.

Report paired-comparisons.json with_drain_ratio alongside foreground time. mechanisms.json contains p50/p99 of individual object reads, CPU, RSS and copying for every run. In paced replay it also reports block arrival-to-issue and arrival-to-completion p99, including loader backlog; these are not inference TTFT. segments.json partitions time by request-index quarter, including boundary idle gaps; quarters are not independent replication units. interactions.json is an exploratory four-cell comparison, not a full RobustBenefit test.

Foreground timing excludes initialization and post-run verification. Copy payload is not physical wire/disk traffic. Logical cache domains are not physical GPUs. Public traces preserve block identity/order with synthetic normalized bytes; saturated replay is not full inference or the original concurrency. Small-n development/supplementary runs do not support confirmatory claims. Negative and uncertain results are retained.
