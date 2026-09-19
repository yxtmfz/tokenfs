# Repeated-miss admission regression

This is a deterministic policy-liveness unit test, not a throughput measurement.
The service/copy samples are artificial inputs chosen to require accumulated reuse.
The same unchanged four-object loop is supplied to both implementations.

- B2 header: `git show 199d74d:src/measured_policy.h`; result: 11 history resets, never admits.
- B3 header: current frozen source identified by results.json; result: no reset, eventually admits.
- Compile repeated_miss.cpp with C++20 and the selected header directory on the include path.
- Success exit code is 0; the B2 negative control exits 1. Source and test hashes are recorded.

The old confirmation queue was cancelled before any held-out performance case ran.
B2 development data remain available; they are not silently relabeled as B3.
