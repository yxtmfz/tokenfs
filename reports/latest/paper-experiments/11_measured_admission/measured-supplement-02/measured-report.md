# Measured-policy evidence

Analysis: descriptive supplement (small n; no confirmatory claim). Recorded stage: confirmation. Batch: measured-supplement-02. All expected runs passed audit.

Time ratio = AURA-adaptive/reference; less than one is faster. Actual throughput is logical MiB / outer wall time.

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Reference | n | Time ratio [95% CI] | Holm p | Verdict |
|---|---:|---:|---:|---:|---|---|---:|---|---:|---|
| mixed_fit | 8 | 384 | 2 | 256 | False | RecentLFU-admit | 3 | 1.0020 [0.9849, 1.0160] | 1 | uncertain |
| stable | 4 | 4096 | 1 | 128 | False | LFU-equal | 3 | 0.8772 [0.8655, 0.8900] | 1 | uncertain |
| stable | 4 | 4096 | 1 | 128 | False | RecentLFU-admit | 3 | 0.9926 [0.9827, 1.0041] | 1 | uncertain |
| mixed_fit | 32 | 384 | 2 | 128 | False | LFU-equal | 3 | 0.9214 [0.9120, 0.9319] | 1 | uncertain |
| mixed_fit | 32 | 384 | 2 | 128 | False | RecentLFU-admit | 3 | 1.0182 [0.9892, 1.0644] | 1 | uncertain |
| shift | 8 | 384 | 2 | 64 | False | RecentLFU-admit | 3 | 0.8834 [0.8664, 0.9113] | 1 | uncertain |
| mooncake_conversation | 16 | 1024 | 1 | 128 | True | LFU-equal | 3 | 0.9901 [0.9858, 0.9946] | 1 | uncertain |
| mooncake_conversation | 16 | 1024 | 1 | 128 | True | RecentLFU-admit | 3 | 0.9893 [0.9831, 0.9931] | 1 | uncertain |
| shift | 8 | 384 | 2 | 256 | False | RecentLFU-admit | 3 | 0.7385 [0.7256, 0.7474] | 1 | uncertain |
| mixed_fit | 16 | 384 | 2 | 128 | False | LFU-equal | 3 | 0.9363 [0.9181, 0.9714] | 1 | uncertain |
| mixed_fit | 16 | 384 | 2 | 128 | False | RecentLFU-admit | 3 | 1.0207 [0.9854, 1.0498] | 1 | uncertain |
| shift | 4 | 4096 | 1 | 128 | False | LFU-equal | 3 | 0.6160 [0.5726, 0.6453] | 1 | uncertain |
| shift | 4 | 4096 | 1 | 128 | False | RecentLFU-admit | 3 | 0.9499 [0.8988, 0.9772] | 1 | uncertain |
| mooncake_toolagent | 16 | 1024 | 1 | 128 | True | LFU-equal | 3 | 1.0167 [0.9978, 1.0381] | 1 | uncertain |
| mooncake_toolagent | 16 | 1024 | 1 | 128 | True | RecentLFU-admit | 3 | 1.0072 [1.0059, 1.0083] | 1 | uncertain |
| stable | 32 | 384 | 2 | 128 | False | LFU-equal | 3 | 1.0058 [1.0028, 1.0088] | 1 | uncertain |
| stable | 32 | 384 | 2 | 128 | False | RecentLFU-admit | 3 | 1.0118 [0.9960, 1.0201] | 1 | uncertain |
| stable | 16 | 384 | 2 | 128 | False | LFU-equal | 3 | 1.0087 [0.9975, 1.0222] | 1 | uncertain |
| stable | 16 | 384 | 2 | 128 | False | RecentLFU-admit | 3 | 1.0361 [1.0082, 1.0808] | 1 | uncertain |
| mixed_fit | 8 | 384 | 2 | 64 | False | RecentLFU-admit | 3 | 1.0108 [0.9946, 1.0325] | 1 | uncertain |

