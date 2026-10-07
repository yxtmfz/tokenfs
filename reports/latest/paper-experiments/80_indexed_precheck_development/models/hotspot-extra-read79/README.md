# Moving74801 extra remote reads: causal-gap diagnosis, not a new policy

**84 versus77 is a net difference of7, not seven uniquely identifiable avoidable requests.** Native-header serial replays produce16requests that are remote only for Full/NoHotspot, and9different requests remote only for shared SIEVE. Full and NoHotspot have exactly the same modeled source sequence. No new strategy, parameter sweep, production edit or server experiment was performed.

## Evidence boundary

Frozen79 raw totals are84remote/148disk/920RAM/28copies for Full and NoHotspot, and77remote/155disk/920RAM/77copies for SIEVE. There are67distinct objects, hence17versus10non-first remote reads. The unchanged original H/native SievePolicy replays reproduce these totals. They also reproduce both real rounds' complete READY-key sequence for every arm; Full and SIEVE additionally match every READY destination. NoHotspot differs only in the final key22destination (model domain2 versus actual domain0).

This close reproduction supports a mechanism explanation but **does not establish real per-request source identities**:79requests contain no backend-tier field, and asynchronous policy events lack request ordinals and timestamps. The16/9sets and RAM-eviction times below are explicitly model inferences, not labels guessed from elapsed-time thresholds. Copies complete instantly in the replay and costs are fixed21ms remote/10.5ms disk/8ms copy. Online rates, pins, queue delays and copy/read overlap are absent.

## Where the difference occurs

The16Full-only remote reads are objects8–23, once each. Fourteen are a second distinct logical run; key10and17are a third run. SIEVE copies these on their earlier read and still retains them at return. Full's ordinary copy threshold often waits for another distinct return; the second read pays remote cost and then creates the useful disk copy. See extra-table.md for all16exact input ordinals, preceding run starts/last accesses, RAM-eviction ordinals and return gaps. Observation ordinals are1based; request indices are0based.

SIEVE's9countervailing misses occur at observations257(key2),269(1),345(6),661(15),761(11),1029(21),1049(20),1089(19),1137(17). Full retains these objects while SIEVE's eager admissions evict them. Its lower remote total costs49extra copies (77versus28). Under the existing fixed proxy, Full costs3542ms and SIEVE3860.5ms: Full saves318.5ms despite7extra remote reads. These scores are not wall-time claims; they show why remote-read count alone is the wrong optimization objective.

## Could the original policy act earlier using only prior information?

Nonmutating Plan probes were added at **every** observed current-key request and each modeled RAM eviction, not just at retrospectively successful objects. They inspect original policy state and resident layout but never execute new decisions. Instrumented original action logs remain exactly equal to the earlier replay.

For13of the16objects, the original Full and NoHotspot both reject copying at the end of the preceding run and at RAM eviction under the fixed measured-cost proxy. Their then-known value is below copying cost; a single4request run is mostly RAM reuse, not evidence that the object will return after eviction. Offline knowledge that this object later returns cannot justify granting it special treatment.

For3objects, both original Full and original NoHotspot already report a feasible positive plan during a prior RAM-served request: key12at observation389, key21at805, key17at853. The first two are within8request runs; the last is a separate return still covered by the retained RAM slot. Current remote-only disk-planning triggers skip these points. Thus there is a **common trigger opportunity**, not a demonstrated H-specific estimation advantage. At subsequent RAM eviction Full's key12/21values have already decayed below copy cost; key17remains profitable. NoHotspot permits all three at that eviction instant.

An earlier copy could consume a pinned buffer, compete with a foreground read or evict a later-useful object. Therefore these3positive probes do not authorize subtracting3remote reads from the final total while holding all other actions fixed. Related common RAM-replan models have already been explored; this diagnosis does not reopen an arbitrary coefficient search or claim an untested net benefit.

## Reproduction and checks

- analyze.py checks all two-round raw aggregates/input ordinals/READY-key sequences and retains file hashes; raw evidence remains unchanged.
- probe_replay.cpp uses copied original native policy headers, records full per-domain reasons/value/loss/copy/noise at past-only observation points, and leaves original actions unchanged. past-only-probes.tsv retains every probe, including negative ones.
- sieve_replay.cpp uses frozen79 SievePolicy with12disk slots and the same2RAM slots. Resident visits include RAM hits as in the current implementation. It changes no production algorithm.
- Three prefix inputs127/401/806cover9arms. All source, eviction, copy and probe records match full-run prefixes exactly. This checks causality, not independence or runtime accuracy.
- No actual throughput or p99 was recomputed or replaced, and no formula candidate was implemented.
