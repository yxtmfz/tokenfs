# Same-binary reverse-order check

Repeat ALL15 symmetric-capture cases with the exact same executable, source, inputs and settings, reversing the five-arm order within each of the three workloads. This repetition is specified before the first symmetric results, and is not conditional on winning. Do not rebuild or tune. Keep individual results and total-bytes/total-wall-time aggregate. Require the original throughput/p99/drain/action conditions in BOTH orders before claiming a repeat-consistent screening pass. n2 known development inputs cannot establish statistical significance or real-GPU performance.

After speed testing, execute all five variants with96requests each and per-request SHA256 verification. Hashing times are excluded from speed results. NoHotspot,NoAffinity,NoJoint remain Full with one module switched off, not isolated single-module strategies. No change to budget, SIEVE capabilities or acceptance thresholds.
