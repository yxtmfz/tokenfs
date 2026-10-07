# Mechanism models, not measured throughput or p99

`object-prior/` contains the development screen that motivated frozen 77, although its original working directory was named `hotspot-disk-demand75/object-prior-model`. It compares the event-weighted and distinct-object newcomer prior for retained and disk-opportunity variants on 10 known inputs, with four component arms (160 model arms). The old 80 arms were exactly reproduced; NoHotspot was unchanged by the prior numerator change. A source-equivalence replay checked 80 source arms and 4,654 exact admission records against the scanning model. This supports implementation/model equivalence, not real performance.

The actual 77 H headers have SHA256:

- `run_reuse.h`: `88f4449720a742784b2e0a28a8e073cfe624bb97db251769f41f2f29da879fa7`
- `measured_policy.h`: `259a97b8a2757818bba0068e19d2f1605d082fed33bdf837752b1db774fb81b3`

The distinct-object numerator gives each recurrent object one vote. It is bounded observed object support, not an unbiased or calibrated recurrence probability: objects have unequal observation ages and incomplete future-return exposure. A positive cohort term in an accepted max-combined decision does not prove that term caused acceptance.

For public74802, retained event-prior and object-prior Full both yield 967 remote reads and 33 copies. All 33 accepted admissions in each have cohort value zero. The model logs only accepted admissions; this alone is not a proof that every rejected candidate had zero computed prior. The unchanged model output gives no basis for attributing the real first-round Full/Legacy difference to the new prior formula.

`capacity-boundary/` reuses the frozen 77 H headers for four capacities (12/18/24/48 MiB), 10 known inputs and four arms: 160 new deterministic model arms. It explicitly includes old retained-model outputs as historical mechanism references. The score `remote_reads*21 ms + disk_hits*10.5 ms + copies*8 ms` assumes zero RAM service cost and instantaneous copies. It omits asynchronous overlap, control costs and contention. It is neither elapsed wall time nor throughput nor p99. The primary acceptance budget remains 24 MiB; choosing another capacity after seeing the result cannot repair a failed primary comparison.

Both favorable and unfavorable model cells are retained. At 24 MiB, moving74801 Full and NoH are exactly 84 remote reads / 28 copies and tie in the fixed storage score. At 18 MiB there is a modeled advantage on all four moving inputs, but this is a boundary hypothesis requiring separately declared future measurement, not a measured result.

Only `.cpp`, `.h`, `.py`, `.json`, `.txt` and `.md` files are included; compiled `replay` and `prior_test` files are excluded and no model source is executed during archive verification. `provenance/model-files.json` lists included/excluded paths and exact copied hashes. Historical generation scripts preserve their original absolute development paths and dependencies on report 75; they are provenance, not a portable one-command rerun promise. Existing model manifests may mention intentionally excluded log/binary files; the archive's own manifest covers the exact included subset.
