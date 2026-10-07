# 78 frozen protocol pre-audit

This is a local source/tooling review while the server batch is running. No server connection or result selection was performed. It does not certify 78 performance; raw speed and correctness evidence is still required.

The actual source archive contains exactly 345 files matching `source-hashes.json`; SHA256 is `c9ba5be4549aae563594a09c110a53d1b95a99bd63d033910b36bfbd4e4eeb76`. Build output records binary `fa7450237ef5fc4a9291ed79f057f48bb858caed784c7ff56a454e242ae58cfe`, 12 native tests and 161 Python tests passed. The binary entity is not currently available locally; this is a build receipt, not an independently rebuilt executable.

## Final Release and drain

The new option key is present for every arm, including the `SyncSubmission` arm with `defer_background_submission_metrics=false`; the benchmark detects key presence rather than truthiness, so the same Release fence protocol applies to all six arms. A valid readonly Release finishes possible fallback submission, increments `read_release_count` once, then flushes. Repeated Release does not increment it again. Deferred acceptance is buffered before the queue mutex permits a worker to consume the task. Completed counts are buffered only after the task ends. A serialized transactional flush publishes the corresponding counters/events; a failed transaction restores pending data and error state before a retry can publish completion.

The benchmark's drain reads all metric counters from one SQLite snapshot and requires both `read_release_count == expected requests` and `background_submitted == background_completed`. Thus an old durable 0/0 pair cannot hide the final unflushed submission. Duplicate releases, background errors and missing Release fences fail. The full drain waiting time is recorded. After shutdown, `finalize_case_metrics` rejects any late changes to release/submission/completion and I/O counters; the offline verifier independently checks exact release count and durable SQLite agreement.

Foreground throughput and request p99 retain their original application-response definitions. They do not claim to include the completion of every asynchronous Release/background callback. A separate completion-with-background time is measured, and nonnegative drain-adjusted improvement is required for acceptance. This distinction must remain in the results report.

## Controls and acceptance

The fixed matrix remains two inspected inputs × two reversed-order rounds × six arms, 24 runs with 1,152 requests each; six separate 96-request SHA runs follow. Full/NoHotspot, Full/NoAffinity and Full/NoJoint each have exactly one strategy flag difference. Full/SyncSubmission differs only in `defer_background_submission_metrics`. Both use the new binary, common read path, SIEVE fix, H prior and Release counting; it is an implementation control, not a fourth strategy innovation or a frozen-77 binary comparison.

Primary acceptance contains exactly 16 comparisons. Each round requires positive throughput, lower p99 and nonnegative completion-with-background gain, plus its required mechanism/action conditions. `SyncSubmission` has four separate implementation comparisons and does not require changed cache actions. A deterministic adversarial fixture with positive aggregate throughput/p99 but a failing second round yielded only 8/16 primary passes; aggregation cannot convert that batch into a full pass. Existing tests also verify unchanged-action Sync can pass while unchanged-action NoHotspot cannot.

## Collection guard added outside frozen source

The original suffix-filtered collection command could silently exclude a remaining SQLite WAL/SHM. Even though successful process shutdown normally removes these, silently dropping one is unsafe for subsequent immutable offline reads. Root authorized adding an explicit rejection of any `state.db-*` before opening the tar archive. This modifies only `work/hotspot-submission78/collect.sh`; the source/spec/results are unchanged. Shell/Python syntax and a temporary WAL rejection check passed. The updated collector SHA is recorded in `preaudit-review.json`.

## When raw data arrives

Check download SHA and raw archive membership before extraction; reject WAL/SHM and failed/extra attempts. Run `verify78.py` against the exact source archive in a fresh external review directory, preserving raw bytes. Verify 345 source hashes, 30 binary receipts, all 27,648 speed requests and 576 SHA checks; reproduce every rate/p99, both execution orders, exact config/input payloads, durable SQL, and strict 16 primary/4 Sync decisions. Review mechanism counters separately, particularly whether a small H timing difference has identical physical work. Do not fill failed cells from 77 or from traced diagnostics. Archive all positive and negative results alongside frozen source, collection receipts and this pre-audit.

Local reproducible checks are in `preaudit78.py`, `preaudit-review.json`, `preaudit-release-tests.log` and `verifier-independent-review.json`.
