# Candidate 79 local native-code validation

Result: PASS with AddressSanitizer and UndefinedBehaviorSanitizer, using the actual current Config, MetadataStore, TokenFS class, and native TokenFSTestAccess methods copied into an unmounted macOS harness. `source-hashes.json` binds main.cpp and policy_metadata_test.cpp. These hashes were checked again against the working files after the final successful run. The generated class code contains the real submission precheck, locks, SQLite query/transactions, worker, and Release implementations; it is not a causal performance model.

Scope exercised: all new precheck decision/ablation/lock/metadata/startup tests, all prior 78 deferred-telemetry tests, and legacy background-fence/Release checks. The final run includes partial capture and changed-source-before-capture-completion fallback. Native tests for the new YAML flag true/false/default were added to policy_metadata_test.cpp but require the full Linux build; the local harness excludes YAML and daemon main.

The platform veneer provides unmounted FUSE declarations (fuse_get_context returns null), O_DIRECT=0 on macOS, fdatasync via fsync, and an unused unsupported allocation function. Therefore this is not a mounted FUSE, Linux O_DIRECT, or performance test. Existing content/Source identity methods used by these fixtures execute normally against local files. Full Linux native tests remain a separate frozen-build gate.

Reproduce from the repository root:

```sh
python3 ../hotspot-precheck79/local-validation/build_harness.py
clang++ -std=c++20 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -I src ../hotspot-precheck79/local-validation/telemetry_harness.cpp -lsqlite3 -pthread -o ../hotspot-precheck79/local-validation/telemetry_harness
../hotspot-precheck79/local-validation/telemetry_harness > ../hotspot-precheck79/local-validation/run.log 2>&1
```

The independent reviewer separately checked 110592 fixed policy snapshots for equivalence of the representative-domain optimistic bound under its restricted support conditions. Its sources/log/report are in work/hotspot-next-review. This does not establish equivalence with an original queued task consulting future observations or costs.

Implementation limitations and protocol interpretation are documented in repo docs/submission-precheck.md. No server was contacted by this implementation subtask, no benchmark workload or measurement script was modified, and no commit was made by this subagent.
