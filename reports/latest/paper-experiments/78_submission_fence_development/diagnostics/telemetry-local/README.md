# Candidate 78 local telemetry validation

This is a local correctness harness, **not performance evidence** and not a substitute for Linux/FUSE native tests. `build_harness.py` copies the actual current `src/main.cpp` prefix containing Config, the full MetadataStore, and the full TokenFS class. It copies the native TokenFSTestAccess implementation. It does not reimplement queue, SQL transactions, Release, or metric-fence logic. `source-hashes.json` identifies the two source files used.

The platform veneer provides unmounted FUSE declarations (`fuse_get_context` returns null), O_DIRECT=0 on macOS, fdatasync via fsync, and an unused unsupported allocation function. YAML parsing, daemon main, actual FUSE transport/mounting and kernel O_DIRECT behavior are not exercised. The new native YAML flag parsing check is intentionally excluded here and must run in the Linux `policy_metadata_test`.

Commands, from the repository root:

```sh
python3 ../hotspot-common78/telemetry-local/build_harness.py
clang++ -std=c++20 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -I src ../hotspot-common78/telemetry-local/telemetry_harness.cpp -lsqlite3 -pthread -o ../hotspot-common78/telemetry-local/telemetry_harness
../hotspot-common78/telemetry-local/telemetry_harness > ../hotspot-common78/telemetry-local/run.log 2>&1
```

Executed successfully under AddressSanitizer and UndefinedBehaviorSanitizer. Checks cover legacy batched/unbatched completion fences; accepted submission without foreground durable wait; before/after fence visibility; standard and unknown task exceptions; SQL triggers rejecting submitted, completed, and policy-event writes; retry through foreground, next task and destructor; exactly-once counters and ordered events; queue capacity and stopping; readonly Release transaction rollback, repeated/unknown Release, and exclusion of writable Release; existing Release lock behavior. A deterministic failed-fence handoff test pauses the calling worker-side outer catch while a foreground fence retries, ensuring the error is already in the restored batch before completed can become durable.

The modified opt-in is default false and requires `batch_background_metrics=true`. No durability mode or core data/copy/metadata transaction is changed. Persistent SQLite failure at destruction retains the pre-existing limitation: successful final durability cannot be promised if the final fence continues to fail. These checks validate recovery after the injected fault is removed.
