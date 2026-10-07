# Candidate80 moving trace tooling: independent read-only review

Reviewed `work/hotspot-indexed80-moving-trace/{tail-trace.py,tail-trace-analysis.py,collect-trace.py}`
and its freeze/selftest receipts. Their SHA256 identities are in
`moving-trace-reviewed-files.json`. No edits or server execution by this reviewer.

**No blocking issue found; ready for the two authorized diagnostic cases.**

- Run validates the exact original80 freeze, binary and all 355 source hashes,
  Release build configuration, fixed moving_shared/74801/1152 × 2 MiB/24 MiB input,
  and generated object hashes. It uses the original study configuration; only
  diagnostic trace output is added. Full/NoHotspot differ in static H only.
- CPU affinity is set to [0,2,4,6] before spawning the benchmark and checked again
  in each arm's before/after environment receipts. Existing TokenFS process checks
  and unique output/data directories prevent accidental overlap/reuse.
- The original frozen benchmark provides the real release drain fence. The audit
  requires read_release_count=1152, complete request order, indexed activation,
  exact actual partial-index definitions, durable metrics equal to the result,
  submitted=completed, zero error counters, and bounded retained/capture bytes.
- The parser joins client requests to actual unique daemon handles and verifies
  path/caller/tier/bytes/timing. Cross-arm comparison uses the same logical
  ordinal/key/caller and preserves each realized route. Both top12 sets contribute
  to the union; it does not match by latency rank.
- Per-request physical pread counts/bytes remain null because the trace lacks
  those explicit fields. Aggregate counters are reported separately. In particular,
  a positive pread_ns on an EOF callback must not be interpreted as a data-bearing
  remote device read.
- Copy/plan/release overlap is explicitly association, not summed causal delay.
  Release can occur after client close. Non-pread residuals are not labelled as
  SQLite fsync time. Trace results are marked diagnosis-only, never acceptance
  speed evidence; the public77 files are only parser-compatibility tests.
- Collector preserves the entire stopped evidence directory including sidecars,
  without checkpoint/unlink/kill. Immutable SQL analysis refuses any sidecar;
  this can require later explicit evidence handling but avoids silently ignoring
  WAL. Failed/partial archives remain available with receipts.

This review checks code and the saved local selftests, not a completed80 trace
run. `audit` should be run and pass on the collected evidence before interpreting
`tail-trace-analysis.py` output; its convenience analyzer is not a replacement
for the complete source/binary/CPU audit.
