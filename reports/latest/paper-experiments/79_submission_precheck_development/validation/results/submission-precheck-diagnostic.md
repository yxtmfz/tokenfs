# Submission-precheck diagnostic: Full / NoSubmitPrecheck

The admission formulas are unchanged; the treatment may reject a submission at the current observation rather than let a later queued task reconsider it. This diagnostic is separate from the four primary policy tables.

|负载|吞吐(完整/对照 MiB/s)|吞吐变化%|p99(完整/对照 ms)|p99降低%|双指标改善|完整验收|
|---|---:|---:|---:|---:|---:|---:|
|moving_shared|350.032 / 345.821|+1.218|26.460 / 26.583|+0.463|2/2|2/2|
|public_toolagent|87.968 / 87.905|+0.072|27.971 / 28.653|+2.380|1/2|1/2|
