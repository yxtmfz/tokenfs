# 热点估值修复：小规模开发回归

24次测速，27,648次请求。两个已分析输入，各两轮反向顺序。速率为总逻辑字节/总墙钟时间；汇总p99是两次运行p99的中位数，不是合并请求p99。吞吐提升为正、p99变化为负才有利。前三表均为完整版只关闭一项功能的单开关消融。

## 1. 热点估值消融

|输入|新版 MiB/s|对照 MiB/s|吞吐提升|新版p99 ms|对照p99 ms|p99变化|严格通过|
|---|---:|---:|---:|---:|---:|---:|---:|
|moving_shared|356.065|350.507|+1.586%|27.296|27.084|+0.783%|0/2|
|public_toolagent|89.248|90.655|-1.552%|28.703|28.310|+1.391%|0/2|

## 2. 跨逻辑域放置消融

|输入|新版 MiB/s|对照 MiB/s|吞吐提升|新版p99 ms|对照p99 ms|p99变化|严格通过|
|---|---:|---:|---:|---:|---:|---:|---:|
|moving_shared|356.065|354.586|+0.417%|27.296|25.811|+5.754%|0/2|
|public_toolagent|89.248|88.213|+1.173%|28.703|28.678|+0.087%|0/2|

## 3. 联合准入消融

|输入|新版 MiB/s|对照 MiB/s|吞吐提升|新版p99 ms|对照p99 ms|p99变化|严格通过|
|---|---:|---:|---:|---:|---:|---:|---:|
|moving_shared|356.065|345.106|+3.176%|27.296|26.771|+1.961%|0/2|
|public_toolagent|89.248|86.328|+3.383%|28.703|29.487|-2.657%|2/2|

## 4. 整体对共享SIEVE

|输入|新版 MiB/s|对照 MiB/s|吞吐提升|新版p99 ms|对照p99 ms|p99变化|严格通过|
|---|---:|---:|---:|---:|---:|---:|---:|
|moving_shared|356.065|352.129|+1.118%|27.296|26.577|+2.706%|0/2|
|public_toolagent|89.248|73.849|+20.852%|28.703|32.151|-10.722%|2/2|

## 补充：新旧完整版同批对照

|输入|新版 MiB/s|对照 MiB/s|吞吐提升|新版p99 ms|对照p99 ms|p99变化|严格通过|
|---|---:|---:|---:|---:|---:|---:|---:|
|moving_shared|356.065|352.371|+1.048%|27.296|26.945|+1.304%|0/2|
|public_toolagent|89.248|89.412|-0.183%|28.703|28.689|+0.051%|0/2|

## 全部逐轮结果

|输入/轮次|对照|吞吐变化|p99变化|严格通过|
|---|---|---:|---:|---|
|moving_shared-73501-r1|NoHotspot|-2.129%|+1.443%|False|
|moving_shared-73501-r1|NoAffinity|-1.824%|+2.904%|False|
|moving_shared-73501-r1|NoJoint|+0.301%|+2.840%|False|
|moving_shared-73501-r1|PoolSIEVE1|-4.416%|+4.617%|False|
|moving_shared-73501-r1|OldFull|+0.623%|+0.244%|False|
|public_toolagent-73602-r1|NoHotspot|-0.371%|+0.391%|False|
|public_toolagent-73602-r1|NoAffinity|+1.122%|+0.157%|False|
|public_toolagent-73602-r1|NoJoint|+3.041%|-2.092%|True|
|public_toolagent-73602-r1|PoolSIEVE1|+21.055%|-11.539%|True|
|public_toolagent-73602-r1|OldFull|+0.611%|-0.808%|False|
|moving_shared-73501-r2|NoHotspot|+5.502%|+0.135%|False|
|moving_shared-73501-r2|NoAffinity|+2.780%|+8.748%|False|
|moving_shared-73501-r2|NoJoint|+6.206%|+1.101%|False|
|moving_shared-73501-r2|PoolSIEVE1|+6.952%|+0.876%|False|
|moving_shared-73501-r2|OldFull|+1.497%|+2.379%|False|
|public_toolagent-73602-r2|NoHotspot|-2.728%|+2.404%|False|
|public_toolagent-73602-r2|NoAffinity|+1.224%|+0.017%|False|
|public_toolagent-73602-r2|NoJoint|+3.723%|-3.212%|True|
|public_toolagent-73602-r2|PoolSIEVE1|+20.649%|-9.895%|True|
|public_toolagent-73602-r2|OldFull|-0.973%|+0.919%|False|

## 复制与远端读取

|输入|版本|两轮远端MiB|两轮复制次数|两轮CPU秒|
|---|---|---:|---:|---:|
|moving_shared|Full|312|58|5.39|
|moving_shared|NoHotspot|316|56|5.64|
|moving_shared|NoAffinity|376|70|4.98|
|moving_shared|NoJoint|336|70|5.70|
|moving_shared|PoolSIEVE1|296|148|5.78|
|moving_shared|OldFull|290|133|5.83|
|public_toolagent|Full|3508|80|10.59|
|public_toolagent|NoHotspot|3496|56|10.09|
|public_toolagent|NoAffinity|3604|68|10.34|
|public_toolagent|NoJoint|3636|302|11.97|
|public_toolagent|PoolSIEVE1|4292|2146|22.32|
|public_toolagent|OldFull|3508|80|10.59|

仅cn7上的逻辑消费者域与cn13 NVMe/TCP；不代表物理GPU或推理加速。本轮使用已检查数据进行开发，不覆盖报告66，也不代表独立确认、显著性或全部工作负载。
