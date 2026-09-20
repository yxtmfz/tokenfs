# Measured-policy evidence

Stage: development. Batch: measured-dev-04. All expected runs passed audit.

Time ratio = AURA-adaptive/reference; less than one is faster. Actual throughput is logical MiB / outer wall time.

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Reference | n | Time ratio [95% CI] | Holm p | Verdict |
|---|---:|---:|---:|---:|---|---|---:|---|---:|---|
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RemoteOnly | 2 | 0.9860 [0.9770, 0.9952] | 1 | development / no confirmatory claim |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LRU-equal | 2 | 0.9861 [0.9854, 0.9869] | 1 | development / no confirmatory claim |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LFU-equal | 2 | 1.0267 [0.9873, 1.0675] | 1 | development / no confirmatory claim |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 2 | 1.0270 [0.9927, 1.0624] | 1 | development / no confirmatory claim |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RemoteOnly | 2 | 0.9132 [0.9033, 0.9234] | 1 | development / no confirmatory claim |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LRU-equal | 2 | 0.9455 [0.9426, 0.9483] | 1 | development / no confirmatory claim |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LFU-equal | 2 | 0.9859 [0.9773, 0.9946] | 1 | development / no confirmatory claim |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 2 | 1.0015 [0.9922, 1.0109] | 1 | development / no confirmatory claim |
| stable | 16 | 384 | 2 | 128 | False | RemoteOnly | 1 | 0.6141 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 16 | 384 | 2 | 128 | False | LRU-equal | 1 | 0.9993 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 16 | 384 | 2 | 128 | False | LFU-equal | 1 | 0.9976 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 16 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 1.0048 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 32 | 384 | 2 | 128 | False | RemoteOnly | 1 | 0.5751 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 32 | 384 | 2 | 128 | False | LRU-equal | 1 | 0.9375 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 32 | 384 | 2 | 128 | False | LFU-equal | 1 | 0.9379 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 32 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 0.9424 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 16 | 384 | 2 | 128 | False | RemoteOnly | 1 | 0.9283 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 16 | 384 | 2 | 128 | False | LRU-equal | 1 | 0.9016 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 16 | 384 | 2 | 128 | False | LFU-equal | 1 | 0.9342 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 16 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 1.0126 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 32 | 384 | 2 | 128 | False | RemoteOnly | 1 | 0.8358 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 32 | 384 | 2 | 128 | False | LRU-equal | 1 | 0.8628 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 32 | 384 | 2 | 128 | False | LFU-equal | 1 | 0.9293 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 32 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 1.0271 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 4 | 4096 | 1 | 128 | False | RemoteOnly | 1 | 0.5905 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 4 | 4096 | 1 | 128 | False | LRU-equal | 1 | 0.7653 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 4 | 4096 | 1 | 128 | False | LFU-equal | 1 | 0.8609 [unavailable] | unavailable | development / no confirmatory claim |
| stable | 4 | 4096 | 1 | 128 | False | RecentLFU-admit | 1 | 0.9763 [unavailable] | unavailable | development / no confirmatory claim |
| shift | 4 | 4096 | 1 | 128 | False | RemoteOnly | 1 | 0.8090 [unavailable] | unavailable | development / no confirmatory claim |
| shift | 4 | 4096 | 1 | 128 | False | LRU-equal | 1 | 1.0586 [unavailable] | unavailable | development / no confirmatory claim |
| shift | 4 | 4096 | 1 | 128 | False | LFU-equal | 1 | 0.8350 [unavailable] | unavailable | development / no confirmatory claim |
| shift | 4 | 4096 | 1 | 128 | False | RecentLFU-admit | 1 | 1.3681 [unavailable] | unavailable | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 64 | False | RecentLFU-admit | 1 | 0.9292 [unavailable] | unavailable | development / no confirmatory claim |
| shift | 8 | 384 | 2 | 256 | False | RecentLFU-admit | 1 | 0.7653 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 64 | False | RecentLFU-admit | 1 | 1.0244 [unavailable] | unavailable | development / no confirmatory claim |
| mixed_fit | 8 | 384 | 2 | 256 | False | RecentLFU-admit | 1 | 1.0079 [unavailable] | unavailable | development / no confirmatory claim |

