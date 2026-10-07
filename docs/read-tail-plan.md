# Read-tail I/O repair and hotspot diagnostic (75)

This is a fixed small development diagnostic, not a completed four-table result. The known moving/public inputs remain unchanged. No run is repeated or dropped based on its performance.

A 2 MiB request in report73 was split by FUSE into 1048528, 48, 1048528, 48 and EOF. The original aligned O_DIRECT path reread a 4 KiB page for each 48-byte piece. The new optional per-open tail buffer retains only already-fetched unused bytes, with descriptor identity/size/mtime/ctime validation before reuse; stale, discontinuous or partially covered reads use normal pread. Every read uses the same alignment and no additional read-ahead.

## Fixed matrix and interpretation

Two scenes (moving74801, public74802), two reversed orders, four arms = 16 runs of 1152 x 2 MiB. Full and NoHotspot use the existing report70 estimator and its original static ablation; the rejected report74 disk-opportunity switch stays off. Full/NoHotspot enable the tail optimization; NoTail/NoHotspotNoTail disable only that switch. All four use one frozen binary. Thus Full vs NoTail and NoHotspot vs NoHotspotNoTail isolate the common read-path repair; Full vs NoHotspot is diagnostic only for the original H comparison. This batch cannot establish P/J effects or final acceptance.

Capacity: unchanged 24 MiB total disk and 4 MiB shared capture. Additionally, enabled arms allocate at most one 4096-byte tail payload per live non-RAM reader, released with its handle; report its peak separately. Every enabled arm uses the same rule, and any later H/P/J/SIEVE comparison must enable it equally. This small extra per-open memory must not be described as included in the 4 MiB retained cache.

Keep actual foreground wall throughput and complete request response p99. Do not remove cold requests. Content checks are separate and excluded from speed statistics. Require source/binary/config receipts, correct logical byte counts and exact response-time recomputation, zero read/content errors, final replica content checks, and all background tasks complete. Record physical pread calls/bytes, tail hits/bytes, and extra payload peak to test the proposed mechanism. Run 96 independent content-verified requests for each arm (384 total).

## Scope

cn7 logical consumer domains, cn13 NVMe/TCP mount; no cn14 access and no physical-GPU claim. Native tests and Python regression checks precede timing. The opt-in switch is not promoted based solely on synthetic tests or one favorable round. New local hotspot models are retained as model evidence; none of the screened variants demonstrated sufficiently consistent benefit to replace the estimator in this batch.
