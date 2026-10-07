# Diagnosis only: public74802 tail decomposition

Tracing changes timings. These two arms do not replace the frozen speed tables. Overlap is association, not proof of causality.

## Full

| index | class | tier | response ms | open ms | read ms | pread ms | release in client ms | copy overlap ms |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 194 | first | remote | 87.199 | 2.057 | 84.852 | 82.478 | 0.000 | 0.000 |
| 70 | reused | remote | 32.868 | 6.619 | 25.973 | 21.035 | 0.000 | 3.983 |
| 64 | reused | remote | 32.594 | 6.342 | 25.974 | 21.068 | 0.000 | 4.123 |
| 0 | first | remote | 31.119 | 3.749 | 26.686 | 20.757 | 0.000 | 0.226 |
| 65 | reused | remote | 31.012 | 6.519 | 24.211 | 20.348 | 0.000 | 4.009 |
| 68 | reused | remote | 30.607 | 6.122 | 24.218 | 20.495 | 0.000 | 4.088 |
| 67 | reused | remote | 30.535 | 4.296 | 25.966 | 21.076 | 0.000 | 0.000 |
| 12 | first | remote | 30.416 | 5.636 | 24.464 | 20.529 | 0.000 | 4.500 |
| 9 | first | remote | 30.116 | 5.292 | 24.511 | 20.509 | 0.000 | 4.462 |
| 37 | first | remote | 30.044 | 5.539 | 24.180 | 20.357 | 0.000 | 0.000 |
| 101 | first | remote | 29.917 | 5.269 | 24.371 | 20.437 | 0.000 | 0.000 |
| 107 | first | remote | 29.895 | 5.282 | 24.344 | 20.411 | 0.000 | 0.000 |

Diagnostic overhead enabled. No performance acceptance. Copy/plan/release overlaps are unions per category and may overlap each other; do not add them. Release may finish after client close; flush is its total, not a known in-request subinterval. First/reused means prior access to this object in this fixed trace, not an inferred cache miss. Read non-pread residual includes allocation, copying, counters, capture and scheduling; there is no standalone SubmitBackground timestamp, so it cannot be attributed solely to SQLite fsync.

## NoHotspot

| index | class | tier | response ms | open ms | read ms | pread ms | release in client ms | copy overlap ms |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 0 | first | remote | 31.407 | 4.027 | 26.772 | 20.629 | 0.000 | 0.188 |
| 72 | first | remote | 31.326 | 5.413 | 25.525 | 20.846 | 0.000 | 0.000 |
| 7 | first | remote | 31.127 | 5.052 | 25.605 | 20.418 | 0.000 | 4.309 |
| 37 | first | remote | 30.001 | 5.428 | 24.208 | 20.263 | 0.000 | 0.000 |
| 24 | first | remote | 29.935 | 5.397 | 24.153 | 20.235 | 0.000 | 0.000 |
| 9 | first | remote | 29.807 | 5.036 | 24.376 | 20.369 | 0.000 | 4.615 |
| 84 | first | remote | 29.716 | 5.153 | 24.188 | 20.378 | 0.000 | 0.000 |
| 105 | first | remote | 29.703 | 5.158 | 24.258 | 20.294 | 0.000 | 0.000 |
| 116 | first | remote | 29.694 | 5.427 | 23.996 | 20.220 | 0.000 | 0.000 |
| 93 | first | remote | 29.675 | 5.024 | 24.288 | 20.341 | 0.000 | 0.000 |
| 90 | first | remote | 29.631 | 5.073 | 24.203 | 20.412 | 0.000 | 0.000 |
| 54 | first | remote | 29.621 | 5.104 | 24.161 | 20.359 | 0.000 | 0.000 |

Diagnostic overhead enabled. No performance acceptance. Copy/plan/release overlaps are unions per category and may overlap each other; do not add them. Release may finish after client close; flush is its total, not a known in-request subinterval. First/reused means prior access to this object in this fixed trace, not an inferred cache miss. Read non-pread residual includes allocation, copying, counters, capture and scheduling; there is no standalone SubmitBackground timestamp, so it cannot be attributed solely to SQLite fsync.

