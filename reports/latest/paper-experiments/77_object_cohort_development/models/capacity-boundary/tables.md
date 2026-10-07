# Capacity boundary diagnostic for frozen77 H

Frozen77 actual H headers, 4 capacities(12/18/24/48 MiB) × 10 known inputs × 4 arms =160 new model arms. Original retained-capacity model reused as explicit old-data mechanism reference; it is not fresh server data. Fixed storage-cost score=remote_reads*21ms + disk_hits*10.5ms + copies*8ms, with RAM service cost zero. This additive score ignores asynchronous overlap, control costs and real contention, so it is neither wall time nor throughput nor p99. Original24MiB primary acceptance unchanged; other capacities are boundary diagnostics only.

Every cell: remote reads / copies / fixed storage cost ms.

|Input|Global MiB|H|Full|NoH|NoP|NoJ|Full saving vs NoH ms|
|---|---:|---|---:|---:|---:|---:|---:|
| moving_shared-73501 | 12 | object_weighted | 115 / 42 / 4053.0 | 125 / 29 / 4054.0 | 141 / 47 / 4366.0 | 132 / 76 / 4503.5 | 1.0 |
| moving_shared-73501 | 12 | legacy_event_prior | 118 / 47 / 4124.5 | 125 / 29 / 4054.0 | 142 / 50 / 4400.5 | 136 / 130 / 4977.5 | -70.5 |
| moving_shared-73501 | 18 | object_weighted | 80 / 27 / 3565.5 | 86 / 26 / 3620.5 | 122 / 48 / 4174.5 | 110 / 57 / 4120.5 | 55.0 |
| moving_shared-73501 | 18 | legacy_event_prior | 87 / 54 / 3855.0 | 86 / 26 / 3620.5 | 124 / 52 / 4227.5 | 112 / 109 / 4557.5 | -234.5 |
| moving_shared-73501 | 24 | object_weighted | 79 / 29 / 3571.0 | 79 / 28 / 3563.0 | 101 / 38 / 3874.0 | 89 / 39 / 3756.0 | -8.0 |
| moving_shared-73501 | 24 | legacy_event_prior | 77 / 65 / 3838.0 | 79 / 28 / 3563.0 | 95 / 44 / 3859.0 | 99 / 97 / 4325.0 | -275.0 |
| moving_shared-73501 | 48 | object_weighted | 73 / 37 / 3572.0 | 73 / 37 / 3572.0 | 73 / 30 / 3516.0 | 73 / 37 / 3572.0 | 0.0 |
| moving_shared-73501 | 48 | legacy_event_prior | 62 / 61 / 3648.5 | 73 / 37 / 3572.0 | 71 / 51 / 3663.0 | 75 / 75 / 3897.0 | -76.5 |
| moving_shared-73502 | 12 | object_weighted | 122 / 49 / 4245.5 | 129 / 30 / 4167.0 | 158 / 53 / 4655.5 | 145 / 84 / 4767.0 | -78.5 |
| moving_shared-73502 | 12 | legacy_event_prior | 124 / 55 / 4314.5 | 129 / 30 / 4167.0 | 162 / 60 / 4753.5 | 157 / 148 / 5405.0 | -147.5 |
| moving_shared-73502 | 18 | object_weighted | 84 / 26 / 3662.5 | 92 / 26 / 3746.5 | 134 / 50 / 4379.5 | 108 / 50 / 4106.5 | 84.0 |
| moving_shared-73502 | 18 | legacy_event_prior | 98 / 63 / 4105.5 | 92 / 26 / 3746.5 | 120 / 50 / 4232.5 | 108 / 102 / 4522.5 | -359.0 |
| moving_shared-73502 | 24 | object_weighted | 83 / 28 / 3668.0 | 85 / 28 / 3689.0 | 120 / 51 / 4240.5 | 101 / 46 / 4001.0 | 21.0 |
| moving_shared-73502 | 24 | legacy_event_prior | 76 / 64 / 3882.5 | 85 / 28 / 3689.0 | 112 / 55 / 4188.5 | 88 / 85 / 4176.5 | -193.5 |
| moving_shared-73502 | 48 | object_weighted | 83 / 40 / 3764.0 | 83 / 40 / 3764.0 | 80 / 30 / 3652.5 | 83 / 40 / 3764.0 | 0.0 |
| moving_shared-73502 | 48 | legacy_event_prior | 65 / 65 / 3775.0 | 83 / 40 / 3764.0 | 81 / 64 / 3935.0 | 74 / 74 / 3941.5 | -11.0 |
| moving_shared-73503 | 12 | object_weighted | 120 / 50 / 4138.0 | 127 / 28 / 4035.5 | 149 / 49 / 4434.5 | 139 / 82 / 4593.5 | -102.5 |
| moving_shared-73503 | 12 | legacy_event_prior | 122 / 59 / 4231.0 | 127 / 28 / 4035.5 | 150 / 51 / 4461.0 | 141 / 137 / 5054.5 | -195.5 |
| moving_shared-73503 | 18 | object_weighted | 78 / 25 / 3497.0 | 85 / 25 / 3570.5 | 135 / 53 / 4319.5 | 111 / 57 / 4099.5 | 73.5 |
| moving_shared-73503 | 18 | legacy_event_prior | 85 / 53 / 3794.5 | 85 / 25 / 3570.5 | 135 / 58 / 4359.5 | 122 / 119 / 4711.0 | -224.0 |
| moving_shared-73503 | 24 | object_weighted | 78 / 28 / 3521.0 | 79 / 28 / 3531.5 | 114 / 45 / 4035.0 | 98 / 47 / 3883.0 | 10.5 |
| moving_shared-73503 | 24 | legacy_event_prior | 78 / 63 / 3801.0 | 79 / 28 / 3531.5 | 114 / 53 / 4099.0 | 107 / 104 / 4433.5 | -269.5 |
| moving_shared-73503 | 48 | object_weighted | 78 / 40 / 3617.0 | 79 / 40 / 3627.5 | 71 / 30 / 3463.5 | 78 / 40 / 3617.0 | 10.5 |
| moving_shared-73503 | 48 | legacy_event_prior | 60 / 60 / 3588.0 | 79 / 40 / 3627.5 | 77 / 54 / 3718.5 | 73 / 73 / 3828.5 | 39.5 |
| moving_shared-74801 | 12 | object_weighted | 112 / 41 / 3940.0 | 127 / 30 / 4009.5 | 164 / 55 / 4598.0 | 165 / 103 / 4992.5 | 69.5 |
| moving_shared-74801 | 12 | legacy_event_prior | 114 / 44 / 3985.0 | 127 / 30 / 4009.5 | 160 / 56 / 4564.0 | 162 / 157 / 5393.0 | 24.5 |
| moving_shared-74801 | 18 | object_weighted | 86 / 27 / 3555.0 | 93 / 27 / 3628.5 | 130 / 45 / 4161.0 | 136 / 77 / 4480.0 | 73.5 |
| moving_shared-74801 | 18 | legacy_event_prior | 92 / 55 / 3842.0 | 93 / 27 / 3628.5 | 130 / 54 / 4233.0 | 126 / 124 / 4751.0 | -213.5 |
| moving_shared-74801 | 24 | object_weighted | 84 / 28 / 3542.0 | 84 / 28 / 3542.0 | 107 / 36 / 3847.5 | 110 / 54 / 4023.0 | 0.0 |
| moving_shared-74801 | 24 | legacy_event_prior | 79 / 68 / 3809.5 | 84 / 28 / 3542.0 | 105 / 48 / 3922.5 | 111 / 111 / 4489.5 | -267.5 |
| moving_shared-74801 | 48 | object_weighted | 78 / 34 / 3527.0 | 78 / 34 / 3527.0 | 80 / 34 / 3548.0 | 78 / 34 / 3527.0 | 0.0 |
| moving_shared-74801 | 48 | legacy_event_prior | 67 / 67 / 3675.5 | 78 / 34 / 3527.0 | 82 / 62 / 3793.0 | 82 / 82 / 3953.0 | -148.5 |
| public_toolagent-73601 | 12 | object_weighted | 1010 / 22 / 22866.5 | 1006 / 13 / 22752.5 | 1044 / 22 / 23223.5 | 1051 / 275 / 25321.0 | -114.0 |
| public_toolagent-73601 | 12 | legacy_event_prior | 1010 / 22 / 22866.5 | 1006 / 13 / 22752.5 | 1044 / 22 / 23223.5 | 1051 / 275 / 25321.0 | -114.0 |
| public_toolagent-73601 | 18 | object_weighted | 938 / 28 / 22158.5 | 940 / 19 / 22107.5 | 983 / 28 / 22631.0 | 1008 / 238 / 24573.5 | -51.0 |
| public_toolagent-73601 | 18 | legacy_event_prior | 938 / 28 / 22158.5 | 940 / 19 / 22107.5 | 983 / 28 / 22631.0 | 1008 / 238 / 24573.5 | -51.0 |
| public_toolagent-73601 | 24 | object_weighted | 865 / 34 / 21440.0 | 873 / 25 / 21452.0 | 921 / 34 / 22028.0 | 960 / 196 / 23733.5 | 12.0 |
| public_toolagent-73601 | 24 | legacy_event_prior | 865 / 34 / 21440.0 | 873 / 25 / 21452.0 | 921 / 34 / 22028.0 | 960 / 196 / 23733.5 | 12.0 |
| public_toolagent-73601 | 48 | object_weighted | 799 / 41 / 20803.0 | 833 / 41 / 21160.0 | 826 / 44 / 21110.5 | 830 / 94 / 21552.5 | 357.0 |
| public_toolagent-73601 | 48 | legacy_event_prior | 799 / 41 / 20803.0 | 833 / 41 / 21160.0 | 826 / 44 / 21110.5 | 830 / 94 / 21552.5 | 357.0 |
| public_toolagent-73602 | 12 | object_weighted | 1026 / 29 / 23080.0 | 1012 / 17 / 22837.0 | 1031 / 20 / 23060.5 | 1040 / 270 / 25155.0 | -243.0 |
| public_toolagent-73602 | 12 | legacy_event_prior | 1026 / 29 / 23080.0 | 1012 / 17 / 22837.0 | 1031 / 20 / 23060.5 | 1040 / 270 / 25155.0 | -243.0 |
| public_toolagent-73602 | 18 | object_weighted | 954 / 37 / 22388.0 | 943 / 23 / 22160.5 | 969 / 27 / 22465.5 | 996 / 232 / 24389.0 | -227.5 |
| public_toolagent-73602 | 18 | legacy_event_prior | 954 / 37 / 22388.0 | 943 / 23 / 22160.5 | 969 / 27 / 22465.5 | 996 / 232 / 24389.0 | -227.5 |
| public_toolagent-73602 | 24 | object_weighted | 879 / 43 / 21648.5 | 870 / 28 / 21434.0 | 904 / 34 / 21839.0 | 919 / 161 / 23012.5 | -214.5 |
| public_toolagent-73602 | 24 | legacy_event_prior | 879 / 43 / 21648.5 | 870 / 28 / 21434.0 | 904 / 34 / 21839.0 | 919 / 161 / 23012.5 | -214.5 |
| public_toolagent-73602 | 48 | object_weighted | 770 / 36 / 20448.0 | 818 / 36 / 20952.0 | 780 / 34 / 20537.0 | 788 / 53 / 20773.0 | 504.0 |
| public_toolagent-73602 | 48 | legacy_event_prior | 770 / 36 / 20448.0 | 818 / 36 / 20952.0 | 780 / 34 / 20537.0 | 788 / 53 / 20773.0 | 504.0 |
| public_toolagent-73603 | 12 | object_weighted | 1035 / 24 / 23134.5 | 1046 / 12 / 23154.0 | 1041 / 19 / 23157.5 | 1069 / 247 / 25275.5 | 19.5 |
| public_toolagent-73603 | 12 | legacy_event_prior | 1035 / 24 / 23134.5 | 1046 / 12 / 23154.0 | 1041 / 19 / 23157.5 | 1069 / 247 / 25275.5 | 19.5 |
| public_toolagent-73603 | 18 | object_weighted | 975 / 30 / 22552.5 | 1001 / 18 / 22729.5 | 992 / 25 / 22691.0 | 1036 / 220 / 24713.0 | 177.0 |
| public_toolagent-73603 | 18 | legacy_event_prior | 975 / 30 / 22552.5 | 1001 / 18 / 22729.5 | 992 / 25 / 22691.0 | 1036 / 220 / 24713.0 | 177.0 |
| public_toolagent-73603 | 24 | object_weighted | 920 / 34 / 22007.0 | 938 / 21 / 22092.0 | 940 / 28 / 22169.0 | 985 / 175 / 23817.5 | 85.0 |
| public_toolagent-73603 | 24 | legacy_event_prior | 920 / 34 / 22007.0 | 938 / 21 / 22092.0 | 940 / 28 / 22169.0 | 985 / 175 / 23817.5 | 85.0 |
| public_toolagent-73603 | 48 | object_weighted | 821 / 29 / 20927.5 | 851 / 29 / 21242.5 | 830 / 38 / 21094.0 | 831 / 39 / 21112.5 | 315.0 |
| public_toolagent-73603 | 48 | legacy_event_prior | 821 / 29 / 20927.5 | 851 / 29 / 21242.5 | 830 / 38 / 21094.0 | 831 / 39 / 21112.5 | 315.0 |
| public_toolagent-74802 | 12 | object_weighted | 1072 / 23 / 23515.0 | 1072 / 14 / 23443.0 | 1071 / 13 / 23424.5 | 1061 / 181 / 24663.5 | -72.0 |
| public_toolagent-74802 | 12 | legacy_event_prior | 1072 / 23 / 23515.0 | 1072 / 14 / 23443.0 | 1071 / 13 / 23424.5 | 1061 / 181 / 24663.5 | -72.0 |
| public_toolagent-74802 | 18 | object_weighted | 1015 / 27 / 22948.5 | 1035 / 19 / 23094.5 | 1036 / 18 / 23097.0 | 1030 / 156 / 24138.0 | 146.0 |
| public_toolagent-74802 | 18 | legacy_event_prior | 1015 / 27 / 22948.5 | 1035 / 19 / 23094.5 | 1036 / 18 / 23097.0 | 1030 / 156 / 24138.0 | 146.0 |
| public_toolagent-74802 | 24 | object_weighted | 967 / 33 / 22492.5 | 1002 / 25 / 22796.0 | 995 / 21 / 22690.5 | 987 / 119 / 23390.5 | 303.5 |
| public_toolagent-74802 | 24 | legacy_event_prior | 967 / 33 / 22492.5 | 1002 / 25 / 22796.0 | 995 / 21 / 22690.5 | 987 / 119 / 23390.5 | 303.5 |
| public_toolagent-74802 | 48 | object_weighted | 876 / 36 / 21561.0 | 936 / 36 / 22191.0 | 899 / 35 / 21794.5 | 882 / 42 / 21672.0 | 630.0 |
| public_toolagent-74802 | 48 | legacy_event_prior | 876 / 36 / 21561.0 | 936 / 36 / 22191.0 | 899 / 35 / 21794.5 | 882 / 42 / 21672.0 | 630.0 |
| stationary_shared-73701 | 12 | object_weighted | 119 / 50 / 4264.0 | 118 / 22 / 4029.5 | 135 / 45 / 4392.0 | 122 / 62 / 4391.5 | -234.5 |
| stationary_shared-73701 | 12 | legacy_event_prior | 119 / 50 / 4264.0 | 118 / 22 / 4029.5 | 135 / 45 / 4392.0 | 150 / 142 / 5325.5 | -234.5 |
| stationary_shared-73701 | 18 | object_weighted | 65 / 9 / 3369.0 | 65 / 9 / 3369.0 | 90 / 22 / 3735.5 | 65 / 9 / 3369.0 | 0.0 |
| stationary_shared-73701 | 18 | legacy_event_prior | 77 / 33 / 3687.0 | 65 / 9 / 3369.0 | 91 / 27 / 3786.0 | 95 / 90 / 4332.0 | -318.0 |
| stationary_shared-73701 | 24 | object_weighted | 65 / 12 / 3393.0 | 65 / 12 / 3393.0 | 82 / 21 / 3643.5 | 65 / 12 / 3393.0 | 0.0 |
| stationary_shared-73701 | 24 | legacy_event_prior | 74 / 53 / 3815.5 | 65 / 12 / 3393.0 | 84 / 29 / 3728.5 | 81 / 79 / 4097.0 | -422.5 |
| stationary_shared-73701 | 48 | object_weighted | 65 / 24 / 3489.0 | 65 / 24 / 3489.0 | 69 / 21 / 3507.0 | 65 / 24 / 3489.0 | 0.0 |
| stationary_shared-73701 | 48 | legacy_event_prior | 66 / 66 / 3835.5 | 65 / 24 / 3489.0 | 78 / 35 / 3713.5 | 71 / 71 / 3928.0 | -346.5 |
| uniform-73702 | 12 | object_weighted | 784 / 36 / 19576.5 | 785 / 25 / 19499.0 | 792 / 31 / 19620.5 | 858 / 837 / 26761.5 | -77.5 |
| uniform-73702 | 12 | legacy_event_prior | 784 / 36 / 19576.5 | 785 / 25 / 19499.0 | 792 / 31 / 19620.5 | 858 / 837 / 26761.5 | -77.5 |
| uniform-73702 | 18 | object_weighted | 663 / 40 / 18338.0 | 667 / 35 / 18340.0 | 659 / 35 / 18256.0 | 720 / 702 / 24232.5 | 2.0 |
| uniform-73702 | 18 | legacy_event_prior | 663 / 40 / 18338.0 | 667 / 35 / 18340.0 | 659 / 35 / 18256.0 | 720 / 702 / 24232.5 | 2.0 |
| uniform-73702 | 24 | object_weighted | 544 / 45 / 17128.5 | 546 / 41 / 17117.5 | 532 / 41 / 16970.5 | 576 / 561 / 21592.5 | -11.0 |
| uniform-73702 | 24 | legacy_event_prior | 544 / 45 / 17128.5 | 546 / 41 / 17117.5 | 532 / 41 / 16970.5 | 576 / 561 / 21592.5 | -11.0 |
| uniform-73702 | 48 | object_weighted | 24 / 24 / 11500.5 | 24 / 24 / 11500.5 | 30 / 24 / 11563.5 | 24 / 24 / 11500.5 | 0.0 |
| uniform-73702 | 48 | legacy_event_prior | 24 / 24 / 11500.5 | 24 / 24 / 11500.5 | 30 / 24 / 11563.5 | 24 / 24 / 11500.5 | 0.0 |
