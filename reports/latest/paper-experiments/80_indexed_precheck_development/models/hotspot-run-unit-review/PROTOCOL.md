# Logical-run unit normalization: fixed model diagnostic

Protocol recorded before results. No production source or server changes. Use frozen78 original native policy headers (object-weighted cohort), the same ten development inputs,24MiB disk/4MiB RAM LRU, original fixed21ms remote/10.5ms disk/8ms copy costs. Compare original and exactly one candidate, four arms each (Full/NoHotspot/NoAffinity/NoJoint),80arms total. No parameter sweep or input/capacity change.

## Single conceptual change

Normalize both H's recent and persistent demand to distinct logical runs rather than multiplying logical request counts by a global reciprocal completed-run length.

- Recent: in the existing logical request window, count groups of this key's positions separated by a gap greater than1. Every observed group counts at most once, including the current incomplete group; never read its eventual length. A group partially cut by the left edge still counts as one observed group. Use max(0,groups-1) with frequency_admission=false (groups otherwise), then the **unchanged** Survival.
- Persistent: use original RunReuse::Estimate, but omit this key's learned completed-run-length multiplier. Preserve confidence, interval clamp, last_seen clock, original immediate-decay setting and competition discount. Do **not** enable74's separate DiskOpportunity/grace or disable cohort.
- Value: max(recent_run_value, persistent_run_value * existing competition, existing object-weighted cohort value), multiplied by original SavingRate*bytes*coverage. Existing recent-value-floor semantics remain; original burst-residual is zero under retained RAM.
- Keep NoHotspot's static Value byte-for-byte unchanged. Keep noise margin, cost sampling, headroom exploration, planning triggers, placement, joint loss, RAM policy and resource budgets unchanged.

The branch is restricted to retained+causal+shared+persistent+burst H. Arriving and resident objects use the same function.

## Prior work and limits

Report68 and75's disk histories count actual non-RAM demand, not logical run groups. Their negative results remain. Report74 normalized persistent demand but retained globally scaled recent demand, and also changed aging/cohort. The exact current object-weighted/immediate-decay combination above was not found in prior model sources.

Moving runs are mostly4requests but merge into8/12/16runs; see offline input-run-characterization.json, not consulted by policy. Even equal4-length runs do not make subtract-one-request then divideby4 identical to subtract-one-run: an already completed resident run retains an extra0.75 recent units. This is a possible counting mismatch, not proof it caused measured slowdown. Public inputs have all run lengths1, so model actions should be exactly preserved.

Run original replay reproduction, same NoHotspot statistics/actions, accounting/resource guards and all ten inputs' prefixchecks at127/401/806. Keep complete outcomes, including negatives. This serial/instant-copy model does not measure actual speed,p99 or asynchronous online-cost/scheduling effects and cannot itself authorize server adoption.