## Absolute performance and resource cost

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Strategy | n | Mean wall s | Mean MiB/s | Copied MiB | Daemon CPU s | Peak RSS KiB |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RemoteOnly | 2 | 30.1881 | 67.842 | 0.00 | 7.495 | 10088.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LRU-equal | 2 | 30.1861 | 67.849 | 5.00 | 7.485 | 10408.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LFU-equal | 2 | 29.0079 | 70.671 | 5.00 | 6.265 | 10408.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 2 | 28.9948 | 70.682 | 1.00 | 6.835 | 10634.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | AURA-adaptive | 2 | 29.7672 | 68.805 | 1.00 | 7.490 | 10898.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RemoteOnly | 2 | 29.8230 | 68.675 | 0.00 | 7.305 | 9452.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LRU-equal | 2 | 28.8088 | 71.105 | 198.50 | 8.600 | 13250.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LFU-equal | 2 | 27.6331 | 74.167 | 118.00 | 8.195 | 13526.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 2 | 27.2033 | 75.341 | 79.50 | 7.955 | 11384.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | AURA-adaptive | 2 | 27.2395 | 75.209 | 79.50 | 7.885 | 12684.0 |
| stable | 16 | 384 | 2 | 128 | False | RemoteOnly | 1 | 10.1043 | 76.007 | 0.00 | 2.010 | 11512.0 |
| stable | 16 | 384 | 2 | 128 | False | LRU-equal | 1 | 6.2094 | 123.683 | 60.00 | 2.610 | 12152.0 |
| stable | 16 | 384 | 2 | 128 | False | LFU-equal | 1 | 6.2205 | 123.463 | 62.00 | 2.580 | 12152.0 |
| stable | 16 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 6.1760 | 124.352 | 26.00 | 2.350 | 12796.0 |
| stable | 16 | 384 | 2 | 128 | False | AURA-adaptive | 1 | 6.2054 | 123.764 | 26.00 | 2.380 | 12156.0 |
| stable | 32 | 384 | 2 | 128 | False | RemoteOnly | 1 | 10.1199 | 75.890 | 0.00 | 2.010 | 11512.0 |
| stable | 32 | 384 | 2 | 128 | False | LRU-equal | 1 | 6.2086 | 123.700 | 52.00 | 2.310 | 12152.0 |
| stable | 32 | 384 | 2 | 128 | False | LFU-equal | 1 | 6.2055 | 123.761 | 52.00 | 2.600 | 12792.0 |
| stable | 32 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 6.1760 | 124.351 | 32.00 | 2.220 | 11788.0 |
| stable | 32 | 384 | 2 | 128 | False | AURA-adaptive | 1 | 5.8203 | 131.952 | 32.00 | 2.050 | 12156.0 |
| mixed_fit | 16 | 384 | 2 | 128 | False | RemoteOnly | 1 | 24.0301 | 81.731 | 0.00 | 3.810 | 11504.0 |
| mixed_fit | 16 | 384 | 2 | 128 | False | LRU-equal | 1 | 24.7421 | 79.379 | 1424.00 | 11.770 | 12144.0 |
| mixed_fit | 16 | 384 | 2 | 128 | False | LFU-equal | 1 | 23.8804 | 82.243 | 1398.00 | 11.560 | 12144.0 |
| mixed_fit | 16 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 22.0313 | 89.146 | 64.00 | 4.560 | 12784.0 |
| mixed_fit | 16 | 384 | 2 | 128 | False | AURA-adaptive | 1 | 22.3082 | 88.039 | 94.00 | 4.770 | 12784.0 |
| mixed_fit | 32 | 384 | 2 | 128 | False | RemoteOnly | 1 | 24.0612 | 81.625 | 0.00 | 3.890 | 12144.0 |
| mixed_fit | 32 | 384 | 2 | 128 | False | LRU-equal | 1 | 23.3080 | 84.263 | 1160.00 | 10.760 | 12784.0 |
| mixed_fit | 32 | 384 | 2 | 128 | False | LFU-equal | 1 | 21.6422 | 90.749 | 1024.00 | 10.120 | 12144.0 |
| mixed_fit | 32 | 384 | 2 | 128 | False | RecentLFU-admit | 1 | 19.5813 | 100.300 | 78.00 | 4.680 | 12144.0 |
| mixed_fit | 32 | 384 | 2 | 128 | False | AURA-adaptive | 1 | 20.1111 | 97.658 | 128.00 | 4.950 | 12784.0 |
| stable | 4 | 4096 | 1 | 128 | False | RemoteOnly | 1 | 59.0231 | 69.397 | 0.00 | 15.030 | 8808.0 |
| stable | 4 | 4096 | 1 | 128 | False | LRU-equal | 1 | 45.5375 | 89.948 | 1270.00 | 22.050 | 12272.0 |
| stable | 4 | 4096 | 1 | 128 | False | LFU-equal | 1 | 40.4799 | 101.186 | 898.00 | 19.410 | 13240.0 |
| stable | 4 | 4096 | 1 | 128 | False | RecentLFU-admit | 1 | 35.6964 | 114.746 | 4.00 | 13.310 | 10968.0 |
| stable | 4 | 4096 | 1 | 128 | False | AURA-adaptive | 1 | 34.8512 | 117.528 | 4.00 | 12.830 | 8808.0 |
| shift | 4 | 4096 | 1 | 128 | False | RemoteOnly | 1 | 58.7624 | 69.704 | 0.00 | 14.730 | 10724.0 |
| shift | 4 | 4096 | 1 | 128 | False | LRU-equal | 1 | 44.9086 | 91.207 | 1310.00 | 21.340 | 14124.0 |
| shift | 4 | 4096 | 1 | 128 | False | LFU-equal | 1 | 56.9315 | 71.946 | 2502.00 | 29.930 | 13504.0 |
| shift | 4 | 4096 | 1 | 128 | False | RecentLFU-admit | 1 | 34.7497 | 117.872 | 16.00 | 12.590 | 8808.0 |
| shift | 4 | 4096 | 1 | 128 | False | AURA-adaptive | 1 | 47.5394 | 86.160 | 8.00 | 14.850 | 8808.0 |
| shift | 8 | 384 | 2 | 64 | False | RecentLFU-admit | 1 | 7.4001 | 103.782 | 34.00 | 2.490 | 12796.0 |
| shift | 8 | 384 | 2 | 64 | False | AURA-adaptive | 1 | 6.8760 | 111.692 | 34.00 | 2.430 | 12152.0 |
| shift | 8 | 384 | 2 | 256 | False | RecentLFU-admit | 1 | 8.8748 | 86.537 | 22.00 | 2.340 | 12156.0 |
| shift | 8 | 384 | 2 | 256 | False | AURA-adaptive | 1 | 6.7916 | 113.081 | 34.00 | 2.420 | 12156.0 |
| mixed_fit | 8 | 384 | 2 | 64 | False | RecentLFU-admit | 1 | 22.5197 | 87.213 | 36.00 | 4.190 | 11504.0 |
| mixed_fit | 8 | 384 | 2 | 64 | False | AURA-adaptive | 1 | 23.0687 | 85.137 | 70.00 | 4.610 | 13424.0 |
| mixed_fit | 8 | 384 | 2 | 256 | False | RecentLFU-admit | 1 | 22.6885 | 86.564 | 18.00 | 4.080 | 12784.0 |
| mixed_fit | 8 | 384 | 2 | 256 | False | AURA-adaptive | 1 | 22.8680 | 85.884 | 34.00 | 4.240 | 13048.0 |

## Interpretation

The primary family comprises LRU, LFU and RecentLFU comparisons across the scenes in this batch; other families are per-component. Intervals are unadjusted paired bootstrap intervals; p-values use Holm correction within each family. No component is necessary merely because its point estimate is favorable. Inspect mechanisms.json and component-evidence.json for actual activity and changed actions; untriggered components have no identified necessity even if timing differs.

Report paired-comparisons.json with_drain_ratio alongside foreground time. mechanisms.json contains p50/p99 of individual object reads, CPU, RSS and copying for every run. In paced replay it also reports block arrival-to-issue and arrival-to-completion p99, including loader backlog; these are not inference TTFT. segments.json partitions time by request-index quarter, including boundary idle gaps; quarters are not independent replication units. interactions.json is an exploratory four-cell comparison, not a full RobustBenefit test.

Foreground timing excludes initialization and post-run verification. Copy payload is not physical wire/disk traffic. Logical cache domains are not physical GPUs. Public traces preserve block identity/order with synthetic normalized bytes; saturated replay is not full inference or the original concurrency. Small-n development/supplementary runs do not support confirmatory claims. Negative and uncertain results are retained.
