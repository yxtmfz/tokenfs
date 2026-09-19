# Measured-policy evidence

Stage: development. Batch: measured-dev-02. All expected runs passed audit.

Time ratio = AURA-adaptive/reference; less than one is faster. Actual throughput is logical MiB / outer wall time.

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Reference | n | Time ratio [95% CI] | Holm p | Verdict |
|---|---:|---:|---:|---:|---|---|---:|---|---:|---|
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RemoteOnly | 1 | 0.9848 [unavailable] | unavailable | development / no confirmatory claim |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LRU-equal | 1 | 0.9853 [unavailable] | unavailable | development / no confirmatory claim |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LFU-equal | 1 | 0.9813 [unavailable] | unavailable | development / no confirmatory claim |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 1 | 1.0591 [unavailable] | unavailable | development / no confirmatory claim |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RemoteOnly | 1 | 0.9016 [unavailable] | unavailable | development / no confirmatory claim |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LRU-equal | 1 | 0.9381 [unavailable] | unavailable | development / no confirmatory claim |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LFU-equal | 1 | 0.9574 [unavailable] | unavailable | development / no confirmatory claim |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 1 | 0.9777 [unavailable] | unavailable | development / no confirmatory claim |

## Absolute performance and resource cost

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Strategy | n | Mean wall s | Mean MiB/s | Copied MiB | Daemon CPU s | Peak RSS KiB |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RemoteOnly | 1 | 29.9460 | 68.390 | 0.00 | 7.310 | 10088.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LRU-equal | 1 | 29.9303 | 68.426 | 1.00 | 7.200 | 10088.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LFU-equal | 1 | 30.0531 | 68.146 | 1.00 | 7.310 | 9732.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 1 | 27.8458 | 73.548 | 1.00 | 5.690 | 10088.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | AURA-adaptive | 1 | 29.4905 | 69.446 | 1.00 | 7.430 | 10088.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RemoteOnly | 1 | 30.1592 | 67.906 | 0.00 | 7.560 | 9448.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LRU-equal | 1 | 28.9839 | 70.660 | 188.00 | 8.300 | 11824.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LFU-equal | 1 | 28.4004 | 72.112 | 134.00 | 8.180 | 13308.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 1 | 27.8092 | 73.645 | 72.00 | 8.000 | 11764.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | AURA-adaptive | 1 | 27.1901 | 75.321 | 24.00 | 7.520 | 11208.0 |

## Interpretation

The primary family comprises LRU, LFU and RecentLFU comparisons across the scenes in this batch; other families are per-component. Intervals are unadjusted paired bootstrap intervals; p-values use Holm correction within each family. No component is necessary merely because its point estimate is favorable. Inspect mechanisms.json and component-evidence.json for actual activity and changed actions; untriggered components have no identified necessity even if timing differs.

Report paired-comparisons.json with_drain_ratio alongside foreground time. mechanisms.json contains p50/p99 of individual object reads, CPU, RSS and copying for every run. In paced replay it also reports block arrival-to-issue and arrival-to-completion p99, including loader backlog; these are not inference TTFT. segments.json partitions time by request-index quarter, including boundary idle gaps; quarters are not independent replication units. interactions.json is an exploratory four-cell comparison, not a full RobustBenefit test.

Foreground timing excludes initialization and post-run verification. Copy payload is not physical wire/disk traffic. Logical cache domains are not physical GPUs. Public traces preserve block identity/order with synthetic normalized bytes; saturated replay is not full inference or the original concurrency. Small-n development/supplementary runs do not support confirmatory claims. Negative and uncertain results are retained.
