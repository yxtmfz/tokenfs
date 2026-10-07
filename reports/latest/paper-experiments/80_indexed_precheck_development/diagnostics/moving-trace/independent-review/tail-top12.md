# Diagnosis only: moving74801 tail decomposition

Tracing changes timings. These two arms do not replace the frozen speed tables. Overlap is association, not proof of causality.

## Full

| index | class | tier | response ms | open ms | read ms | pread ms | release in client ms | copy overlap ms |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 844 | first | remote | 71.248 | 1.527 | 69.334 | 67.382 | 0.000 | 0.000 |
| 0 | first | remote | 29.632 | 4.483 | 24.707 | 20.426 | 0.000 | 0.000 |
| 12 | first | remote | 29.257 | 4.165 | 24.638 | 21.265 | 0.000 | 0.000 |
| 392 | first | remote | 28.279 | 4.357 | 23.515 | 20.358 | 0.000 | 0.000 |
| 812 | first | remote | 28.230 | 4.528 | 23.328 | 20.295 | 0.000 | 0.000 |
| 976 | first | remote | 27.989 | 3.335 | 24.257 | 21.076 | 0.000 | 0.000 |
| 204 | first | remote | 27.910 | 2.634 | 24.883 | 20.883 | 0.000 | 0.000 |
| 488 | first | remote | 27.634 | 2.102 | 25.065 | 20.974 | 0.000 | 0.000 |
| 44 | first | remote | 27.232 | 3.108 | 23.673 | 20.550 | 0.000 | 0.000 |
| 20 | first | remote | 27.178 | 2.390 | 24.361 | 21.129 | 0.000 | 0.000 |
| 984 | first | remote | 27.114 | 3.273 | 23.410 | 20.295 | 0.000 | 0.000 |
| 776 | first | remote | 26.966 | 2.953 | 23.645 | 20.446 | 0.000 | 0.000 |

Diagnostic overhead enabled. No performance acceptance. Copy/plan/release overlaps are unions per category and may overlap each other; do not add them. Release may finish after client close; flush is its total, not a known in-request subinterval. First/reused means prior access to this object in this fixed trace, not an inferred cache miss. Read non-pread residual includes allocation, copying, counters, capture and scheduling; there is no standalone SubmitBackground timestamp, so it cannot be attributed solely to SQLite fsync.

## NoHotspot

| index | class | tier | response ms | open ms | read ms | pread ms | release in client ms | copy overlap ms |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 0 | first | remote | 30.182 | 4.799 | 24.961 | 20.295 | 0.000 | 0.000 |
| 976 | first | remote | 28.984 | 4.507 | 24.114 | 21.017 | 0.000 | 0.000 |
| 204 | first | remote | 28.341 | 3.849 | 24.141 | 21.012 | 0.000 | 0.000 |
| 12 | first | remote | 28.089 | 3.350 | 24.325 | 21.099 | 0.000 | 0.000 |
| 4 | first | remote | 28.084 | 4.354 | 23.414 | 21.025 | 0.000 | 0.000 |
| 812 | first | remote | 27.505 | 3.519 | 23.581 | 20.356 | 0.000 | 0.000 |
| 984 | first | remote | 27.152 | 3.107 | 23.622 | 20.326 | 0.000 | 0.000 |
| 44 | first | remote | 27.071 | 3.211 | 23.436 | 20.308 | 0.000 | 0.000 |
| 736 | first | remote | 26.970 | 3.857 | 22.683 | 20.458 | 0.000 | 0.000 |
| 776 | first | remote | 26.963 | 4.036 | 22.579 | 20.315 | 0.000 | 0.000 |
| 692 | first | remote | 26.878 | 3.817 | 22.722 | 20.426 | 0.000 | 0.000 |
| 416 | first | remote | 26.816 | 3.850 | 22.559 | 20.353 | 0.000 | 0.000 |

Diagnostic overhead enabled. No performance acceptance. Copy/plan/release overlaps are unions per category and may overlap each other; do not add them. Release may finish after client close; flush is its total, not a known in-request subinterval. First/reused means prior access to this object in this fixed trace, not an inferred cache miss. Read non-pread residual includes allocation, copying, counters, capture and scheduling; there is no standalone SubmitBackground timestamp, so it cannot be attributed solely to SQLite fsync.

