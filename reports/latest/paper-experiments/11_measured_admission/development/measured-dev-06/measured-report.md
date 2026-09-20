# Measured-policy evidence

Stage: development. Batch: measured-dev-06. All expected runs passed audit.

Time ratio = AURA-adaptive/reference; less than one is faster. Actual throughput is logical MiB / outer wall time.

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Reference | n | Time ratio [95% CI] | Holm p | Verdict |
|---|---:|---:|---:|---:|---|---|---:|---|---:|---|
| stable | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 0.5863 [0.5842, 0.5885] | 1 | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 0.9039 [0.8933, 0.9146] | 1 | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 0.9467 [0.9414, 0.9521] | 1 | development / no confirmatory claim |
| stable | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 1.0107 [1.0056, 1.0159] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 0.6736 [0.6673, 0.6801] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 0.8988 [0.8876, 0.9101] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 0.7318 [0.7271, 0.7365] | 1 | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 0.8004 [0.7890, 0.8120] | 1 | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 0.6768 [0.6760, 0.6775] | 1 | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 0.9070 [0.8910, 0.9233] | 1 | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 0.9315 [0.9265, 0.9365] | 1 | development / no confirmatory claim |
| scan | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 1.0305 [1.0043, 1.0573] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 0.9703 [0.9642, 0.9765] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 0.9275 [0.9201, 0.9349] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 0.9226 [0.9133, 0.9319] | 1 | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 1.0133 [1.0109, 1.0157] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 1.0220 [1.0159, 1.0282] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 0.9165 [0.9050, 0.9282] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 0.9325 [0.9314, 0.9336] | 1 | development / no confirmatory claim |
| uniform | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 1.0150 [1.0034, 1.0267] | 1 | development / no confirmatory claim |

## Absolute performance and resource cost

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Strategy | n | Mean wall s | Mean MiB/s | Copied MiB | Daemon CPU s | Peak RSS KiB |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| stable | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 10.0891 | 76.123 | 0.00 | 2.045 | 11512.0 |
| stable | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 6.5457 | 117.371 | 90.00 | 2.715 | 12792.0 |
| stable | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 6.2483 | 122.914 | 65.00 | 2.600 | 12152.0 |
| stable | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 5.8527 | 131.221 | 8.00 | 2.140 | 12794.0 |
| stable | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 5.9156 | 129.832 | 8.00 | 2.125 | 12154.0 |
| shift | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 10.1152 | 75.926 | 0.00 | 2.065 | 11512.0 |
| shift | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 7.5831 | 101.320 | 161.00 | 3.310 | 12472.0 |
| shift | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 9.3125 | 82.486 | 392.00 | 4.415 | 12152.0 |
| shift | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 8.5135 | 90.214 | 32.00 | 2.490 | 12474.0 |
| shift | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 6.8142 | 112.712 | 32.00 | 2.415 | 12154.0 |
| scan | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 10.0785 | 76.202 | 0.00 | 2.030 | 11508.0 |
| scan | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 7.5215 | 102.141 | 200.00 | 3.345 | 12148.0 |
| scan | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 7.3227 | 104.883 | 176.00 | 3.325 | 12294.0 |
| scan | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 6.6213 | 116.067 | 8.00 | 1.975 | 12470.0 |
| scan | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 6.8208 | 112.597 | 8.00 | 2.145 | 12150.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 22.6273 | 82.111 | 0.00 | 3.615 | 12542.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 23.6719 | 78.486 | 1477.00 | 11.445 | 14452.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 23.7976 | 78.071 | 1475.00 | 11.565 | 13812.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 21.6688 | 85.748 | 37.00 | 4.120 | 13492.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 21.9577 | 84.624 | 60.00 | 4.235 | 13492.0 |
| uniform | 8 | 384 | 2 | 128 | False | RemoteOnly | 2 | 10.1342 | 75.783 | 0.00 | 2.055 | 11832.0 |
| uniform | 8 | 384 | 2 | 128 | False | LRU-equal | 2 | 11.3016 | 67.958 | 593.00 | 5.885 | 12152.0 |
| uniform | 8 | 384 | 2 | 128 | False | LFU-equal | 2 | 11.1071 | 69.146 | 594.00 | 5.700 | 12152.0 |
| uniform | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 2 | 10.2062 | 75.271 | 68.00 | 2.680 | 12792.0 |
| uniform | 8 | 384 | 2 | 128 | False | AURA-adaptive | 2 | 10.3577 | 74.150 | 67.00 | 2.840 | 12472.0 |

## Interpretation

The primary family comprises LRU, LFU and RecentLFU comparisons across the scenes in this batch; other families are per-component. Intervals are unadjusted paired bootstrap intervals; p-values use Holm correction within each family. No component is necessary merely because its point estimate is favorable. Inspect mechanisms.json and component-evidence.json for actual activity and changed actions; untriggered components have no identified necessity even if timing differs.

Report paired-comparisons.json with_drain_ratio alongside foreground time. mechanisms.json contains p50/p99 of individual object reads, CPU, RSS and copying for every run. In paced replay it also reports block arrival-to-issue and arrival-to-completion p99, including loader backlog; these are not inference TTFT. segments.json partitions time by request-index quarter, including boundary idle gaps; quarters are not independent replication units. interactions.json is an exploratory four-cell comparison, not a full RobustBenefit test.

Foreground timing excludes initialization and post-run verification. Copy payload is not physical wire/disk traffic. Logical cache domains are not physical GPUs. Public traces preserve block identity/order with synthetic normalized bytes; saturated replay is not full inference or the original concurrency. Small-n development/supplementary runs do not support confirmatory claims. Negative and uncertain results are retained.
