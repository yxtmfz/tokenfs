# Read-tail / H factorial diagnostic

吞吐为两轮总字节/总时间；p99为两轮各自p99的中位数。正的吞吐变化、p99降低率表示改善。不是最终HPJ四表。

|负载|比较|吞吐(处理/对照 MiB/s)|吞吐变化%|p99(处理/对照 ms)|p99降低%|双指标改善|
|---|---|---:|---:|---:|---:|---:|
|moving_shared|Full / NoTail|344.894 / 337.506|+2.189|27.003 / 27.777|+2.789|2/2|
|moving_shared|NoHotspot / NoHotspotNoTail|346.729 / 344.856|+0.543|27.080 / 27.465|+1.402|2/2|
|moving_shared|Full / NoHotspot|344.894 / 346.729|-0.529|27.003 / 27.080|+0.286|0/2|
|moving_shared|NoTail / NoHotspotNoTail|337.506 / 344.856|-2.131|27.777 / 27.465|-1.136|0/2|
|public_toolagent|Full / NoTail|86.897 / 86.443|+0.525|29.763 / 28.528|-4.327|0/2|
|public_toolagent|NoHotspot / NoHotspotNoTail|86.158 / 84.879|+1.507|29.406 / 29.009|-1.370|0/2|
|public_toolagent|Full / NoHotspot|86.897 / 86.158|+0.858|29.763 / 29.406|-1.211|1/2|
|public_toolagent|NoTail / NoHotspotNoTail|86.443 / 84.879|+1.842|28.528 / 29.009|+1.658|2/2|
