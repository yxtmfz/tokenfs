# 第74轮机制计数

所有字段按两轮求和；复制使用PROMOTE_READY/REPLICATE_READY事件计数，不能用仅测量策略记录的copy_cost_samples给SIEVE计数。

|场景|策略|远端MiB|完成复制|CPU s|规划快照|乐观拒绝|
|---|---|---:|---:|---:|---:|---:|
|moving_shared|Full|336|56|5.78|112|352|
|moving_shared|NoHotspot|336|56|5.42|112|352|
|moving_shared|NoAffinity|424|70|5.91|165|117|
|moving_shared|NoJoint|444|110|6.00|220|352|
|moving_shared|PoolSIEVE1|308|154|6.49|0|0|
|moving_shared|OldFull|312|146|6.35|300|14|
|public_toolagent|Full|3978|48|9.56|208|5511|
|public_toolagent|NoHotspot|4008|50|9.43|192|5610|
|public_toolagent|NoAffinity|3990|42|9.25|231|1806|
|public_toolagent|NoJoint|3930|222|10.51|444|5253|
|public_toolagent|PoolSIEVE1|4384|2192|22.71|0|0|
|public_toolagent|OldFull|3868|66|9.26|206|5406|
