# Shared-cache opportunity pilot (2026-09-24)

This is a new exploratory storage-path experiment, not a third confirmation of
D/E affinity prediction and not a GPU inference result. Old failures are retained.
Fixed budget: **18 speed cases + 3 content verification cases**. Larger follow-up
requires user approval. No outcome-dependent workload removal or tuning within
this pilot. Correctness/build failures may be fixed before speed runs begin.

## Question and controls

Private logical partitions cannot read peer READY replicas, although physically
on the same client disk. Existing shared mode exposes the canonical owner's
local copy, but not another caller's replica. Test whether completing this path
reduces genuine NVMe/TCP reads and copies.
All arms: same H reset, J admission, 8 MiB per partition (24 MiB total), immutable
payloads, copy implementation, O_DIRECT reads, input order and empty application
cache. No artificial latency, extra capacity, preloading or future information.

- Private: per-caller replicas, private_cache_domains=true.
- OwnerShare: existing shared mode, private_cache_domains=false.
- AnyReadyShare: OwnerShare plus peer_cache_reads=true. On a remote miss, reuse
  an extant READY replica, pin the file under the layout lock, update recency,
  and avoid scheduling a second copy on that borrowed hit.

OwnerShare is the stronger existing reference. Private is a policy ablation,
not a claim hardware forbids sharing. This tests a data path, not prediction.
Peer reads require immutable canonical data and a shared address space. They
are not CUDA P2P, NVLink, cross-host sharing or inference. An in-flight duplicate
may still finish; this is not perfect single-copy coalescing. Borrowed frequency
is not credited to the resident's value predictor, a retained known limitation.

## Fixed matrix and stopping

Two synthetic scenes x seeds2701–2703 x three arms = 18 speed cases.
Randomized block order and arm order. Each:384 requests x2MiB=768MiB; three
serialized callers cycle0,1,2. Shared_capacity:85% choose one of six shared keys,
15% cold keys32–63. Six hot objects exceed one partition's four-object budget
but fit aggregate capacity. This deliberately tests a capacity opportunity,
not production representativeness. Disjoint:each caller chooses its own four
keys, no sharing; a negative control. Old uniform results remain separate.
Three short correctness cases use seed2699 and96 requests, all checksummed.
Retained copies are verified outside timing in every speed case.

Rate=actual logical bytes/full monotonic foreground time, including control and
pipe/FUSE time. Report background drain, remote/copy/peer bytes, CPU and p99.
Server caches are uncontrolled. No significance claim from three pairs.
Promising means:all three shared pairs faster than OwnerShare, paired geometric
speed gain>=5%, active peer reads and reduced remote bytes, and mean paired
disjoint regression<=3%. Even then request approval before expanding. Otherwise
publish the negative/null finding without retuning or adding runs.

H is held ON:cannot prove H/P interaction or a new joint controller. A later
approved H/P2x2 must hold other settings fixed; never add component percentages.
Sharing gain alone does not establish a new affinity algorithm. Possible next
research question:cost-aware replica placement/retention versus this simple
AnyReadyShare and equal-total-capacity pooled caching under moving reuse and
contention. This must be tested, not assumed novel.

Primary prior art:Preble https://arxiv.org/abs/2407.00023 co-optimizes KV reuse and
compute load balancing; Mooncake https://www.usenix.org/conference/fast25/presentation/qin
uses a global KV cache and SLO-aware scheduler. Novelty must be narrower than
shared caching, affinity or combining caching with scheduling.
