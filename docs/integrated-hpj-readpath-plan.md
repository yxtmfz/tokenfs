# Shared read-path and atomic replica publication follow-up

The telemetry candidate's moving gain over SIEVE reversed from+2.03% to-2.47% in the complete reverse replication. Preserve both batches. Do not call the first run a global gain. Full uses additional peer-metadata queries and cross-domain replica updates compared with a one-domain pool.

Reuse compiled SQLite statements for exactly three hot READ queries (canonical lookup, caller replica lookup, peer list), under the existing store mutex. Reset/clear bindings after every use, including early return and errors; cache no query results or filesystem validity. SQLite prepare_v2 automatically recompiles after schema changes. Finalize statements before closing the connection. No changed fsync or data budget.

Publish READY replica metadata and canonical promotion bookkeeping in one FULL-WAL transaction instead of two autocommits. Missing canonical metadata or any failed update rolls back both. Actual copying, hashes, source validation and final capacity checks remain unchanged. This applies to all modes using these paths. Native checks cover schema invalidation, missing/insert/update/delete transitions, concurrent readers, injected second-write failure and successful retry.

Same15 frozen small runs as telemetry: stationary3271,moving3293,uniform3273,576x2MiB,24MiB disk,4MiB total capture, all5arms, same order/input/one-flag ablations. This is a separately archived candidate, not a replacement for failed results. No threshold changes, workload-specific switches, baseline restrictions or selective reruns. Predeclare a whole reverse replication of this candidate if validation succeeds, plus separate480-request content verification. All performance gates unchanged; inactive H/J stationary remains unproven.
