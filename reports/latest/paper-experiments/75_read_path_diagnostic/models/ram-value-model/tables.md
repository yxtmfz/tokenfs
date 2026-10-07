# Cross-tier RAM victim ranking model

Fixed 10 inputs × 2 H algorithms × 3 RAM replacement choices × 4 arms = 240 model arms. LRU baseline vs original disk-value ranking vs retained_capture=false RAM-value ranking. RAM always captures incoming storage read; chooses victim only among previous 2 objects; exact 4MiB budget. All compared arms use same victim-selection code with existing H/P/J flags. No physical pinning/concurrency in serialized immediate-copy model; no throughput/p99 evidence. This extends H to RAM placement, not unchanged original H.

Each cell: remote reads / local disk hits / RAM hits / copies.

| Input | Variant | Full | NoH | NoP | NoJ |
|---|---|---:|---:|---:|---:|
| moving_shared-73501 | retained_lru | 77 / 162 / 913 / 65 | 79 / 160 / 913 / 28 | 95 / 144 / 913 / 44 | 99 / 140 / 913 / 97 |
| moving_shared-73501 | retained_disk_value | 77 / 151 / 924 / 65 | 79 / 152 / 921 / 28 | 95 / 133 / 924 / 44 | 99 / 129 / 924 / 97 |
| moving_shared-73501 | retained_ram_value | 77 / 151 / 924 / 65 | 79 / 152 / 921 / 28 | 95 / 133 / 924 / 44 | 99 / 129 / 924 / 97 |
| moving_shared-73501 | opportunity74_lru | 78 / 161 / 913 / 29 | 79 / 160 / 913 / 28 | 97 / 142 / 913 / 36 | 85 / 154 / 913 / 36 |
| moving_shared-73501 | opportunity74_disk_value | 78 / 147 / 927 / 29 | 79 / 152 / 921 / 28 | 97 / 128 / 927 / 36 | 85 / 140 / 927 / 36 |
| moving_shared-73501 | opportunity74_ram_value | 78 / 150 / 924 / 29 | 79 / 152 / 921 / 28 | 97 / 131 / 924 / 36 | 85 / 143 / 924 / 36 |
| moving_shared-73502 | retained_lru | 76 / 169 / 907 / 64 | 85 / 160 / 907 / 28 | 112 / 133 / 907 / 55 | 88 / 157 / 907 / 85 |
| moving_shared-73502 | retained_disk_value | 76 / 168 / 908 / 64 | 85 / 151 / 916 / 28 | 112 / 132 / 908 / 55 | 88 / 156 / 908 / 85 |
| moving_shared-73502 | retained_ram_value | 76 / 167 / 909 / 64 | 85 / 151 / 916 / 28 | 112 / 131 / 909 / 55 | 88 / 155 / 909 / 85 |
| moving_shared-73502 | opportunity74_lru | 83 / 162 / 907 / 28 | 85 / 160 / 907 / 28 | 120 / 125 / 907 / 43 | 104 / 141 / 907 / 49 |
| moving_shared-73502 | opportunity74_disk_value | 83 / 155 / 914 / 28 | 85 / 151 / 916 / 28 | 121 / 117 / 914 / 43 | 107 / 131 / 914 / 52 |
| moving_shared-73502 | opportunity74_ram_value | 83 / 160 / 909 / 28 | 85 / 151 / 916 / 28 | 121 / 122 / 909 / 43 | 107 / 136 / 909 / 52 |
| moving_shared-73503 | retained_lru | 78 / 158 / 916 / 63 | 79 / 157 / 916 / 28 | 114 / 122 / 916 / 53 | 107 / 129 / 916 / 104 |
| moving_shared-73503 | retained_disk_value | 79 / 153 / 920 / 64 | 80 / 154 / 918 / 28 | 116 / 116 / 920 / 55 | 107 / 125 / 920 / 104 |
| moving_shared-73503 | retained_ram_value | 79 / 153 / 920 / 64 | 80 / 154 / 918 / 28 | 116 / 116 / 920 / 55 | 107 / 125 / 920 / 104 |
| moving_shared-73503 | opportunity74_lru | 78 / 158 / 916 / 28 | 79 / 157 / 916 / 28 | 119 / 117 / 916 / 42 | 99 / 137 / 916 / 49 |
| moving_shared-73503 | opportunity74_disk_value | 78 / 156 / 918 / 28 | 80 / 154 / 918 / 28 | 118 / 116 / 918 / 43 | 100 / 134 / 918 / 50 |
| moving_shared-73503 | opportunity74_ram_value | 78 / 154 / 920 / 28 | 80 / 154 / 918 / 28 | 118 / 114 / 920 / 43 | 100 / 132 / 920 / 50 |
| moving_shared-74801 | retained_lru | 79 / 153 / 920 / 68 | 84 / 148 / 920 / 28 | 105 / 127 / 920 / 48 | 111 / 121 / 920 / 111 |
| moving_shared-74801 | retained_disk_value | 79 / 156 / 917 / 68 | 84 / 149 / 919 / 28 | 105 / 130 / 917 / 49 | 113 / 122 / 917 / 113 |
| moving_shared-74801 | retained_ram_value | 79 / 156 / 917 / 68 | 84 / 149 / 919 / 28 | 105 / 130 / 917 / 49 | 113 / 122 / 917 / 113 |
| moving_shared-74801 | opportunity74_lru | 84 / 148 / 920 / 28 | 84 / 148 / 920 / 28 | 103 / 129 / 920 / 32 | 111 / 121 / 920 / 55 |
| moving_shared-74801 | opportunity74_disk_value | 84 / 152 / 916 / 28 | 84 / 149 / 919 / 28 | 107 / 129 / 916 / 35 | 113 / 123 / 916 / 57 |
| moving_shared-74801 | opportunity74_ram_value | 84 / 151 / 917 / 28 | 84 / 149 / 919 / 28 | 107 / 128 / 917 / 35 | 113 / 122 / 917 / 57 |
| public_toolagent-73601 | retained_lru | 865 / 286 / 1 / 34 | 873 / 278 / 1 / 25 | 921 / 230 / 1 / 34 | 960 / 191 / 1 / 196 |
| public_toolagent-73601 | retained_disk_value | 859 / 274 / 19 / 33 | 867 / 266 / 19 / 24 | 914 / 219 / 19 / 33 | 960 / 173 / 19 / 196 |
| public_toolagent-73601 | retained_ram_value | 859 / 274 / 19 / 33 | 867 / 266 / 19 / 24 | 914 / 219 / 19 / 33 | 960 / 173 / 19 / 196 |
| public_toolagent-73601 | opportunity74_lru | 869 / 282 / 1 / 34 | 873 / 278 / 1 / 25 | 922 / 229 / 1 / 33 | 969 / 182 / 1 / 204 |
| public_toolagent-73601 | opportunity74_disk_value | 863 / 269 / 20 / 33 | 867 / 266 / 19 / 24 | 922 / 210 / 20 / 33 | 969 / 163 / 20 / 204 |
| public_toolagent-73601 | opportunity74_ram_value | 863 / 270 / 19 / 33 | 867 / 266 / 19 / 24 | 922 / 211 / 19 / 33 | 969 / 164 / 19 / 204 |
| public_toolagent-73602 | retained_lru | 879 / 271 / 2 / 43 | 870 / 280 / 2 / 28 | 904 / 246 / 2 / 34 | 919 / 231 / 2 / 161 |
| public_toolagent-73602 | retained_disk_value | 866 / 269 / 17 / 34 | 854 / 281 / 17 / 24 | 896 / 239 / 17 / 33 | 919 / 216 / 17 / 161 |
| public_toolagent-73602 | retained_ram_value | 866 / 269 / 17 / 34 | 854 / 281 / 17 / 24 | 896 / 239 / 17 / 33 | 919 / 216 / 17 / 161 |
| public_toolagent-73602 | opportunity74_lru | 879 / 271 / 2 / 43 | 870 / 280 / 2 / 28 | 904 / 246 / 2 / 33 | 916 / 234 / 2 / 158 |
| public_toolagent-73602 | opportunity74_disk_value | 866 / 271 / 15 / 34 | 854 / 281 / 17 / 24 | 897 / 240 / 15 / 32 | 916 / 221 / 15 / 158 |
| public_toolagent-73602 | opportunity74_ram_value | 866 / 269 / 17 / 34 | 854 / 281 / 17 / 24 | 896 / 239 / 17 / 32 | 916 / 219 / 17 / 158 |
| public_toolagent-73603 | retained_lru | 920 / 230 / 2 / 34 | 938 / 212 / 2 / 21 | 940 / 210 / 2 / 28 | 985 / 165 / 2 / 175 |
| public_toolagent-73603 | retained_disk_value | 913 / 216 / 23 / 28 | 936 / 195 / 21 / 21 | 940 / 189 / 23 / 28 | 985 / 144 / 23 / 175 |
| public_toolagent-73603 | retained_ram_value | 913 / 216 / 23 / 28 | 936 / 195 / 21 / 21 | 940 / 189 / 23 / 28 | 985 / 144 / 23 / 175 |
| public_toolagent-73603 | opportunity74_lru | 913 / 237 / 2 / 28 | 938 / 212 / 2 / 21 | 943 / 207 / 2 / 26 | 982 / 168 / 2 / 172 |
| public_toolagent-73603 | opportunity74_disk_value | 911 / 217 / 24 / 28 | 936 / 195 / 21 / 21 | 935 / 193 / 24 / 25 | 982 / 146 / 24 / 172 |
| public_toolagent-73603 | opportunity74_ram_value | 911 / 218 / 23 / 28 | 936 / 195 / 21 / 21 | 937 / 192 / 23 / 25 | 982 / 147 / 23 / 172 |
| public_toolagent-74802 | retained_lru | 967 / 183 / 2 / 33 | 1002 / 148 / 2 / 25 | 995 / 155 / 2 / 21 | 987 / 163 / 2 / 119 |
| public_toolagent-74802 | retained_disk_value | 967 / 155 / 30 / 33 | 998 / 123 / 31 / 24 | 995 / 127 / 30 / 21 | 987 / 135 / 30 / 119 |
| public_toolagent-74802 | retained_ram_value | 967 / 155 / 30 / 33 | 998 / 123 / 31 / 24 | 995 / 127 / 30 / 21 | 987 / 135 / 30 / 119 |
| public_toolagent-74802 | opportunity74_lru | 967 / 183 / 2 / 33 | 1002 / 148 / 2 / 25 | 995 / 155 / 2 / 21 | 979 / 171 / 2 / 111 |
| public_toolagent-74802 | opportunity74_disk_value | 967 / 155 / 30 / 33 | 998 / 123 / 31 / 24 | 995 / 127 / 30 / 21 | 979 / 143 / 30 / 111 |
| public_toolagent-74802 | opportunity74_ram_value | 967 / 155 / 30 / 33 | 998 / 123 / 31 / 24 | 995 / 127 / 30 / 21 | 979 / 143 / 30 / 111 |
| stationary_shared-73701 | retained_lru | 74 / 175 / 903 / 53 | 65 / 184 / 903 / 12 | 84 / 165 / 903 / 29 | 81 / 168 / 903 / 79 |
| stationary_shared-73701 | retained_disk_value | 74 / 164 / 914 / 53 | 65 / 174 / 913 / 12 | 84 / 154 / 914 / 29 | 81 / 157 / 914 / 79 |
| stationary_shared-73701 | retained_ram_value | 74 / 164 / 914 / 53 | 65 / 174 / 913 / 12 | 84 / 154 / 914 / 29 | 81 / 157 / 914 / 79 |
| stationary_shared-73701 | opportunity74_lru | 65 / 184 / 903 / 12 | 65 / 184 / 903 / 12 | 86 / 163 / 903 / 22 | 65 / 184 / 903 / 12 |
| stationary_shared-73701 | opportunity74_disk_value | 65 / 172 / 915 / 12 | 65 / 174 / 913 / 12 | 86 / 151 / 915 / 22 | 65 / 172 / 915 / 12 |
| stationary_shared-73701 | opportunity74_ram_value | 65 / 173 / 914 / 12 | 65 / 174 / 913 / 12 | 86 / 152 / 914 / 22 | 65 / 173 / 914 / 12 |
| uniform-73702 | retained_lru | 544 / 509 / 99 / 45 | 546 / 507 / 99 / 41 | 532 / 521 / 99 / 41 | 576 / 477 / 99 / 561 |
| uniform-73702 | retained_disk_value | 550 / 505 / 97 / 44 | 563 / 488 / 101 / 38 | 563 / 492 / 97 / 42 | 593 / 462 / 97 / 578 |
| uniform-73702 | retained_ram_value | 550 / 505 / 97 / 44 | 563 / 488 / 101 / 38 | 563 / 492 / 97 / 42 | 593 / 462 / 97 / 578 |
| uniform-73702 | opportunity74_lru | 529 / 524 / 99 / 38 | 546 / 507 / 99 / 41 | 532 / 521 / 99 / 33 | 600 / 453 / 99 / 585 |
| uniform-73702 | opportunity74_disk_value | 551 / 503 / 98 / 42 | 563 / 488 / 101 / 38 | 546 / 508 / 98 / 33 | 595 / 459 / 98 / 580 |
| uniform-73702 | opportunity74_ram_value | 543 / 512 / 97 / 40 | 563 / 488 / 101 / 38 | 535 / 520 / 97 / 30 | 595 / 460 / 97 / 580 |
