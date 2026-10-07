# RAM value ranking: negative development result

Local model only, no server run and no production source modification. Uses frozen78 policy headers (the same object-weighted H as77), all ten existing development inputs, original 24 MiB shared disk geometry, and exactly two 2 MiB RAM slots. Current79 prefilter source is not used.

**Do not promote this candidate.** Both tested value-ranking forms regress against NoH on two of four moving inputs. The physically corrected form also loses on two public inputs and uniform. No ratio or parameter search followed these results.

## Designs and fairness

1. `lru`: reproduce the existing shared RAM LRU, for all four arms.
2. `ranked`: always protect/admit the currently read complete capture, and evict the lowest-ranked *old* RAM object using original `MeasuredPolicy::Ranked`. Full uses original H values; NoHotspot uses its original static values through the same method. NoAffinity/NoJoint retain their own original options. Every RAM candidate has coverage1.
3. `marginal`: same algorithm, but RAM candidates with a readable disk copy use coverage1, while remote-only candidates use coverage2. This follows the existing model's 21 ms remote, 10.5 ms disk and zero RAM service costs; it is not a tuned coefficient and does not use SSD `MarginalCoverage`'s 0/1 redundancy rule. Both H and NoH receive the same correction.

Disk policy and admission triggers remain unchanged. Memory never exceeds two object slots, and runtime guards ensure that the current object is never evicted. PoolSIEVE production code remains unchanged/LRU; it is not part of this four-arm policy replay and no SIEVE speed claim follows.

## Results

Every cell reports remote reads / disk hits / RAM hits / copies. Positive savings favor Full. The score is `21*remote + 10.5*disk + 8*copies` milliseconds; it ignores overlapping work and control cost, so it is **not** actual wall time, throughput or p99.

| Input | RAM | Full | NoH | Full saving vs NoH, ms |
|---|---|---:|---:|---:|
| moving73501 | ranked | 79 / 149 / 924 / 29 | 79 / 152 / 921 / 28 | +23.5 |
| moving73502 | ranked | 83 / 160 / 909 / 28 | 85 / 151 / 916 / 28 | -52.5 |
| moving73503 | ranked | 78 / 154 / 920 / 28 | 80 / 154 / 918 / 28 | +42 |
| moving74801 | ranked | 84 / 151 / 917 / 28 | 84 / 149 / 919 / 28 | -21 |
| moving73501 | marginal | 79 / 149 / 924 / 29 | 79 / 152 / 921 / 28 | +23.5 |
| moving73502 | marginal | 83 / 159 / 910 / 28 | 85 / 151 / 916 / 28 | -42 |
| moving73503 | marginal | 78 / 154 / 920 / 28 | 80 / 154 / 918 / 28 | +42 |
| moving74801 | marginal | 84 / 150 / 918 / 28 | 84 / 149 / 919 / 28 | -10.5 |
| public73601 | marginal | 852 / 278 / 22 / 33 | 858 / 271 / 23 / 24 | -19.5 |
| public73602 | marginal | 859 / 273 / 20 / 36 | 846 / 283 / 23 / 23 | -272 |
| public73603 | marginal | 908 / 220 / 24 / 28 | 927 / 203 / 22 / 20 | +156.5 |
| public74802 | marginal | 964 / 165 / 23 / 33 | 995 / 130 / 27 / 23 | +203.5 |
| stationary73701 | marginal | 65 / 173 / 914 / 12 | 65 / 174 / 913 / 12 | +10.5 |
| uniform73702 | marginal | 521 / 551 / 80 / 39 | 537 / 515 / 100 / 37 | -58 |

`tables.md` includes every input in all three forms, including the original LRU comparison. `results.json` includes all four arms, not just Full/NoH. In moving74801, original Full LRU is84 remote/148 disk/920 RAM/28copies; either value rank is worse even against Full's own LRU. Public Full usually benefits versus its own LRU, but that does not establish H's advantage over the equally ranked static comparator.

## Verification

- 120 development arms retained: ten unchanged inputs × three RAM policies × four ablation arms.
- All original40 LRU arms reproduce the earlier frozen77 capacity model's remote/copy/RAM/disk counts exactly.
- All arms account for1152 requests, respect the two-slot bound and protect the current capture.
- 90 prefix cases /360 verification arms cover all ten inputs, three policies and cutoffs127/401/806. Every request source, RAM eviction and disk-copy decision equals the corresponding full-run prefix. See `prefix-verification.json` and the retained prefix logs. This rules out consuming future input records in this implementation; it is not an independent statistical validation set.
- Header hashes are in `verification.json`. All full request/decision traces are under `logs/`, and all prefix cases under `prefix/`.

## Physical limitations

This replay serializes requests and completes copies instantly. The real `ReadFillPool::Acquire` reserves space during Open after Observe and before I/O completes; it may evict an old capture even when the new read later fails or remains partial. Captures pinned by readers or queued copies cannot be evicted. If both slots are pinned, a real implementation must preserve `capture_unavailable`; “protect/admit current” is not permission to exceed the byte budget. These timings are not modelled here. A future implementation callback would need to rank only plain key/size/recency candidates, not copy shared pointers and accidentally change pin counts.

The original H estimator was designed for disk admission and scales logical history by burst reuse. Reusing that score for RAM replacement does not by itself prove a correct short-horizon RAM forecast. The derived service-cost correction addresses one clear objective mismatch, yet negative results persist. No further coefficient search or production edit is justified by this batch.

## Frozen diagnostic provenance

This artifact was prepared after frozen78 completed and while candidate79 measurements were running/being collected; it does not use candidate79 performance outcomes. It is diagnostic/development evidence, not a new performance validation run. The first physical copies arose from the original bounded capacity warmup; subsequent early resident reuse supplies the first local cost samples, so both first-copy selection and completion timing can affect later online estimates. The current raw records cannot uniquely separate online cost sampling from asynchronous scheduling effects. The RAM replay uses fixed costs and immediate copies and cannot answer that timing question.
