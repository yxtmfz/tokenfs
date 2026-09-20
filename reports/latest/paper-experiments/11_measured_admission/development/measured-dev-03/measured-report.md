# Measured-policy evidence

Stage: development. Batch: measured-dev-03. All expected runs passed audit.

Time ratio = AURA-adaptive/reference; less than one is faster. Actual throughput is logical MiB / outer wall time.

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Reference | n | Time ratio [95% CI] | Holm p | Verdict |
|---|---:|---:|---:|---:|---|---|---:|---|---:|---|
| stable | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 0.5891 [0.5794, 0.5989] | 1 | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 0.8869 [0.8710, 0.9031] | 1 | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 0.9367 [0.9281, 0.9453] | 1 | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 1.0344 [1.0112, 1.0581] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 0.6750 [0.6699, 0.6802] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 0.9214 [0.9210, 0.9219] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 0.7578 [0.7457, 0.7701] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 0.8089 [0.7895, 0.8288] | 1 | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 0.6760 [0.6709, 0.6812] | 1 | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 0.8955 [0.8934, 0.8977] | 1 | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 0.9358 [0.9331, 0.9385] | 1 | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 1.0045 [0.9984, 1.0107] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 0.9578 [0.9328, 0.9835] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 0.9292 [0.9250, 0.9335] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 0.9192 [0.9024, 0.9364] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 1.0045 [0.9787, 1.0310] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 1.0095 [0.9987, 1.0205] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 0.9108 [0.9083, 0.9132] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 0.9447 [0.9423, 0.9470] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 0.9957 [0.9940, 0.9974] | 1 | development / no confirmatory claim |

## Absolute performance and resource cost

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Strategy | n | Mean wall s | Mean MiB/s | Copied MiB | Daemon CPU s | Peak RSS KiB |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| stable | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 10.1045 | 76.006 | 0.00 | 2.025 | 11832.0 |
| stable | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 6.7117 | 114.429 | 108.00 | 2.750 | 12472.0 |
| stable | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 6.3549 | 120.854 | 77.00 | 2.680 | 12152.0 |
| stable | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 5.7584 | 133.553 | 8.00 | 1.980 | 12156.0 |
| stable | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 5.9530 | 129.037 | 8.00 | 2.145 | 12816.0 |
| shift | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 10.0690 | 76.274 | 0.00 | 2.020 | 11512.0 |
| shift | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 7.3770 | 104.120 | 155.00 | 3.070 | 12152.0 |
| shift | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 8.9698 | 85.623 | 353.00 | 4.255 | 13112.0 |
| shift | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 8.4036 | 91.407 | 33.00 | 2.370 | 12154.0 |
| shift | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 6.7975 | 112.996 | 33.00 | 2.385 | 12476.0 |
| scan | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 10.1233 | 75.868 | 0.00 | 2.055 | 11508.0 |
| scan | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 7.6418 | 100.500 | 200.00 | 3.465 | 12468.0 |
| scan | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 7.3132 | 105.016 | 176.00 | 3.350 | 12468.0 |
| scan | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 6.8130 | 112.729 | 8.00 | 2.165 | 12152.0 |
| scan | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 6.8436 | 112.222 | 8.00 | 2.125 | 12152.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 22.9773 | 81.732 | 0.00 | 3.725 | 12018.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 23.6907 | 79.307 | 1511.00 | 11.435 | 12658.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 23.9435 | 78.438 | 1505.00 | 11.645 | 12978.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 21.9092 | 85.716 | 30.00 | 4.110 | 12658.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 22.0174 | 85.353 | 64.00 | 4.045 | 13618.0 |
| uniform | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 10.1220 | 75.879 | 0.00 | 2.045 | 11512.0 |
| uniform | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 11.2194 | 68.453 | 603.00 | 5.995 | 13446.0 |
| uniform | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 10.8170 | 71.001 | 589.00 | 5.605 | 13112.0 |
| uniform | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 10.2624 | 74.836 | 55.00 | 2.750 | 12796.0 |
| uniform | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 10.2183 | 75.160 | 55.00 | 2.675 | 12156.0 |

## Interpretation

The primary family comprises LRU, LFU and RecentLFU comparisons across the scenes in this batch; other families are per-component. Intervals are unadjusted paired bootstrap intervals; p-values use Holm correction within each family. No component is necessary merely because its point estimate is favorable. Inspect mechanisms.json and component-evidence.json for actual activity and changed actions; untriggered components have no identified necessity even if timing differs.

Report paired-comparisons.json with_drain_ratio alongside foreground time. mechanisms.json contains p50/p99 of individual object reads, CPU, RSS and copying for every run. In paced replay it also reports block arrival-to-issue and arrival-to-completion p99, including loader backlog; these are not inference TTFT. segments.json partitions time by request-index quarter, including boundary idle gaps; quarters are not independent replication units. interactions.json is an exploratory four-cell comparison, not a full RobustBenefit test.

Foreground timing excludes initialization and post-run verification. Copy payload is not physical wire/disk traffic. Logical cache domains are not physical GPUs. Public traces preserve block identity/order with synthetic normalized bytes; saturated replay is not full inference or the original concurrency. Small-n development/supplementary runs do not support confirmatory claims. Negative and uncertain results are retained.
