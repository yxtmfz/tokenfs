# Independent review: default-off shared submission precheck

Reviewed current `src/main.cpp`, `src/measured_policy.h`, `src/read_fill.h`, schema and new native tests. No repository source was edited by this reviewer, and no server was accessed. Native integration execution is owned by the implementer; this review independently ran the policy upper-bound property check described below.

## Conclusion

The current design is a valid **current-snapshot optimistic admission rejection**, under its documented fresh, exclusively managed, immutable cache lifecycle. It is not an equivalence proof for the old queued task, which would inspect future demand/cost state. It also does not protect an out-of-band cache deletion/truncation or canonical-source mutation. The performance result must include the new foreground SQL/policy work and any changed online actions.

No unresolved blocking issue was found after fixing the orphan READY startup check.

## Issue found and resolved

The initial startup proof reused the online READY query, whose `JOIN files` hid orphan replica rows. A stale READY row could be invisible at empty-cache startup, then become visible after a later first read creates its canonical metadata row, falsely increasing the occupied-byte lower bound while its physical file does not exist.

The implementation now uses `TryEmptyResidentState`: startup requires no local-tier files and no replica rows of any state, without the JOIN. The `submission_precheck_startup` test covers an orphan READY row before startup and the later canonical discovery. The entire instance remains in fallback mode.

## Verified design properties

- Empty cache roots are checked before the worker starts. Canonical roots must not alias or nest; duplicate GPU IDs, pre-existing data and stale residence metadata disable the optimization. Online paths must be absolute descendants of the corresponding configured root.
- A physical path represented more than once with consistent domain/size contributes only once. Conflicting sizes/domains and malformed/unknown rows cause normal submission. Temporary/unpublished files omitted by the query only reduce the estimated occupied bytes, which is conservative.
- Layout and metadata mutex acquisition use `try_lock`. Layout is held across the occupancy snapshot and rejection decision, preventing internal eviction from reducing occupied bytes in between. New copy publication may add occupancy, so omission remains conservative. The SQL still scans predicates; it is not constant-time or entirely wait-free.
- Prefiltering requires a complete validated capture with a matching, nonzero incoming size. Missing/partial capture and mismatched sizes use the original path. Cache/source immutability is an explicit environmental assumption, not something `readonly_canonical` enforces against external processes.
- Every permitted domain must lack free headroom. Caller-only placement retains its location restriction. Ineligible PoolSIEVE and other policy configurations do not acquire a new profitability gate.
- The supported configuration requires shared causal demand and disables the location-dependent affinity gate. Its incoming value, incoming uncertainty and copy cost are location-independent. One call to the original `PotentiallyProfitable`, with `used=quota` in a domain that can fit the object, checks the common optimistic bound under one policy mutex. Oversize domains cannot admit. This avoids a multi-domain loop using different history/cost snapshots.
- The original arm options are passed unchanged, including static H and joint/no-joint charging. The NoJoint test specifically covers an incoming value that repays copying but would fail if incoming noise were incorrectly charged.
- The check happens before inserting the shared-inflight token. A rejection cannot strand that token or block a later profitable request. No negative-key result is cached. Existing background source, capacity and pin checks remain in place for submitted tasks.

The new lock order agrees with the existing Open/EnsureLocalCapacity path: layout, a short metadata operation, then policy. No new reverse nested lock path was found. ScheduleSharedPlacement is called after Open releases layout and after Release drops the handle-table lock.

## Independent check and test review

`representative_upper_bound.cpp` uses the actual current `measured_policy.h` and performs 110,592 comparisons across three domains, three object sizes, multiple full/overfull quotas, H/static H, joint/non-joint, and cold/calibrated cost states. All position-independent bound comparisons passed; oversize destinations rejected. See `representative_upper_bound.log`. This is an arithmetic/logic property check, not workload speed evidence.

Reviewed native test source covers default-off/YAML, empty/full capacity, later same-key profitability, actual rejected scheduling without queue insertion, NoH/NoJoint combinations, caller-only placement, both busy mutex fallbacks, invalid sizes/GPU/path prefixes, physical alias accounting, conflicting duplicate metadata, invalid roots/nonempty startup, and the orphan READY regression. Execution results should be taken from the implementer's current native sanitizer logs, not inferred from this static review.

## Model archive

The earlier migration model is archived in `migration-model-source.tar.gz`, with 263 source/text files and no compiled binaries. SHA-256: `11226a336b7db9b07e7c5959eba7e321cfca198fc3af87bff123ffa624711d33`. The accompanying manifest identifies every member. Frozen 78 source/results were not modified.
