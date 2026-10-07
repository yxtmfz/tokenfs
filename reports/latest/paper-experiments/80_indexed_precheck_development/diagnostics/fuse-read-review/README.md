# Cold-read callback splitting: read-only diagnosis

Conclusion: **the frozen evidence does not contain three data-bearing backend
reads per 2 MiB object. It contains two data reads and one cheap EOF check. A
FUSE init/max_read change cannot remove a third remote data read that does not
exist.** The callback splitting is consistent with an unaligned user buffer
exhausting the 256-page direct-I/O request limit, rather than a fixed 1 MiB minus
4 KiB payload limit. Ordinary init negotiation cannot lift Linux v6.8's 256-page
ceiling. This direction should not become the next performance candidate.

No server was accessed, no production source or benchmark changed, no new
performance run was executed. Local Debian headers were extracted without
installing or executing the package. After the headers proved insufficient to
explain the kernel split, the parent allowed consulting the matching official
upstream implementation versions. This is an explanation of frozen77 diagnostic
traces, not a result for candidate80.

## Direct evidence

`hotspot-object77/tail-evidence/{Full,NoHotspot}/request-trace.json` has zero
dropped events. Each arm has 1152 open handles: 1150 disk-backed and 2 captured
RAM reads. Both arms' aggregate `direct_backend_pread_ops` equal 3450; the recorded
pread spans reconcile exactly with that counter.

Typical callback sequences, in returned bytes:

| Arm | First user read | Second user read | Final callback | Number of handles |
| --- | --- | --- | --- | ---: |
| Full, typical disk | 1048128 + 448 | 1048080 + 496 | 0 | 1147 |
| NoHotspot, typical disk | 1047968 + 608 | 1047920 + 656 | 0 | 1147 |
| Either arm, first few disk objects | 1048528 + 48 | 1048528 + 48 | 0 | 3 |

Each pair adds to exactly 1048576. In every disk handle, both large callbacks have
positive `pread_ns`, both small suffix callbacks have zero `pread_ns`, and the
zero-byte EOF callback has positive `pread_ns`. `AlignedReadTail` fetches the
aligned 1 MiB for each large callback, retains the fetched suffix, and serves the
immediately following suffix without another backend call. Aggregate physical
pread **bytes** are 2411724800 = 1150 × 2 MiB: no extra page of successful data is
read beyond those two aligned transfers per object.

The loader in frozen/current `scripts/evidence_benchmark.py::loader` opens with
`buffering=0` and repeatedly calls `f.read(MIB)` until an empty result. It therefore
issues a final read at EOF. In this path `Read` still calls `AlignedReadTail::Read`,
which performs pread, gets zero and returns zero. The extra system-call count is
not an extra MiB or an extra NVMe/TCP data operation.

| Arm / tier | Data preads | Data pread time (ms) | EOF preads | Mean EOF pread (µs) | Sum EOF pread (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full remote | 1954 | 19442.030 | 977 | 2.820 | 2.755 |
| Full local | 346 | 1368.733 | 173 | 2.851 | 0.493 |
| NoHotspot remote | 2004 | 19814.958 | 1002 | 2.870 | 2.876 |
| NoHotspot local | 296 | 1215.147 | 148 | 2.928 | 0.433 |

Removing every EOF backend call, unrealistically for free, would remove only
3.25/3.31 ms of measured pread time in these two full diagnostic runs. The entire
EOF callback totals about 22.8/23.2 ms for disk handles, including other work.
These sums are service-time descriptions, not guaranteed wall or p99 savings.
Skipping EOF would also require preserving source-size and error semantics; a
stale metadata size alone is not a valid replacement. It is not a promising
primary optimization.

The Full remote suffix callbacks total 610.750 ms and NoHotspot 625.628 ms, but
those totals are not all fragmentation overhead. The final suffix completes the
capture and executes accounting and submission work. Consolidating callbacks
would move that required work to the preceding callback, not erase it. Existing
spans cannot separate all of those subcosts. Do not claim a 0.61 s saving.

## Version-specific FUSE explanation

Local `cn7-debs/libfuse3-dev_3.14.0-5build1_amd64.deb` provides the exact 3.14 header
interface; candidate80's saved build log also reports fuse3 version 3.14.0.
`fuse_conn_info` has `max_read` and `max_write`, but no public `max_pages` member.
Its header says max_read remains kernel-limited and must agree with the mount
option. TokenFS does not assign `ops.init`; its Open explicitly enables
`fi->direct_io` according to the frozen configuration.

In upstream libfuse 3.14, session buffer size starts from its internal 256-page
limit; initialization caps max_write to that buffer payload and derives the
protocol max_pages from max_write. max_read mismatching its mount option aborts
initialization. Adding an init callback is not evidence that existing negotiation
was wrong. [libfuse 3.14 low-level implementation](https://raw.githubusercontent.com/libfuse/libfuse/fuse-3.14.0/lib/fuse_lowlevel.c),
[internal page limit](https://raw.githubusercontent.com/libfuse/libfuse/fuse-3.14.0/lib/fuse_i.h).

The historical cn7 receipt `affinity-shared-preflight-cn7.json` identifies
`6.8.0-31-generic`; this is not a fresh server query. Upstream Linux v6.8 initializes
the connection's maximum page limit from 256 and clamps the requested max_pages
to that limit. This review does not claim a byte-for-byte audit of Ubuntu's
patched kernel binary. [Linux v6.8 limits](https://raw.githubusercontent.com/torvalds/linux/v6.8/fs/fuse/fuse_i.h),
[initialization/clamping](https://raw.githubusercontent.com/torvalds/linux/v6.8/fs/fuse/inode.c).

The kernel's direct-read path packs user pages with their starting offset until
the page limit is reached. An unaligned 1 MiB buffer can span 257 pages; with a
256-page limit the first FUSE request can return 1 MiB minus that buffer's page
offset, followed by a short request. This **inference** explains the changing
48/448/496/608/656 suffixes; the trace does not record user pointers or the actual
INIT handshake, so it does not directly prove their addresses. The missing bytes
are not a constant FUSE protocol-header subtraction. [Linux v6.8 direct-I/O page packing](https://raw.githubusercontent.com/torvalds/linux/v6.8/fs/fuse/file.c).

Thus increasing max_read alone does not remove the page-count limit; requesting
more max_write/pages through init still faces the kernel ceiling. Altering kernel
limits, replacing the library, switching to page-cache reads, or changing the
loader's buffer alignment would be a different environment/protocol change, not
a small missing init fix. None is implemented or recommended here.

A future truly common read-path improvement would need evidence that allocation,
copying, capture validation or callback scheduling contributes material avoidable
cost. It must preserve the same input/request workload, direct-I/O semantics,
budgets, source checks and all arms including SIEVE. Current evidence is enough
to reject the third-data-read hypothesis, not to select another unmeasured fix.
Finish the already prepared candidate80 moving trace diagnosis first.

## Reproduction and record

Run `python3 work/hotspot-fuse-read-review/analyze.py` from the task directory.
It reads the two frozen77 traces and verifies the 2 data + 1 EOF pattern for every
disk handle, reconciles callback bytes and the 3450 aggregate pread count, and
writes `evidence.json` here. That file contains source/header/package/receipt and
input SHA256 identities. No frozen input files are modified.

The package headers are under `fuse3-package/usr/include/fuse3`; the package
was decompressed with the bundled Node 24 `zstdDecompressSync`, then unpacked
locally. No package installation occurred. Source links above name immutable
release tags, consulted on 2026-10-07.
