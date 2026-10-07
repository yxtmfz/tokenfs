# Persistent disk demand model

Persistent actual non-RAM demand; per-key all disk request gaps observed (including cache hits), bounded last 128 disk-event generations, recency expiry after mean+std; no future access. Same 10 inputs and four arms.

NoHotspot equality against retained policy checked for all 40 controls.

| Input | Variant | Full remote/copies | NoH remote/copies | NoP remote/copies | NoJ remote/copies |
|---|---|---:|---:|---:|---:|
| moving_shared-73501 | disk_clock_persistent_raw | 79/30 | 79/28 | 103/32 | 99/51 |
| moving_shared-73501 | disk_clock_persistent_matched | 79/30 | 79/28 | 103/32 | 99/51 |
| moving_shared-73501 | logical_clock_persistent_raw | 82/30 | 79/28 | 104/32 | 95/46 |
| moving_shared-73501 | logical_clock_persistent_matched | 82/30 | 79/28 | 104/32 | 95/46 |
| moving_shared-73502 | disk_clock_persistent_raw | 84/29 | 85/28 | 119/41 | 107/54 |
| moving_shared-73502 | disk_clock_persistent_matched | 84/29 | 85/28 | 119/41 | 107/54 |
| moving_shared-73502 | logical_clock_persistent_raw | 87/29 | 85/28 | 119/37 | 107/52 |
| moving_shared-73502 | logical_clock_persistent_matched | 87/29 | 85/28 | 119/37 | 107/52 |
| moving_shared-73503 | disk_clock_persistent_raw | 80/32 | 79/28 | 117/34 | 96/48 |
| moving_shared-73503 | disk_clock_persistent_matched | 80/32 | 79/28 | 117/34 | 96/48 |
| moving_shared-73503 | logical_clock_persistent_raw | 83/30 | 79/28 | 120/32 | 97/46 |
| moving_shared-73503 | logical_clock_persistent_matched | 83/30 | 79/28 | 120/32 | 97/46 |
| moving_shared-74801 | disk_clock_persistent_raw | 83/28 | 84/28 | 115/36 | 112/57 |
| moving_shared-74801 | disk_clock_persistent_matched | 83/28 | 84/28 | 115/36 | 112/57 |
| moving_shared-74801 | logical_clock_persistent_raw | 86/28 | 84/28 | 116/31 | 111/55 |
| moving_shared-74801 | logical_clock_persistent_matched | 86/28 | 84/28 | 116/31 | 111/55 |
| public_toolagent-73601 | disk_clock_persistent_raw | 875/34 | 873/25 | 927/33 | 960/196 |
| public_toolagent-73601 | disk_clock_persistent_matched | 875/34 | 873/25 | 927/33 | 960/196 |
| public_toolagent-73601 | logical_clock_persistent_raw | 875/34 | 873/25 | 927/33 | 960/196 |
| public_toolagent-73601 | logical_clock_persistent_matched | 875/34 | 873/25 | 927/33 | 960/196 |
| public_toolagent-73602 | disk_clock_persistent_raw | 879/42 | 870/28 | 906/32 | 913/155 |
| public_toolagent-73602 | disk_clock_persistent_matched | 879/42 | 870/28 | 907/33 | 913/155 |
| public_toolagent-73602 | logical_clock_persistent_raw | 879/42 | 870/28 | 906/32 | 913/155 |
| public_toolagent-73602 | logical_clock_persistent_matched | 879/42 | 870/28 | 907/33 | 913/155 |
| public_toolagent-73603 | disk_clock_persistent_raw | 913/28 | 938/21 | 943/26 | 991/181 |
| public_toolagent-73603 | disk_clock_persistent_matched | 913/28 | 938/21 | 943/26 | 991/181 |
| public_toolagent-73603 | logical_clock_persistent_raw | 913/28 | 938/21 | 943/26 | 991/181 |
| public_toolagent-73603 | logical_clock_persistent_matched | 913/28 | 938/21 | 943/26 | 991/181 |
| public_toolagent-74802 | disk_clock_persistent_raw | 967/33 | 1002/25 | 995/21 | 979/111 |
| public_toolagent-74802 | disk_clock_persistent_matched | 967/33 | 1002/25 | 995/21 | 979/111 |
| public_toolagent-74802 | logical_clock_persistent_raw | 967/33 | 1002/25 | 995/21 | 979/111 |
| public_toolagent-74802 | logical_clock_persistent_matched | 967/33 | 1002/25 | 995/21 | 979/111 |
| stationary_shared-73701 | disk_clock_persistent_raw | 65/12 | 65/12 | 83/20 | 65/12 |
| stationary_shared-73701 | disk_clock_persistent_matched | 65/12 | 65/12 | 83/20 | 65/12 |
| stationary_shared-73701 | logical_clock_persistent_raw | 65/12 | 65/12 | 79/15 | 65/12 |
| stationary_shared-73701 | logical_clock_persistent_matched | 65/12 | 65/12 | 79/15 | 65/12 |
| uniform-73702 | disk_clock_persistent_raw | 537/33 | 546/41 | 512/24 | 574/560 |
| uniform-73702 | disk_clock_persistent_matched | 545/34 | 546/41 | 523/27 | 574/560 |
| uniform-73702 | logical_clock_persistent_raw | 541/33 | 546/41 | 530/25 | 590/576 |
| uniform-73702 | logical_clock_persistent_matched | 548/37 | 546/41 | 535/26 | 590/576 |
