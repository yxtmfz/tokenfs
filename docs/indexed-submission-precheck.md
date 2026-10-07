# Indexed metadata for the shared submission precheck

`policy.indexed_shared_precheck` defaults to `false`. It requests two partial
covering SQLite indexes only after `precheck_shared_submission` has passed its
existing fresh, exclusively managed, immutable cache eligibility checks. The
flag may be present in unsupported configurations, including shared SIEVE; it
is ignored there. It does not enable the precheck by itself.

The query, metadata validation, path deduplication, capacity bound, policy
options and rejection rule are unchanged from
[the submission precheck](submission-precheck.md). This candidate reduces the
rows SQLite must scan to construct the resident snapshot. It does not change
hotspot estimation, affinity or joint admission, and it adds no shortcut for
one ablation arm.

The indexes are:

```sql
CREATE INDEX idx_files_shared_precheck_local
ON files(gpu_id,physical_path,size_bytes)
WHERE tier='local' AND state='COMMITTED';

CREATE INDEX idx_replicas_shared_precheck_ready
ON local_replicas(logical_path,gpu_id,physical_path,size_bytes)
WHERE state='READY';
```

The first restricts scanning to committed local canonical files. The second
restricts scanning to READY replicas and supplies the columns for the existing
join to `files`, whose primary key checks the canonical state. Orphan replicas
remain excluded; duplicate rows remain present for the existing path validation
and deduplication step. Every relevant state transition updates the indexes
through the original SQLite transaction. No core copy or metadata transaction,
WAL setting or durability fence is relaxed.

Index setup happens before the background worker starts. Both DDL statements
run in one transaction. `IF NOT EXISTS` is followed by an exact schema-definition
check, so a foreign same-name index cannot be reported as the intended index.
Equivalent hand-written definitions with different formatting may conservatively
fail this check. Existing indexes are never dropped or replaced. On an ordinary
SQL failure, the transaction rolls back all newly created indexes and the
original unindexed precheck remains available. If SQLite still has a transaction
open after the rollback attempt, initialization throws instead of continuing
with uncertain transaction state.

Startup telemetry distinguishes the outcomes:

| Metric | Meaning |
| --- | --- |
| `submission_precheck_enabled` | Existing precheck lifecycle checks succeeded. |
| `submission_precheck_index_enabled` | Both requested definitions were verified and setup committed. |
| `submission_precheck_index_fallback` | Setup failed and recovered; the original query is retained. |

The index metrics are zero when the flag is off or the precheck is unsupported
or ineligible. Setup failure does not count as enabled. These are buffered
startup counters persisted through the existing telemetry fence. The enabled
counter confirms schema setup; it does not force SQLite to choose an index for
every future database size or SQLite version.

Turning either flag off is not a schema migration. A reused database retains
its existing indexes and their maintenance costs. Therefore the experiment's
claim that SIEVE and the unindexed control pay no new index maintenance cost
requires the existing protocol's separate fresh database per case. A recovered
fallback may also retain foreign or previously created indexes; a strict indexed
versus unindexed experiment must reject fallback cases rather than silently mix
them into a treatment arm.

The optimization adds index maintenance work to local state changes and replica
insertion/removal. Lower snapshot scan work is not itself a throughput or p99
claim. Evaluate the whole run, including copy and metadata work, with the same
source, inputs, budgets and measurement fences. All original precheck limitations
still apply, including submission-time versus later worker-time decisions and
the requirement that external processes do not alter the source or cache.

Native regression tests use the exact production query. With 4096 unrelated
remote canonical rows they check both index names in the actual query plan and
compare SQLite full-scan step counters. They compare the full result multiset
against an unindexed database through committed/deleting/copying and replica
READY/CREATING transitions, including duplicate paths and a formerly orphan
replica. Additional tests cover all measured ablation configurations, disabled
flags, SIEVE, failed lifecycle checks, retained schema after flag-off restart,
YAML defaults, second-DDL name collisions, incompatible existing definitions,
and a real SQLite authorizer that denies rollback. The last failure must escape
the precheck eligibility catch.
