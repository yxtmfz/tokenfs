# Measured-policy evidence

Stage: confirmation. Batch: measured-confirm-02. All expected runs passed audit.

Time ratio = AURA-adaptive/reference; less than one is faster. Actual throughput is logical MiB / outer wall time.

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Reference | n | Time ratio [95% CI] | Holm p | Verdict |
|---|---:|---:|---:|---:|---|---|---:|---|---:|---|
| uniform | 8 | 384 | 2 | 128 | False | RemoteOnly | 12 | 1.0223 [1.0092, 1.0346] | 0.0083008 | slower |
| uniform | 8 | 384 | 2 | 128 | False | LRU-equal | 12 | 0.9267 [0.9134, 0.9386] | 0.010254 | faster |
| uniform | 8 | 384 | 2 | 128 | False | LFU-equal | 12 | 0.9301 [0.9210, 0.9388] | 0.010254 | faster |
| uniform | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 12 | 1.0021 [0.9901, 1.0143] | 1 | uncertain |
| uniform | 8 | 384 | 2 | 128 | False | AURA-no-admission | 12 | 0.9099 [0.9027, 0.9163] | 0.0014648 | faster |
| uniform | 8 | 384 | 2 | 128 | False | AURA-no-cost | 12 | 0.9995 [0.9933, 1.0058] | 1 | uncertain |
| uniform | 8 | 384 | 2 | 128 | False | AURA-no-shift | 12 | 1.0024 [0.9941, 1.0111] | 0.61572 | uncertain |
| stable | 8 | 384 | 2 | 128 | False | RemoteOnly | 12 | 0.5857 [0.5804, 0.5908] | 0.003418 | faster |
| stable | 8 | 384 | 2 | 128 | False | LRU-equal | 12 | 0.8839 [0.8618, 0.9065] | 0.010254 | faster |
| stable | 8 | 384 | 2 | 128 | False | LFU-equal | 12 | 0.9190 [0.9041, 0.9328] | 0.010254 | faster |
| stable | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 12 | 0.9985 [0.9877, 1.0084] | 1 | uncertain |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-admission | 12 | 0.8361 [0.8217, 0.8492] | 0.0014648 | faster |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-value | 12 | 0.9962 [0.9815, 1.0126] | 1 | uncertain |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-joint | 12 | 0.7575 [0.7465, 0.7682] | 0.00097656 | faster |
| stable | 8 | 384 | 2 | 128 | False | AURA-synchronous | 12 | 0.9939 [0.9792, 1.0107] | 0.48535 | uncertain |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-shift | 12 | 0.9915 [0.9809, 1.0013] | 0.31543 | uncertain |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-aging | 12 | 0.9939 [0.9776, 1.0113] | 0.51074 | uncertain |
| shift | 8 | 384 | 2 | 128 | False | RemoteOnly | 12 | 0.6750 [0.6609, 0.6877] | 0.003418 | faster |
| shift | 8 | 384 | 2 | 128 | False | LRU-equal | 12 | 0.9149 [0.8972, 0.9350] | 0.010254 | faster |
| shift | 8 | 384 | 2 | 128 | False | LFU-equal | 12 | 0.7423 [0.7280, 0.7575] | 0.010254 | faster |
| shift | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 12 | 0.8010 [0.7859, 0.8167] | 0.010254 | faster |
| shift | 8 | 384 | 2 | 128 | False | AURA-no-aging | 12 | 0.7331 [0.7204, 0.7477] | 0.00097656 | faster |
| shift | 8 | 384 | 2 | 128 | False | AURA-no-shift | 12 | 0.7907 [0.7774, 0.8065] | 0.0014648 | faster |
| shift | 8 | 384 | 2 | 128 | False | AURA-no-cost | 12 | 1.0056 [0.9924, 1.0145] | 1 | uncertain |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RemoteOnly | 12 | 0.8750 [0.8547, 0.8926] | 0.003418 | faster |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LRU-equal | 12 | 0.9379 [0.9218, 0.9532] | 0.010254 | faster |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LFU-equal | 12 | 0.9959 [0.9872, 1.0044] | 1 | uncertain |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 12 | 1.0180 [1.0033, 1.0402] | 0.19922 | uncertain |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | AURA-no-cost | 12 | 1.0038 [0.9951, 1.0121] | 1 | uncertain |
| mixed_fit | 8 | 384 | 2 | 128 | False | RemoteOnly | 12 | 0.9656 [0.9546, 0.9761] | 0.003418 | faster |
| mixed_fit | 8 | 384 | 2 | 128 | False | LRU-equal | 12 | 0.9264 [0.9155, 0.9361] | 0.010254 | faster |
| mixed_fit | 8 | 384 | 2 | 128 | False | LFU-equal | 12 | 0.9305 [0.9211, 0.9388] | 0.010254 | faster |
| mixed_fit | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 12 | 1.0022 [0.9870, 1.0148] | 1 | uncertain |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-no-size | 12 | 0.9942 [0.9880, 0.9997] | 0.097656 | uncertain |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-no-cost | 12 | 1.0054 [0.9921, 1.0182] | 1 | uncertain |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-no-value | 12 | 0.9947 [0.9886, 1.0007] | 0.41162 | uncertain |
| scan | 8 | 384 | 2 | 128 | False | RemoteOnly | 12 | 0.6720 [0.6604, 0.6815] | 0.003418 | faster |
| scan | 8 | 384 | 2 | 128 | False | LRU-equal | 12 | 0.8918 [0.8758, 0.9048] | 0.010254 | faster |
| scan | 8 | 384 | 2 | 128 | False | LFU-equal | 12 | 0.9268 [0.9096, 0.9417] | 0.010254 | faster |
| scan | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 12 | 1.0004 [0.9827, 1.0172] | 1 | uncertain |
| scan | 8 | 384 | 2 | 128 | False | AURA-no-admission | 12 | 0.9191 [0.8960, 0.9418] | 0.0014648 | faster |
| scan | 8 | 384 | 2 | 128 | False | AURA-no-value | 12 | 0.9951 [0.9747, 1.0128] | 1 | uncertain |
| scan | 8 | 384 | 2 | 128 | False | AURA-no-joint | 12 | 0.8359 [0.8202, 0.8494] | 0.00097656 | faster |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RemoteOnly | 12 | 0.9808 [0.9753, 0.9851] | 0.003418 | faster |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LRU-equal | 12 | 0.9942 [0.9851, 1.0019] | 1 | uncertain |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LFU-equal | 12 | 0.9913 [0.9844, 0.9968] | 0.070312 | uncertain |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 12 | 1.0007 [0.9960, 1.0056] | 1 | uncertain |

