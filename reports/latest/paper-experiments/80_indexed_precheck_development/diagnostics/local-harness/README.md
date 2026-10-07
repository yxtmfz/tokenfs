# Candidate80 local validation

The executable tested here contains the exact current `Config`, `MetadataStore`
and `TokenFS` implementations extracted from `src/main.cpp`, plus the actual
native test methods from `tests/policy_metadata_test.cpp`. The harness supplies
unmounted macOS FUSE declarations and unused Linux allocation-call compatibility.
It does not include YAML parsing or the mounted daemon entry point. The complete
Linux native suite, including the added YAML default/on/off assertions, is a
separate validation step owned by the parent task.

ASan and UBSan completed successfully. `run.log` includes intentional injected
error messages from the background telemetry tests; the final PASS is after all
expected exceptions, not an ignored process failure. The three candidate80 groups
cover indexed query equivalence and plan/scan work, activation eligibility and
schema persistence, and real SQL/setup failure recovery. Existing candidate79
precheck and candidate78 deferred telemetry/fence tests run in the same executable.

Observed SQLite full-scan step counts: **4101 unindexed, 3 indexed**. Both intended
indexes appear as COVERING INDEX scans in the actual query plan. This is a query
work check, not an end-to-end throughput or p99 measurement.

Reproduce from the repository directory:

```sh
python3 ../hotspot-index80/local-validation/build_harness.py
clang++ -std=c++20 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -I src ../hotspot-index80/local-validation/telemetry_harness.cpp -lsqlite3 -pthread -o ../hotspot-index80/local-validation/telemetry_harness
../hotspot-index80/local-validation/telemetry_harness > ../hotspot-index80/local-validation/run.log 2>&1
```

`source-hashes.json` identifies the two source files used to generate the harness.
`reviewed-files.json` additionally identifies the new implementation document.
A source edit requires regeneration and rerunning; the harness is not a substitute
for Linux/FUSE integration. No server was accessed for this validation. No older
frozen evidence was changed.
