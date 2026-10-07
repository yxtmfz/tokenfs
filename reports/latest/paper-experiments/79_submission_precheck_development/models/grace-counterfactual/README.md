# Existing grace switch: single negative counterfactual

Local model only; no repository source changes or server run. The sole changed option is `persistent_reuse_immediate_decay=false`. All original object-weighted H options remain enabled, disk capacity stays24MiB, RAM stays4MiB LRU, and all ten existing1152-request inputs are retained. Full, NoHotspot, NoAffinity and NoJoint receive the same switch. The original static NoHotspot formula is unchanged.

**Do not promote the existing grace switch based on this batch.** Full gains on one input, loses on two, and ties on seven relative to immediate decay. Four moving inputs all tie the original Full, including84remote/28copies on moving74801. Public73601 and uniform become worse. This is not a remedy for the missing H advantage on the current moving input.

## Why test this option, and what it can establish

Frozen78 public analysis identified a small positive preliminary margin that could become negative after one logical observation of immediate decay. Existing `RunReuse::Estimate` supports an observed-gap-plus-standard-deviation grace: overdue=`max(0, age - gap - stddev)`. For the early recurring public key's observed gap14 and one return interval, this holds its dimensionless forecast at128/14×1/2=4.57142857 for the first14observations, instead of immediately multiplying by2^(-age/14). It is causal because its interval and variance come only from preceding returns; the standard deviation allowance is a heuristic, not a confidence bound.

This local replay serializes requests and completes copies immediately, with fixed21ms remote/10.5ms disk/8ms copy samples. It therefore tests cache decisions under the original service-cost proxy, but **cannot measure online cost sampling, preliminary-to-commit scheduling, actual speed or p99, or prove the real public branch becomes stable**. Holding the near-term incoming forecast can also hold obsolete resident values longer. That downside must be retained rather than assuming grace is universally beneficial.

## Historical overlap check

Report36 already compared older GraceFull and immediate-decay Full. Its moving3293 result favored immediate decay (56remote reads versus74with grace). That experiment predates object-weighted cohort support and the current option set, uses different traces and576requests rather than1152, so it does not duplicate this exact counterfactual. The local75/77/78 model search did not find an exact object-weighted/current-options counterpart. See `history-audit.json`; the older negative evidence is not overwritten.

## Full results

Each count cell is remote/disk/RAM/copies. Positive savings favor Full. Fixed score is21×remote+10.5×disk+8×copies milliseconds; it is not a measured runtime.

|Input|Immediate Full|Grace Full|NoH, unchanged|Grace saving vs immediate, ms|Grace saving vs NoH, ms|
|---|---:|---:|---:|---:|---:|
|moving73501|79/160/913/29|79/160/913/29|79/160/913/28|0|-8|
|moving73502|83/162/907/28|83/162/907/28|85/160/907/28|0|21|
|moving73503|78/158/916/28|78/158/916/28|79/157/916/28|0|10.5|
|moving74801|84/148/920/28|84/148/920/28|84/148/920/28|0|0|
|public73601|865/286/1/34|875/276/1/34|873/278/1/25|-105|-93|
|public73602|879/271/2/43|879/271/2/43|870/280/2/28|0|-214.5|
|public73603|920/230/2/34|913/237/2/28|938/212/2/21|121.5|206.5|
|public74802|967/183/2/33|967/183/2/33|1002/148/2/25|0|303.5|
|stationary73701|65/184/903/12|65/184/903/12|65/184/903/12|0|0|
|uniform73702|544/509/99/45|555/498/99/38|546/507/99/41|-59.5|-70.5|

`results.json` contains all80arms (40original replay checks plus40counterfactual arms), including NoAffinity and NoJoint with their positive and negative changes. `tables.md` retains both modes side by side. No further interval, ratio, horizon, input or capacity sweep was performed.

## Verification and provenance

- All40 original arms exactly reproduce the previous frozen78-header LRU replay, including reason counters.
- NoHotspot's aggregate counts and full request/RAM-eviction/disk-copy logs are exactly unchanged for all10inputs.
- All80arms account for1152requests; runtime guards protect the current RAM capture and the2slot bound.
-60prefix cases/240verification arms at cutoffs127/401/806 reproduce all full-run prefix decisions. Inputs, results and logs are retained. This checks implementation causality, not statistical independence.
- Header hashes are in `history-audit.json`. The headers were copied from the prior frozen78 model; current79 source is not substituted.
- The diagnostic was completed while parent collected candidate79 output, without viewing its performance outcomes. It does not alter candidate78/79 raw results.