## Absolute performance and resource cost

| Scenario | Quota MiB | Requests | Base MiB | Window | Paced | Strategy | n | Mean wall s | Mean MiB/s | Copied MiB | Daemon CPU s | Peak RSS KiB |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| uniform | 8 | 384 | 2 | 128 | False | RemoteOnly | 12 | 10.0610 | 76.347 | 0.00 | 1.978 | 11672.0 |
| uniform | 8 | 384 | 2 | 128 | False | LRU-equal | 12 | 11.0995 | 69.212 | 593.33 | 5.742 | 12449.0 |
| uniform | 8 | 384 | 2 | 128 | False | LFU-equal | 12 | 11.0575 | 69.465 | 594.17 | 5.697 | 12601.0 |
| uniform | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 12 | 10.2641 | 74.846 | 61.17 | 2.724 | 12216.3 |
| uniform | 8 | 384 | 2 | 128 | False | AURA-adaptive | 12 | 10.2854 | 74.687 | 57.83 | 2.696 | 12436.3 |
| uniform | 8 | 384 | 2 | 128 | False | AURA-no-admission | 12 | 11.3028 | 67.955 | 685.17 | 6.537 | 12562.3 |
| uniform | 8 | 384 | 2 | 128 | False | AURA-no-cost | 12 | 10.2901 | 74.646 | 61.17 | 2.750 | 12654.0 |
| uniform | 8 | 384 | 2 | 128 | False | AURA-no-shift | 12 | 10.2612 | 74.865 | 58.00 | 2.664 | 12386.3 |
| stable | 8 | 384 | 2 | 128 | False | RemoteOnly | 12 | 10.0238 | 76.631 | 0.00 | 1.975 | 11831.7 |
| stable | 8 | 384 | 2 | 128 | False | LRU-equal | 12 | 6.6460 | 115.732 | 105.00 | 2.743 | 12415.3 |
| stable | 8 | 384 | 2 | 128 | False | LFU-equal | 12 | 6.3889 | 120.262 | 78.17 | 2.629 | 12415.0 |
| stable | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 12 | 5.8796 | 130.656 | 8.33 | 2.105 | 12364.7 |
| stable | 8 | 384 | 2 | 128 | False | AURA-adaptive | 12 | 5.8706 | 130.844 | 8.50 | 2.044 | 12418.0 |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-admission | 12 | 7.0240 | 109.438 | 189.67 | 3.601 | 12478.0 |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-value | 12 | 5.8942 | 130.385 | 8.33 | 2.069 | 12204.7 |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-joint | 12 | 7.7523 | 99.147 | 253.50 | 3.935 | 12424.7 |
| stable | 8 | 384 | 2 | 128 | False | AURA-synchronous | 12 | 5.9082 | 130.087 | 8.33 | 1.962 | 11459.3 |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-shift | 12 | 5.9212 | 129.736 | 8.50 | 2.093 | 12228.0 |
| stable | 8 | 384 | 2 | 128 | False | AURA-no-aging | 12 | 5.9083 | 130.075 | 8.50 | 2.083 | 12258.0 |
| shift | 8 | 384 | 2 | 128 | False | RemoteOnly | 12 | 10.0518 | 76.411 | 0.00 | 2.007 | 11882.0 |
| shift | 8 | 384 | 2 | 128 | False | LRU-equal | 12 | 7.4209 | 103.637 | 156.33 | 3.245 | 12384.3 |
| shift | 8 | 384 | 2 | 128 | False | LFU-equal | 12 | 9.1431 | 84.050 | 368.33 | 4.359 | 12526.7 |
| shift | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 12 | 8.4712 | 90.677 | 33.17 | 2.458 | 12054.7 |
| shift | 8 | 384 | 2 | 128 | False | AURA-adaptive | 12 | 6.7878 | 113.254 | 33.00 | 2.403 | 12484.3 |
| shift | 8 | 384 | 2 | 128 | False | AURA-no-aging | 12 | 9.2552 | 83.000 | 16.50 | 2.320 | 12367.3 |
| shift | 8 | 384 | 2 | 128 | False | AURA-no-shift | 12 | 8.5818 | 89.524 | 31.50 | 2.454 | 12389.0 |
| shift | 8 | 384 | 2 | 128 | False | AURA-no-cost | 12 | 6.7483 | 113.851 | 32.83 | 2.439 | 12418.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RemoteOnly | 12 | 29.6422 | 69.095 | 0.00 | 7.157 | 9241.7 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LRU-equal | 12 | 27.6600 | 74.084 | 203.25 | 8.463 | 13391.0 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | LFU-equal | 12 | 26.0664 | 78.716 | 93.00 | 7.637 | 13063.3 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 12 | 25.5317 | 80.570 | 50.25 | 7.298 | 11872.7 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | AURA-adaptive | 12 | 25.9573 | 79.028 | 49.50 | 7.613 | 11364.3 |
| mooncake_toolagent | 16 | 2048 | 1 | 128 | False | AURA-no-cost | 12 | 25.8614 | 79.328 | 50.25 | 7.627 | 12114.3 |
| mixed_fit | 8 | 384 | 2 | 128 | False | RemoteOnly | 12 | 23.3503 | 82.206 | 0.00 | 3.697 | 11953.3 |
| mixed_fit | 8 | 384 | 2 | 128 | False | LRU-equal | 12 | 24.3377 | 78.866 | 1512.17 | 11.690 | 12996.3 |
| mixed_fit | 8 | 384 | 2 | 128 | False | LFU-equal | 12 | 24.2336 | 79.217 | 1508.50 | 11.560 | 12799.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 12 | 22.5016 | 85.320 | 41.50 | 4.263 | 13065.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-adaptive | 12 | 22.5479 | 85.145 | 59.17 | 4.212 | 12699.7 |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-no-size | 12 | 22.6765 | 84.643 | 58.17 | 4.344 | 12758.0 |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-no-cost | 12 | 22.4309 | 85.600 | 50.00 | 4.202 | 12724.3 |
| mixed_fit | 8 | 384 | 2 | 128 | False | AURA-no-value | 12 | 22.6652 | 84.685 | 55.83 | 4.347 | 12622.7 |
| scan | 8 | 384 | 2 | 128 | False | RemoteOnly | 12 | 10.0656 | 76.307 | 0.00 | 2.017 | 11614.0 |
| scan | 8 | 384 | 2 | 128 | False | LRU-equal | 12 | 7.5854 | 101.280 | 200.00 | 3.385 | 12467.0 |
| scan | 8 | 384 | 2 | 128 | False | LFU-equal | 12 | 7.2982 | 105.251 | 176.00 | 3.288 | 12360.7 |
| scan | 8 | 384 | 2 | 128 | False | RecentLFU-admit | 12 | 6.7614 | 113.616 | 8.00 | 2.126 | 12087.0 |
| scan | 8 | 384 | 2 | 128 | False | AURA-adaptive | 12 | 6.7656 | 113.590 | 8.00 | 2.062 | 12257.3 |
| scan | 8 | 384 | 2 | 128 | False | AURA-no-admission | 12 | 7.3618 | 104.412 | 258.00 | 3.785 | 12398.7 |
| scan | 8 | 384 | 2 | 128 | False | AURA-no-value | 12 | 6.7980 | 113.006 | 8.00 | 2.101 | 12448.7 |
| scan | 8 | 384 | 2 | 128 | False | AURA-no-joint | 12 | 8.0920 | 94.936 | 288.00 | 4.119 | 12664.3 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RemoteOnly | 12 | 30.0008 | 68.270 | 0.00 | 7.341 | 10044.7 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LRU-equal | 12 | 29.5968 | 69.211 | 10.67 | 7.002 | 10619.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | LFU-equal | 12 | 29.6825 | 69.008 | 10.42 | 7.088 | 10961.0 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | RecentLFU-admit | 12 | 29.4044 | 69.653 | 1.00 | 7.327 | 10835.3 |
| mooncake_conversation | 16 | 2048 | 1 | 128 | False | AURA-adaptive | 12 | 29.4236 | 69.607 | 1.00 | 7.343 | 10316.3 |

## Interpretation

The primary family comprises LRU, LFU and RecentLFU comparisons across the scenes in this batch; other families are per-component. Intervals are unadjusted paired bootstrap intervals; p-values use Holm correction within each family. No component is necessary merely because its point estimate is favorable. Inspect mechanisms.json and component-evidence.json for actual activity and changed actions; untriggered components have no identified necessity even if timing differs.

Report paired-comparisons.json with_drain_ratio alongside foreground time. mechanisms.json contains p50/p99 of individual object reads, CPU, RSS and copying for every run. In paced replay it also reports block arrival-to-issue and arrival-to-completion p99, including loader backlog; these are not inference TTFT. segments.json partitions time by request-index quarter, including boundary idle gaps; quarters are not independent replication units. interactions.json is an exploratory four-cell comparison, not a full RobustBenefit test.

Foreground timing excludes initialization and post-run verification. Copy payload is not physical wire/disk traffic. Logical cache domains are not physical GPUs. Public traces preserve block identity/order with synthetic normalized bytes; saturated replay is not full inference or the original concurrency. Small-n development/supplementary runs do not support confirmatory claims. Negative and uncertain results are retained.