## Absolute performance and resource cost

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Strategy | n | Mean wall s | Mean MiB/s | Copied MiB | Daemon CPU s | Peak RSS KiB |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| mixed_fit | 8 | 384 | 2 | 256 | False | RecentLFU-admit | 3 | 22.3614 | 85.391 | 27.33 | 4.150 | 12566.7 |
| mixed_fit | 8 | 384 | 2 | 256 | False | AURA-adaptive | 3 | 22.4053 | 85.225 | 29.33 | 4.167 | 12570.7 |
| stable | 4 | 4096 | 1 | 128 | False | LFU-equal | 3 | 40.4703 | 101.233 | 895.00 | 19.513 | 13320.0 |
| stable | 4 | 4096 | 1 | 128 | False | RecentLFU-admit | 3 | 35.7623 | 114.535 | 4.00 | 13.287 | 9922.7 |
| stable | 4 | 4096 | 1 | 128 | False | AURA-adaptive | 3 | 35.4974 | 115.399 | 4.00 | 13.127 | 10009.3 |
| mixed_fit | 32 | 384 | 2 | 128 | False | LFU-equal | 3 | 20.6884 | 92.301 | 966.00 | 9.417 | 12570.7 |
| mixed_fit | 32 | 384 | 2 | 128 | False | RecentLFU-admit | 3 | 18.7259 | 102.002 | 92.00 | 4.487 | 12122.7 |
| mixed_fit | 32 | 384 | 2 | 128 | False | AURA-adaptive | 3 | 19.0631 | 100.174 | 100.00 | 4.667 | 12144.0 |
| shift | 8 | 384 | 2 | 64 | False | RecentLFU-admit | 3 | 7.3649 | 104.292 | 32.00 | 2.447 | 12578.7 |
| shift | 8 | 384 | 2 | 64 | False | AURA-adaptive | 3 | 6.5073 | 118.084 | 32.00 | 2.173 | 12152.0 |
| mooncake_conversation | 16 | 1024 | 1 | 128 | True | LFU-equal | 3 | 16.3053 | 62.876 | 1.00 | 3.543 | 10448.0 |
| mooncake_conversation | 16 | 1024 | 1 | 128 | True | RecentLFU-admit | 3 | 16.3198 | 62.821 | 1.00 | 3.750 | 10088.0 |
| mooncake_conversation | 16 | 1024 | 1 | 128 | True | AURA-adaptive | 3 | 16.1458 | 63.509 | 1.00 | 3.623 | 9774.7 |
| shift | 8 | 384 | 2 | 256 | False | RecentLFU-admit | 3 | 9.1581 | 83.869 | 20.67 | 2.437 | 12150.7 |
| shift | 8 | 384 | 2 | 256 | False | AURA-adaptive | 3 | 6.7631 | 113.576 | 32.00 | 2.443 | 11938.7 |
| mixed_fit | 16 | 384 | 2 | 128 | False | LFU-equal | 3 | 23.0014 | 83.016 | 1337.33 | 10.463 | 12804.0 |
| mixed_fit | 16 | 384 | 2 | 128 | False | RecentLFU-admit | 3 | 21.0983 | 90.517 | 70.00 | 4.267 | 12144.0 |
| mixed_fit | 16 | 384 | 2 | 128 | False | AURA-adaptive | 3 | 21.5352 | 88.683 | 88.67 | 4.597 | 12357.3 |
| shift | 4 | 4096 | 1 | 128 | False | LFU-equal | 3 | 54.5968 | 75.040 | 2219.33 | 28.207 | 13562.7 |
| shift | 4 | 4096 | 1 | 128 | False | RecentLFU-admit | 3 | 35.4016 | 115.705 | 17.00 | 13.320 | 10518.7 |
| shift | 4 | 4096 | 1 | 128 | False | AURA-adaptive | 3 | 33.6604 | 121.915 | 16.00 | 12.190 | 10528.0 |
| mooncake_toolagent | 16 | 1024 | 1 | 128 | True | LFU-equal | 3 | 13.6080 | 75.762 | 46.33 | 3.630 | 11802.7 |
| mooncake_toolagent | 16 | 1024 | 1 | 128 | True | RecentLFU-admit | 3 | 13.7545 | 75.161 | 27.67 | 3.770 | 10374.7 |
| mooncake_toolagent | 16 | 1024 | 1 | 128 | True | AURA-adaptive | 3 | 13.8547 | 74.624 | 27.67 | 3.867 | 11300.0 |
| stable | 32 | 384 | 2 | 128 | False | LFU-equal | 3 | 6.0468 | 127.049 | 38.67 | 2.400 | 12152.0 |
| stable | 32 | 384 | 2 | 128 | False | RecentLFU-admit | 3 | 6.0103 | 127.812 | 24.67 | 2.330 | 12364.0 |
| stable | 32 | 384 | 2 | 128 | False | AURA-adaptive | 3 | 6.0819 | 126.325 | 24.67 | 2.303 | 12365.3 |
| stable | 16 | 384 | 2 | 128 | False | LFU-equal | 3 | 5.9987 | 128.038 | 40.67 | 2.413 | 12365.3 |
| stable | 16 | 384 | 2 | 128 | False | RecentLFU-admit | 3 | 5.8443 | 131.593 | 23.33 | 2.203 | 12364.0 |
| stable | 16 | 384 | 2 | 128 | False | AURA-adaptive | 3 | 6.0520 | 126.947 | 23.33 | 2.317 | 12365.3 |
| mixed_fit | 8 | 384 | 2 | 64 | False | RecentLFU-admit | 3 | 22.5081 | 84.834 | 63.33 | 4.380 | 12144.0 |
| mixed_fit | 8 | 384 | 2 | 64 | False | AURA-adaptive | 3 | 22.7494 | 83.932 | 108.00 | 4.710 | 12585.3 |

## Interpretation

The primary family comprises LRU, LFU and RecentLFU comparisons across the scenes in this batch; other families are per-component. Intervals are unadjusted paired bootstrap intervals; p-values use Holm correction within each family. No component is necessary merely because its point estimate is favorable. Inspect mechanisms.json and component-evidence.json for actual activity and changed actions; untriggered components have no identified necessity even if timing differs.

Report paired-comparisons.json with_drain_ratio alongside foreground time. mechanisms.json contains p50/p99 of individual object reads, CPU, RSS and copying for every run. In paced replay it also reports block arrival-to-issue and arrival-to-completion p99, including loader backlog; these are not inference TTFT. segments.json partitions time by request-index quarter, including boundary idle gaps; quarters are not independent replication units. interactions.json is an exploratory four-cell comparison, not a full RobustBenefit test.

Foreground timing excludes initialization and post-run verification. Copy payload is not physical wire/disk traffic. Logical cache domains are not physical GPUs. Public traces preserve block identity/order with synthetic normalized bytes; saturated replay is not full inference or the original concurrency. Small-n development/supplementary runs do not support confirmatory claims. Negative and uncertain results are retained.
