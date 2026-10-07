# Candidate80 indexed precheck: independent read-only review

**No blocking finding remains in the reviewed implementation.** Suitable to freeze for native Linux verification; no actual performance improvement is asserted by this code review. No repository source, Git state, server or existing experiment evidence was modified by the reviewer.

Reviewed main.cpp SHA256: `2877d41476b903069092c688ec8b884a5f514d7a7395b616407451e5b23ce6e1`.
Reviewed policy_metadata_test.cpp SHA256: `4125d266e0bd7d8c030c94e89fca0449bf766a0b51f259ff70d70fccc8d41b3f`.

## Safety, compatibility and semantics

- The production resident SELECT is byte-for-byte identical to frozen79, now held in a shared constant. Partial indexes change its access path, not its predicate, UNION ALL multiplicity, orphan handling or canonical-state requirement. Original path deduplication and malformed-row fallback remain unchanged; output ordering is not used as a decision criterion.
- Index creation occurs only after existing fresh-cache eligibility succeeds, and before the background worker starts. Full/NoH/NoP/NoJ receive the same eligibility and index implementation; SIEVE, disabled precheck and ineligible lifecycles create no new indexes. DDL takes only the metadata mutex at this startup point, with no new runtime lock ordering.
- Both CREATE statements and exact existing-definition checks are in one transaction. Ordinary failure rolls back newly created schema, leaves older indexes/data intact, and records fallback. Same-name foreign definitions are conservatively rejected without DROP. Startup requires an idle SQLite transaction; after any failure, an unrecovered active transaction throws through Init. The setup call is outside the eligibility catch, so this fatal condition cannot be swallowed.
- These points resolve the initial review findings: IF NOT EXISTS alone accepted wrong definitions, the earlier eligibility catch would hide fatal transaction errors, and a claim that disabled controls never maintain indexes was too broad.
- Persisted indexes survive flag-off restart. Fairness therefore depends on the fixed fresh-database-per-arm protocol. Existing or foreign indexes may survive a fallback; treatment audits must reject fallback rather than call it a clean indexed/unindexed comparison. The final documentation explicitly says this.

## Verification inspected and independently performed

The implementer's local actual TokenFS/MetadataStore harness passed ASan+UBSan, including old telemetry/release/precheck regressions. Its exact query reports full-scan steps4101→3 with both expected covering indexes. The reviewer inspected native tests covering result multiset equality (duplicates/orphans/noncommitted canonical rows), relevant state transitions, all four measured arms, fresh SIEVE/disabled controls, restart compatibility, second-DDL conflict, incompatible existing definitions, existing schema preservation and authorizer-denied rollback propagation. Source hashes above match the harness receipt. This is the unmounted macOS veneer, not the Linux FUSE build.

Independently, a read-only copy of frozen79 public Full's SQLite database was backed up to an in-memory connection. The production query's12rows were identical before/after indexing with864canonical rows and8replicas. The local SQLite plan changed both scans to the expected covering indexes; replica rows still require a primary-key lookup of canonical file state. A real second-CREATE table-name conflict rolled back both new indexes; a previously existing first index survived, as required. The source evidence file hash remained unchanged. The initial independent SQL proof intentionally demonstrates why IF NOT EXISTS alone is insufficient; the final C++ implementation now additionally validates definitions.

Artifacts: `work/hotspot-index80-independent-review/sql-review.json`, `review_sql.py`, `final-diff.txt`, `final-source-identity.json`; native receipt/log: `work/hotspot-index80/local-validation/source-hashes.json`, `run.log`.

## Performance limits

SQLite may choose a different plan on other versions or distributions; schema-enabled telemetry does not guarantee an index is chosen. Local/replica insertion, state changes and removal maintain these indexes through the original transactions. The common read-count/last-access fields are not indexed, but no zero-maintenance-cost claim is made. Any write/storage overhead, scheduling changes and resulting policy choices must remain in whole-run throughput,p99 and drained measurements. This common metadata optimization is not independent H/P/J strategy novelty and does not establish H benefit when Full/NoH perform identical I/O.
