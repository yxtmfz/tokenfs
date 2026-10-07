# Common read-path diagnostic: Full / NoRAMFirst

This is a separate implementation contrast; it is not one of the four primary policy tables.

|负载|吞吐(完整/对照 MiB/s)|吞吐变化%|p99(完整/对照 ms)|p99降低%|双指标改善|
|---|---:|---:|---:|---:|---:|
|moving_shared|351.549 / 352.546|-0.283|27.010 / 26.827|-0.686|1/2|
|public_toolagent|86.691 / 86.653|+0.044|29.677 / 29.380|-1.012|0/2|
