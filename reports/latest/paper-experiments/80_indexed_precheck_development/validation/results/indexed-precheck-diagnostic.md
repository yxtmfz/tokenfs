# Indexed-precheck diagnostic: Full / NoIndexedPrecheck

Both arms use the same submission-time admission formulas; query indexes change their execution cost. Online timing/cost samples may still change actions. This diagnostic is separate from the four primary policy tables.

|负载|吞吐(完整/对照 MiB/s)|吞吐变化%|p99(完整/对照 ms)|p99降低%|双指标改善|完整验收|
|---|---:|---:|---:|---:|---:|---:|
|moving_shared|344.338 / 347.791|-0.993|26.698 / 26.733|+0.131|0/2|0/2|
|public_toolagent|89.185 / 88.458|+0.822|28.305 / 28.506|+0.704|0/2|0/2|
