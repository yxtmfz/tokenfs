# Capacity-aware optimistic rejection: frozen development screen

Direction A (residence-limited residual demand) is screened locally on the eight
already-used report66 inputs. Its counters do not justify server timing.
Direction B retains the hotspot estimator and corrects an ineffective planner
precheck: an empty-cache check always explores under bounded warmup, even when
the actual destination has no room. Use measured actual usage, ignore victim
loss optimistically, and preserve incoming uncertainty, costs and free headroom.
Reject only if this optimistic plan cannot pay for copying. Build the resident
snapshot only for surviving destinations. Actual migrations retain the existing
live capacity/pin/value check. This shared execution repair is not a new H claim.

Before timing, native tests include8000 randomized bound checks across dynamic
and static valuation, joint on/off, headroom/full cache and costs/admission on/off.
A real accepted plan must imply optimistic acceptance at identical policy state.
Warmup with real headroom must still be allowed. Existing native/Python tests run.

Twelve timed cases: moving_shared73501 and public_toolagent73602, each1152 two-MiB
requests; Full, NoHotspot, NoAffinity, NoJoint, PoolSIEVE1 and exact retained
OldFull binary. Same fixed randomized order as report67 first rounds, capacity
24MiB plus shared capture4MiB, serialized logical domains on cn7 and cn13 TCP.
No changes to valuation, quotas, durability, request inclusion or SIEVE behavior.
These already-inspected inputs are development, one observation per pair; neither
repeatability nor independent confirmation is established. Do not expand or rerun
based on favorable timing. Save every outcome, four comparisons, old/new controls,
actual wall throughput and request response p99. Check pruning/snapshot counters.

Run480 separate content hashes and an independent raw-request/SQLite/source audit.
Select a direction only if mechanism and measured evidence support it. Preserve
negative results and do not equate engineering gains with H's marginal contribution.
