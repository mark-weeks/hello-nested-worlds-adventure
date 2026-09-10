# M4: familiar places remain actionable

**Date:** 2026-09-08. **Review update:** 2026-09-09. **Base:** fetched `origin/main` at
`d97ea1422d0a0c307d952ac1044e8607a5fad502` (M3, PR #96), with M1
`09317c35c5d07beafe2bbe93b9233fd2fba9a8bf` and M2
`de45e98d4e4a3579e7eeb88df8fa290f8a5636a3` verified as ancestors.
Worktree `m4-responsive`, branch `codex/m4-responsive-inhabitants`.
All databases and servers used here are disposable. No deployment, merge or
production observation. M3's repository merge at 22:12:28 UTC is now recorded
in its evaluation and the milestone plan; it is not deployment evidence.

## Policy and persistence boundary

[ADR-022](../decisions/ADR-022-m4-responsive-inhabitants.md) separates five things:

| Concern | Rule |
|---|---|
| Discovery | Keep accumulated canonical names. Familiar activity adds no fresh discovery. |
| Revisit | Screen up to 64 recent candidates for unconsumed, persona-relevant, accessible opportunities before assigning two slots; then a durable fair scan. Initial home affinity seeds that cursor only. |
| Persona action | One initial opportunity, then one per new external material event. Tenders use existing verbs; scholars retain their documentary verbs; destabilizers retain existing decay. All cast-origin effects, including sourced maturations, are excluded as new triggers. |
| Puzzle | One attempt per current renewal epoch, with the existing difficulty-weighted deterministic roll. Epoch zero keeps its previous roll; later epochs receive a new deterministic roll. Failure waits for renewal, not a timer or a property edit. |
| Activity/context | Real visits, withdrawal, puzzle attempts and accepted persona acts form recent context. Quiet or capacity-exhausted opportunities add no visit/context; cap retained context at 100 entries. Run records and completion notices count actual visits separately from fresh discovery. Causal arrivals never move the inhabitant. |

An initial opportunity does not require clearing legacy discovery memory. A
shared or no-op admission consumes that opportunity without inventing an origin
or participant credit. A dangerous place can produce one recorded withdrawal;
unchanged danger does not repeatedly amplify itself. Seals block entry, while
someone already inside can still leave. Quiet conditions may produce no action.

The persistence gap is a durable attempt fence and fair cursor. A bounded recent
log cannot provide either after eviction. Migration 0020 adds a nullable cursor,
a small `(world, inhabitant, place)` attention table holding only consumed change
ID and epoch, and one partial history index. Existing memory formats, history,
world nodes, and pending work are preserved. No dialogue, journal, promise,
situation, identity, inventory or geography system is introduced.

Markers commit with each acceptance under M1's SQLite lock. A failed transaction
refunds the opportunity because nothing was accepted; a post-commit failure does
not. Shared/no-op admission commits only the marker. Discovery/cursor/context are checkpointed
separately and can lag an abruptly killed new visit; the marker and chronicle remain
authoritative and prevent repeating it. Legacy memory gets one initial opportunity
per eligible place without erasing any known names. See the ADR and
[operating guidance](../infrastructure/delivery-recovery.md#m4-attention-alongside-accepted-work)
for compatibility and stopped-writer backup/restore boundaries.

## Reproducible before/after evidence

The [portable probe](2026-09-08-m4-responsive/heartbeat_probe.py) accepts an explicit
checkout path, uses real `run_tick` calls and real `/act` and `/puzzle/attempt`
requests, and removes its own databases. The partially explored fixture knows
270 names beneath one Galaxy; the full fixture knows all 4,208 born names.
A separate 12-tick fixture populates every recurring cast member's discovery
memory. These are constructed saturation cases, not measured production frequency
or a forecast of time until saturation.

| Observation | M3 baseline | M4 |
|---|---|---|
| Five ticks, four-visit request, partially/full known | 80 recursive node calls per tick, despite a nominal budget of four; zero persona acts. | At most 16 candidate inspections and four visits. The first tick acts on familiar ground; quiet ticks inspect without inventing activity. |
| Recent context in those fixtures | First tick erases the saved context. | Initial context retained; quiet ticks preserve the same six, then nine, entries. |
| Real Ada kindle matures at the familiar Galaxy | No response on the next tick. | The bounded recent-change lane revisits it and accepts an inhabitant kindle. That is pending work, not a claim of immediate density growth. |
| Fully known recurring cast, 12 ticks | 0 fresh discoveries, 0 persona acts, 0 chronicle rows. | 0 fresh discoveries, 6 persona acts, 16 chronicle rows before draining all staged work. |
| Human endpoint solve → decay → epoch 1 | Agent attempts `The Keeper Witness of the Room` from epoch zero. | Agent attempts the current `The Jumbled Room Word · Renewal 1`; difficulty stays 3. |

The [before JSON](2026-09-08-m4-responsive/before.json) and
[current after JSON](2026-09-08-m4-responsive/after-review.json) retain tick summaries, SQL read
counts, hydration counts, context sizes, player acceptance and renewal evidence.
The [initial M4 output](2026-09-08-m4-responsive/after.json) is retained as
pre-review evidence from `d85edc6`; it is superseded by `after-review.json`.
The five-tick fixtures use 6 SQL reads per baseline tick versus 24, 11, 11, 23
and 11 in M4 (SELECT and WITH included). The increase pays for current state
and accepted action checks; it does not multiply queries by all known nodes.
The endpoint/heartbeat regressions separately force repeated inspection of one
place to prove that quiet state, a failed puzzle and the cast's own delayed
landing do not repeatedly authorize effects. The priority regression leaves the
fair cursor over 1,000 nodes away, lands a real human contribution, and observes
a response on that inhabitant's next tick without resetting fair progress.

```bash
mkdir -p /tmp/enfolded-m4-baseline
git archive d97ea1422d0a0c307d952ac1044e8607a5fad502 | tar -x -C /tmp/enfolded-m4-baseline
.venv/bin/python docs/evaluation/2026-09-08-m4-responsive/heartbeat_probe.py /tmp/enfolded-m4-baseline
.venv/bin/python docs/evaluation/2026-09-08-m4-responsive/heartbeat_probe.py .
```

## Work bounds and their limits

Let `N` be the number of born nodes and `D` the maximum neighbor count (parent
plus children) in that stored tree. The heartbeat does one O(N) topology hydration
and builds one name index; it does not hydrate the world for each candidate or
retry. Discovery memory loading/union remains O(N). Birth is a separate one-time
initialization, not part of the repeat-tick measurement.

| Work per tick | Enforced limit | Maximum in the 22 recorded ticks |
|---|---|---|
| Recent candidates screened | Latest 64 material/renewal rows; eligibility checked before assigning 2 priority slots | 1 |
| Traversal candidate inspections | `min(40, 4 × requested visits)`; at most 104 checks including screening | 40 |
| Initial projected names | At most `(64 + 40) × 11 = 1,144`; batches of at most 550 | 50 |
| Actual visits | `min(10, requested visits)` | 4 |
| Puzzle attempts | 2 | 1 |
| All puzzle/persona admissions, including races/no-ops | 4 combined, including reserved deferred admissions | 3 |
| Origin effects | Visits + 4, at most 14 | 2 |
| Initial causal rows | At most `4 × D` | 6 |
| Persona returns to previously visited places | At most 2 | 2 |
| Conversations | At most 1 | 1 |
| History projection | 200,000 SQLite VM steps per projection | Below cutoff |
| Whole-tick SQL work | 2,000,000 sampled VM steps across connections | 71,000 |

SQLite progress is sampled in 1,000-instruction quanta; short statements and
partial quanta are not exact instruction counts. This is not a latency SLA:
SQLite lock waits retain their existing five-second timeout, hydration and JSON
work are Python work, and pacing adds at most ten requested visit delays. The
fixed action/candidate limits also bound statement counts. Candidate/ancestor
properties, epochs and markers are batch reads; only attempted actions refresh
their short chains under the writer lock. No per-inspected-node SQL loop or
repeated full-world hydration is added. A separate full-pool regression screens
64 recent candidates and inspects 40 traversal candidates: 109 initial projected
names, 30 SELECT/WITH reads, one hydration and 86,000 sampled SQL steps. This
measures the screening work separately rather than hiding it in the 40-node cap.

The causal pump retains its independent 64-candidate / 32-maturation batches and
M3's eight-commit/50ms notification flush rule. Each accepted causal source can
ultimately reach at most the finite born tree; this change does not clip an
accepted cascade or silently change a law. Initial sources are bounded per tick;
this is not a global historical storage quota. Cast attention rows are bounded
by inhabitants × born places; chronicle and completion retention remain unchanged.

Priority is a latency aid, not a complete work queue: more recent traffic can
push a change out of its 64-row window. Fair scanning still reaches it, per
inhabitant's scheduled ticks. Persistent SQL budget exhaustion requires read
optimization/operational investigation, not erasing memory or raising unbounded
budgets. An interrupted run never reports previously committed effects as zero.

## Acceptance through player-visible recovery

Persona verbs continue through `accept_verb`: M1 atomic acceptance, v2 operation
admission, pressure, first ring and optional maturation. Autonomous puzzle/decay
origins now commit through the same existing wiring and staged first-ring
boundary, with their attention marker in the transaction. Visits are local
existing `AGENT_VISIT` events. All external broadcasts follow commit.

M1's delivery transactions, completion fences, retry/recovery, source IDs and
continuations are unchanged. V1 absolute patches and v2 operations retain their
interpretation. Shared pending outcomes and explicit terminal no-ops remain M2
facts. Pump/history narration continues using M3's evidence-bound source
projection and notification batches. No taxonomy is added to Wayback; it still
folds recorded deltas. Agent solves never create human attempt/session credit,
open human seals, or complete human constellations.

New regressions cover repeated/quiet ticks, partial/full discovery, recent-change
priority and fair progress, own/cross-cast effects, saturation/shared no-ops,
current renewal and failed-attempt suppression, seals/withdrawal, 100-entry
context, concurrent ticks, bounded reads and SQL interruption. Three real SIGKILL
cases interrupt before the marker, after its write but before commit, and after
commit. Fresh processes recover accepted causal/maturation work; same-opportunity
reinspection adds no second origin. A v19 upgrade preserves old rows, and a
pending-work backup/restore preserves markers, cursor and completion fences.

Both `/` and `/app` browser cases create a real player action and run a real
heartbeat in a saturated world. They observe the inhabitant's attributed
acceptance and arriving ripples, preserve the player's response, and add no
`/world` or `/history` reads and at most one `/node` refresh for cast acceptance.
Then they miss notifications, kill/restart the server with pending work, verify
that another tick cannot duplicate the acceptance, drain both contributions,
and reload the attributed outcome and density 459. These are desktop consistency
checks; M5's mobile/accessibility slice and invite-default gates are unchanged.

## PR review follow-up, 2026-09-09

The [owner review](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/97#pullrequestreview-5162478122)
and [Copilot review](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/97#pullrequestreview-5162535663)
examined `d85edc6`. Twelve targeted cases failed on that head; four shared-seal
parity cases already passed. Eighteen new regression cases now cover those
findings plus combined capacity and full-pool read accounting.

| Finding | Reproduced behavior | Correction and evidence |
|---|---|---|
| Observer drop-in under danger | Real `/observe` finished with zero visits; CLI ambient left no trace. | Plain traversal stops ancestor checks at its supplied root. Both endpoint and CLI now leave real visits, while internal danger still blocks descent. The review's seed-42 25.5% prevalence is not claimed as remeasured; these regressions use disposable seed 382. |
| Consumed/ineligible priority candidates | Two newer dead candidates displaced an older real human maturation. | Batched current epochs, consumed markers, persona relevance and access filter candidates before the two-slot slice; the next tick reaches the human change without resetting fair progress. |
| Capacity exhausted after eligibility | A known five-puzzle page made five visits after only two attempts. | Check capacity before movement, and reserve deferred persona slots against the same four-admission budget. Two puzzle opportunities now produce two visits; later candidates leave context alone. |
| Unused home-affinity draws | Three ticks sampled three drop-ins despite a saved cursor. | One initial home drop-in, then three distinct cursor positions. Roster and ADR claims now describe initial placement. No additional affinity lane or mutable identity was added. |
| Seal covenant duplicated | Existing inside/outside and human-solve behavior agreed. | Reuse `gates.sealing_room` and `gates._path_suffix`; parity cases retain renewal and the already-inside exemption. Batched solve evidence stays local. |
| Malformed action text | `kindleed`, `inscribeed`, `observeed` were returned/persisted. | One correctly formed past tense feeds both new context and summary; old records remain untouched. |
| Familiar visits reported as zero | A real visit had `fresh=0`, and run records/completion notices also said zero. | Persist and broadcast actual visits; both real clients display that count. The zero-discovery field remains separate. |

The wider focused pass initially exposed one old assertion expecting
`inscribeed`; that expectation was corrected. The two real-client cases pass
with displayed counts, player response ownership, live attribution, missed
notifications and process restart still covered. No migration or causal-law
change was added by this follow-up; all M1/M2/M3 recovery tests remain in the
canonical gate.

## Verification and irreversibility

The suite adds 46 Python cases (28 initial plus 18 review regressions) and two browser cases. Initial checks exposed two
old fixtures: a broadcast test selected a newly respected unsafe drop-in, and
a social test supplied a seed-42 identity to seed 43. Their replacements use
safe ground and independent same-world social trials. A new renewal test also
needed `depth=11` to address its real Room through HTTP. No production data was
used to correct these fixtures.

The first remote browser run exposed a test-only dependency: importing a
Python test helper required `pytest`, which the browser job's runtime-only
installation intentionally lacks. The browser fixture now defines its tiny
deterministic RNG and tree walk locally. Both new browser cases also pass in
a clean locked-runtime environment with `pytest` confirmed absent (4.5s).

The canonical check passed: **1,080 Python tests** in 135.75s, **110 Vitest
tests**, **35 Playwright tests** (2.2m), Ruff, a byte-fresh committed production
bundle and installed-wheel smoke. Python 3.11.15 / Node 20.19.0 were installed
through `setup.sh`. Both browser screenshots were inspected.

Canonical verification results are recorded in
[verification.json](2026-09-08-m4-responsive/verification.json). All existing
M1/M2/M3 reconstruction, recovery, co-op, canonical-world and continuity suites
remain in `ENFOLDED_E2E=1 ./scripts/check.sh`.

**Irreversibility check:** additive migration 0020 stores only attention markers,
a scan cursor and a partial read index; attention shares existing acceptance
transactions. Existing chronicle producers are bounded/staged, with no new event
kind, historical rewrite, golden re-pin, born-node, hinge, era or causal-law edit.
