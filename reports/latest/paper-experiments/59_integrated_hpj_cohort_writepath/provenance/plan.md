# Reuse compiled accounting and telemetry statements

Cohort candidate gives all three component throughput gains in both orders, but Full versus SIEVE is+4.42%/-2.20%. Preserve all ten results. Previously profiled open accounting takes1.7–2ms per logical read, and telemetry flush about0.7ms. Both still compile the same SQL writes on each operation.

Cache only a fixed set of compiled SQLite accounting/telemetry statements, under the existing store mutex. Clear bindings/reset on every scope exit including errors; no cached query results. Preserve transaction boundaries, FULL-WAL commits, delta-before-maximum order, read/access counts, replica touches and legacy affinity behavior. Native test injects failure after an earlier accounting update, retries after schema invalidation, checks concurrent exact counts and reopens the durable database; existing telemetry rollback/fence tests remain required. This applies equally to all arms. H/P/J formulas and trace remain unchanged from the cohort candidate.

Same ten uninstrumented moving3293 runs, same576 requests,24MiB disk and4MiB RAM, all5arms in complete reversed orders, fresh state per run. No seed/order/result selection. Throughput target: all four gains positive in both rounds. Report all tail/drain/mechanism flags separately. No claim of physical GPUs or statistical significance.
