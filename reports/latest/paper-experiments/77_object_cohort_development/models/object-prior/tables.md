# Distinct-object newcomer prior screen

Fixed 10 known inputs × original/event vs distinct-object newcomer prior × retained/74 H × 4 arms =160 arms. Only NewcomerDiskPrior numerator changed; all other logic, old zero guards, controls, cost constants and geometry unchanged. Instant copies, 21ms remote/10.5ms local/8ms copy; no actual rates/p99. Distinct recurrent entries/(entries+1) is bounded object support, not an unbiased probability; entries have unequal ages and incomplete future-return exposure. Positive cohort value in an admission is association, not proof it drove max()-combined acceptance.

Each cell: remote / copies / admissions with positive cohort term.

| Input | Variant | Full | NoH | NoP | NoJ | Full positive cohort: headroom / net_gain |
|---|---|---:|---:|---:|---:|---:|
| moving_shared-73501 | retained_event_prior | 77 / 65 / 47 | 79 / 28 / 0 | 95 / 44 / 12 | 99 / 97 / 56 | 8 / 39 |
| moving_shared-73501 | retained_object_prior | 79 / 29 / 8 | 79 / 28 / 0 | 101 / 38 / 3 | 89 / 39 / 8 | 8 / 0 |
| moving_shared-73501 | opportunity74_event_prior | 78 / 29 / 0 | 79 / 28 / 0 | 97 / 36 / 0 | 85 / 36 / 0 | 0 / 0 |
| moving_shared-73501 | opportunity74_object_prior | 78 / 29 / 0 | 79 / 28 / 0 | 97 / 36 / 0 | 85 / 36 / 0 | 0 / 0 |
| moving_shared-73502 | retained_event_prior | 76 / 64 / 49 | 85 / 28 / 0 | 112 / 55 / 17 | 88 / 85 / 58 | 6 / 43 |
| moving_shared-73502 | retained_object_prior | 83 / 28 / 6 | 85 / 28 / 0 | 120 / 51 / 3 | 101 / 46 / 6 | 6 / 0 |
| moving_shared-73502 | opportunity74_event_prior | 83 / 28 / 0 | 85 / 28 / 0 | 120 / 43 / 0 | 104 / 49 / 0 | 0 / 0 |
| moving_shared-73502 | opportunity74_object_prior | 83 / 28 / 0 | 85 / 28 / 0 | 120 / 43 / 0 | 104 / 49 / 0 | 0 / 0 |
| moving_shared-73503 | retained_event_prior | 78 / 63 / 47 | 79 / 28 / 0 | 114 / 53 / 13 | 107 / 104 / 56 | 8 / 39 |
| moving_shared-73503 | retained_object_prior | 78 / 28 / 8 | 79 / 28 / 0 | 114 / 45 / 4 | 98 / 47 / 8 | 8 / 0 |
| moving_shared-73503 | opportunity74_event_prior | 78 / 28 / 0 | 79 / 28 / 0 | 119 / 42 / 0 | 99 / 49 / 0 | 0 / 0 |
| moving_shared-73503 | opportunity74_object_prior | 78 / 28 / 0 | 79 / 28 / 0 | 119 / 42 / 0 | 99 / 49 / 0 | 0 / 0 |
| moving_shared-74801 | retained_event_prior | 79 / 68 / 54 | 84 / 28 / 0 | 105 / 48 / 19 | 111 / 111 / 63 | 8 / 46 |
| moving_shared-74801 | retained_object_prior | 84 / 28 / 8 | 84 / 28 / 0 | 107 / 36 / 5 | 110 / 54 / 8 | 8 / 0 |
| moving_shared-74801 | opportunity74_event_prior | 84 / 28 / 0 | 84 / 28 / 0 | 103 / 32 / 0 | 111 / 55 / 0 | 0 / 0 |
| moving_shared-74801 | opportunity74_object_prior | 84 / 28 / 0 | 84 / 28 / 0 | 103 / 32 / 0 | 111 / 55 / 0 | 0 / 0 |
| public_toolagent-73601 | retained_event_prior | 865 / 34 / 0 | 873 / 25 / 0 | 921 / 34 / 0 | 960 / 196 / 0 | 0 / 0 |
| public_toolagent-73601 | retained_object_prior | 865 / 34 / 0 | 873 / 25 / 0 | 921 / 34 / 0 | 960 / 196 / 0 | 0 / 0 |
| public_toolagent-73601 | opportunity74_event_prior | 869 / 34 / 0 | 873 / 25 / 0 | 922 / 33 / 0 | 969 / 204 / 0 | 0 / 0 |
| public_toolagent-73601 | opportunity74_object_prior | 869 / 34 / 0 | 873 / 25 / 0 | 922 / 33 / 0 | 969 / 204 / 0 | 0 / 0 |
| public_toolagent-73602 | retained_event_prior | 879 / 43 / 0 | 870 / 28 / 0 | 904 / 34 / 0 | 919 / 161 / 0 | 0 / 0 |
| public_toolagent-73602 | retained_object_prior | 879 / 43 / 0 | 870 / 28 / 0 | 904 / 34 / 0 | 919 / 161 / 0 | 0 / 0 |
| public_toolagent-73602 | opportunity74_event_prior | 879 / 43 / 0 | 870 / 28 / 0 | 904 / 33 / 0 | 916 / 158 / 0 | 0 / 0 |
| public_toolagent-73602 | opportunity74_object_prior | 879 / 43 / 0 | 870 / 28 / 0 | 904 / 33 / 0 | 916 / 158 / 0 | 0 / 0 |
| public_toolagent-73603 | retained_event_prior | 920 / 34 / 0 | 938 / 21 / 0 | 940 / 28 / 0 | 985 / 175 / 0 | 0 / 0 |
| public_toolagent-73603 | retained_object_prior | 920 / 34 / 0 | 938 / 21 / 0 | 940 / 28 / 0 | 985 / 175 / 0 | 0 / 0 |
| public_toolagent-73603 | opportunity74_event_prior | 913 / 28 / 0 | 938 / 21 / 0 | 943 / 26 / 0 | 982 / 172 / 0 | 0 / 0 |
| public_toolagent-73603 | opportunity74_object_prior | 913 / 28 / 0 | 938 / 21 / 0 | 943 / 26 / 0 | 982 / 172 / 0 | 0 / 0 |
| public_toolagent-74802 | retained_event_prior | 967 / 33 / 0 | 1002 / 25 / 0 | 995 / 21 / 0 | 987 / 119 / 0 | 0 / 0 |
| public_toolagent-74802 | retained_object_prior | 967 / 33 / 0 | 1002 / 25 / 0 | 995 / 21 / 0 | 987 / 119 / 0 | 0 / 0 |
| public_toolagent-74802 | opportunity74_event_prior | 967 / 33 / 0 | 1002 / 25 / 0 | 995 / 21 / 0 | 979 / 111 / 0 | 0 / 0 |
| public_toolagent-74802 | opportunity74_object_prior | 967 / 33 / 0 | 1002 / 25 / 0 | 995 / 21 / 0 | 979 / 111 / 0 | 0 / 0 |
| stationary_shared-73701 | retained_event_prior | 74 / 53 / 40 | 65 / 12 / 0 | 84 / 29 / 10 | 81 / 79 / 59 | 6 / 34 |
| stationary_shared-73701 | retained_object_prior | 65 / 12 / 6 | 65 / 12 / 0 | 82 / 21 / 4 | 65 / 12 / 6 | 6 / 0 |
| stationary_shared-73701 | opportunity74_event_prior | 65 / 12 / 0 | 65 / 12 / 0 | 86 / 22 / 0 | 65 / 12 / 0 | 0 / 0 |
| stationary_shared-73701 | opportunity74_object_prior | 65 / 12 / 0 | 65 / 12 / 0 | 86 / 22 / 0 | 65 / 12 / 0 | 0 / 0 |
| uniform-73702 | retained_event_prior | 544 / 45 / 2 | 546 / 41 / 0 | 532 / 41 / 1 | 576 / 561 / 2 | 2 / 0 |
| uniform-73702 | retained_object_prior | 544 / 45 / 2 | 546 / 41 / 0 | 532 / 41 / 1 | 576 / 561 / 2 | 2 / 0 |
| uniform-73702 | opportunity74_event_prior | 529 / 38 / 0 | 546 / 41 / 0 | 532 / 33 / 0 | 600 / 585 / 0 | 0 / 0 |
| uniform-73702 | opportunity74_object_prior | 529 / 38 / 0 | 546 / 41 / 0 | 532 / 33 / 0 | 600 / 585 / 0 | 0 / 0 |
