# Disk demand model screening

Fixed 10 known inputs; four arms per variant. Constant remote/local/copy costs; instantaneous copies. Not throughput or latency evidence.

NoHotspot equality against unmodified retained policy checked for all variants and inputs.

| Input | Variant | Full remote/copies | NoH remote/copies | NoP remote/copies | NoJ remote/copies |
|---|---|---:|---:|---:|---:|
| moving_shared-73501 | retained | 77/65 | 79/28 | 95/44 | 99/97 |
| moving_shared-73501 | opportunity74 | 78/29 | 79/28 | 97/36 | 85/36 |
| moving_shared-73501 | disk_clock_raw | 81/30 | 79/28 | 110/44 | 96/48 |
| moving_shared-73501 | disk_clock_matched | 81/30 | 79/28 | 110/44 | 96/48 |
| moving_shared-73501 | logical_clock_raw | 77/28 | 79/28 | 107/44 | 91/39 |
| moving_shared-73501 | logical_clock_matched | 77/28 | 79/28 | 107/44 | 91/39 |
| moving_shared-73502 | retained | 76/64 | 85/28 | 112/55 | 88/85 |
| moving_shared-73502 | opportunity74 | 83/28 | 85/28 | 120/43 | 104/49 |
| moving_shared-73502 | disk_clock_raw | 88/31 | 85/28 | 127/49 | 100/47 |
| moving_shared-73502 | disk_clock_matched | 88/31 | 85/28 | 127/49 | 100/47 |
| moving_shared-73502 | logical_clock_raw | 84/29 | 85/28 | 120/47 | 105/49 |
| moving_shared-73502 | logical_clock_matched | 84/29 | 85/28 | 120/47 | 105/49 |
| moving_shared-73503 | retained | 78/63 | 79/28 | 114/53 | 107/104 |
| moving_shared-73503 | opportunity74 | 78/28 | 79/28 | 119/42 | 99/49 |
| moving_shared-73503 | disk_clock_raw | 85/33 | 79/28 | 134/55 | 104/56 |
| moving_shared-73503 | disk_clock_matched | 85/33 | 79/28 | 134/55 | 104/56 |
| moving_shared-73503 | logical_clock_raw | 79/28 | 79/28 | 121/49 | 99/46 |
| moving_shared-73503 | logical_clock_matched | 79/28 | 79/28 | 121/49 | 99/46 |
| moving_shared-74801 | retained | 79/68 | 84/28 | 105/48 | 111/111 |
| moving_shared-74801 | opportunity74 | 84/28 | 84/28 | 103/32 | 111/55 |
| moving_shared-74801 | disk_clock_raw | 85/28 | 84/28 | 127/54 | 115/60 |
| moving_shared-74801 | disk_clock_matched | 85/28 | 84/28 | 127/54 | 115/60 |
| moving_shared-74801 | logical_clock_raw | 85/28 | 84/28 | 114/41 | 110/48 |
| moving_shared-74801 | logical_clock_matched | 85/28 | 84/28 | 114/41 | 110/48 |
| public_toolagent-73601 | retained | 865/34 | 873/25 | 921/34 | 960/196 |
| public_toolagent-73601 | opportunity74 | 869/34 | 873/25 | 922/33 | 969/204 |
| public_toolagent-73601 | disk_clock_raw | 873/25 | 873/25 | 949/28 | 957/193 |
| public_toolagent-73601 | disk_clock_matched | 873/25 | 873/25 | 949/28 | 957/193 |
| public_toolagent-73601 | logical_clock_raw | 873/25 | 873/25 | 949/28 | 957/193 |
| public_toolagent-73601 | logical_clock_matched | 873/25 | 873/25 | 949/28 | 957/193 |
| public_toolagent-73602 | retained | 879/43 | 870/28 | 904/34 | 919/161 |
| public_toolagent-73602 | opportunity74 | 879/43 | 870/28 | 904/33 | 916/158 |
| public_toolagent-73602 | disk_clock_raw | 870/28 | 870/28 | 883/24 | 925/167 |
| public_toolagent-73602 | disk_clock_matched | 871/28 | 870/28 | 886/24 | 925/167 |
| public_toolagent-73602 | logical_clock_raw | 870/28 | 870/28 | 883/24 | 925/167 |
| public_toolagent-73602 | logical_clock_matched | 870/28 | 870/28 | 883/24 | 925/167 |
| public_toolagent-73603 | retained | 920/34 | 938/21 | 940/28 | 985/175 |
| public_toolagent-73603 | opportunity74 | 913/28 | 938/21 | 943/26 | 982/172 |
| public_toolagent-73603 | disk_clock_raw | 938/21 | 938/21 | 933/19 | 982/169 |
| public_toolagent-73603 | disk_clock_matched | 938/21 | 938/21 | 933/19 | 982/169 |
| public_toolagent-73603 | logical_clock_raw | 938/21 | 938/21 | 933/19 | 982/169 |
| public_toolagent-73603 | logical_clock_matched | 938/21 | 938/21 | 933/19 | 982/169 |
| public_toolagent-74802 | retained | 967/33 | 1002/25 | 995/21 | 987/119 |
| public_toolagent-74802 | opportunity74 | 967/33 | 1002/25 | 995/21 | 979/111 |
| public_toolagent-74802 | disk_clock_raw | 1003/25 | 1002/25 | 1007/21 | 979/111 |
| public_toolagent-74802 | disk_clock_matched | 1002/25 | 1002/25 | 1007/21 | 979/111 |
| public_toolagent-74802 | logical_clock_raw | 1003/25 | 1002/25 | 1007/21 | 979/111 |
| public_toolagent-74802 | logical_clock_matched | 1002/25 | 1002/25 | 1007/21 | 979/111 |
| stationary_shared-73701 | retained | 74/53 | 65/12 | 84/29 | 81/79 |
| stationary_shared-73701 | opportunity74 | 65/12 | 65/12 | 86/22 | 65/12 |
| stationary_shared-73701 | disk_clock_raw | 65/12 | 65/12 | 87/27 | 65/12 |
| stationary_shared-73701 | disk_clock_matched | 65/12 | 65/12 | 87/27 | 65/12 |
| stationary_shared-73701 | logical_clock_raw | 65/12 | 65/12 | 83/22 | 65/12 |
| stationary_shared-73701 | logical_clock_matched | 65/12 | 65/12 | 83/22 | 65/12 |
| uniform-73702 | retained | 544/45 | 546/41 | 532/41 | 576/561 |
| uniform-73702 | opportunity74 | 529/38 | 546/41 | 532/33 | 600/585 |
| uniform-73702 | disk_clock_raw | 547/36 | 546/41 | 544/32 | 587/573 |
| uniform-73702 | disk_clock_matched | 544/39 | 546/41 | 544/33 | 587/573 |
| uniform-73702 | logical_clock_raw | 545/40 | 546/41 | 530/33 | 591/576 |
| uniform-73702 | logical_clock_matched | 543/41 | 546/41 | 531/36 | 591/576 |
