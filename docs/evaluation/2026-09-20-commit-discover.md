# Commit, then discover: implementation evidence

**2026-09-20.** Owner-directed Batch 1, based on refreshed `main` at `4e78d97`
(merged PR #105). This records tested behavior, not production deployment or
live-model quality. The subsequent UX batch has not started.

## Acceptance and observed results

Both browser clients extend their existing Act component. Four labeled suggestions
commit directly. Optional combinations collect up to four ordered attempted actions;
intention submission authorizes the attempted action. The public preview route is
closed, the choices response contains no simulated changes/signals/routes, and
pending destination names are absent from recaps. Ordinary action descriptions and
present properties remain readable.

Version 3 stores normalized attempts without a patch, signal or route forecast.
Acceptance records `phase=accepted`; settlement adds a distinct `phase=observed`
row, including material, partial and no-material results. Each step resolves against
current properties. Only materialized steps contribute to the outgoing disturbance;
no net change sends none. Each receiver passes on its actual remainder after meeting
current conditions. Effect, observation, continuation and completion share one SQLite
transaction. Earlier versions retain their interpreters and accepted receipt payloads.

## Executed evidence

- **Real endpoints:** direct actions need no `expected` token; a menu read before
  another player acts does not create a stale forecast conflict. Repeated Engrave
  is accepted and records an observed no-op. Invalid scope, foreign-scale actions,
  caller-selected performers and invalid model steps cannot mutate the world.
- **Independent actions during delay:** Bea commits Spiral; Ada subsequently commits
  Spiral + Scatter before either matures. Bea's action changes the shape during
  Ada's wait. At Ada's settlement, Spiral is moot and Scatter changes density
  **400 → 360**. The outgoing impulse is **−2**, from the step that materialized,
  rather than the **−1** a precomputed two-step signal would carry. A repeated
  delayed Spiral becomes a terminal no-op with no false downstream work.
- **Both actual clients:** those independent actions survive a real server restart;
  both map and scene show pending acceptance followed by the partial observation.
  Separate cases drop the HTTP acknowledgement after the server commits, reload
  the browser, and retry the retained ID. One receipt and one attempt survive.
- **Model fixture:** production interpretation/schema validation and real endpoints
  handle four ambiguity classes (action/target/scope/order), unsupported constraints,
  invalid operations and quiet failure. Both browsers retain the editable intention
  after clarification/refusal. A clear modeled attempt commits on submission.
  Retrying its lost receipt bypasses the provider, including after leaving the place.
- **Concurrent replies:** while one provider result waits, a concurrent retry's quiet
  reply wins the serialized receipt. The later model result returns that same reply
  and cannot commit an action after the client was told none was accepted.
- **Recovery:** injected failure rolls back acceptance, material delta and receipt
  together. Concurrent duplicate requests make one attempt. A child process is
  killed after a v3 settlement write but before completion; backup/restore retains
  the pending input and subsequently applies it once. Existing v1 and v2 acceptance,
  actor attribution, pending work, rollback and process-death cases remain covered.
  The client also recovers old preview-shaped local storage records.
- **Missed notices:** polling refreshes observations even when one pending hop replaces
  another and the pending count stays one. Existing late-reply/navigation and
  co-viewer tests continue to check that personal feedback stays with its actor/place.
- **Receiver edge correction:** a saturated echo can remain unchanged while danger
  changes. A regression verifies that such a receiver still passes its observed
  **0.65** remainder; a live woven resonator reduces that remainder. Removing an
  unchanged property from the stored delta must not erase the physical signal.

The browser fixtures accelerate clocks on disposable databases. These results do
not establish production timings, workload capacity or natural-play frequencies.

## Inspection and preserved local world

In-app browser inspection exercised one-click Engrave in the scene client, then
opened the map client on the same served state and inspected observed history.
Four suggestions, intention disclosure and optional combinations occupy the same
Act surface. Manual 390px scene inspection also submitted `polish, engrave` by
keyboard and observed the ordered results with no net material change. Browser cases capture 390px layouts and verify no horizontal overflow;
existing keyboard recovery and arrival-save failures remain exercised.

Inspection used a separate SQLite backup copy of the existing local playtest world.
A read-only before/after logical SHA-256 comparison of **all 39 original tables**
matched: **4,208 born nodes and 1,697 history rows** remained unchanged. No original
server restart, world reset, migration or production operation was performed.

## Verification result

The canonical gate passed **1,332 Python, 122 Vitest and 68 Playwright** cases.
After the final receiver correction, **86 affected Python** and the full
**1,333 Python** passed; all **9 Act Vitest** cases passed. Ruff, document references
and diff whitespace are clean. The canonical
`ENFOLDED_E2E=1 ./scripts/check.sh` covers Ruff, Python, Vitest, build/bundle freshness,
installed-wheel smoke and Chromium. The final receiver correction also runs the
full Python suite again; the wheel smoke explicitly requires the v3 interpreter.

## Remaining limitations and UX handoff

- **No live-model validation:** all interpretation evidence uses deterministic
  provider fixtures. Prompt/schema boundaries do not prove semantic accuracy on
  arbitrary player prose. Explicit action notation works without a model.
- The vocabulary remains 44 scale-native operations; no arbitrary creation, remote
  targets, negotiated joint actions or expanded autonomous-agent/CLI vocabulary.
- New v3 combinations are ordered attempts: moot steps do not cancel remaining
  steps. Recaps expose at most eight records with pending work first. They describe
  observed history, not guaranteed destinations or times.
- No scoring, broad restyling, navigation redesign or media work. The scene/map's
  pre-existing typography, visual hierarchy and host event-feed presentation remain
  topics for the separately authorized UX batch. Preserve the direct commitment,
  clarification, recovery and history contract while doing that work.

## Irreversibility check

`persistence/interventions.py` adds v3 acceptance/observation writes through the
existing append-only event writer and schedules continuations transactionally.
The owner explicitly requested this acceptance/consequence correction and distinct
history phases; ADR-028 records that scope. No migration, golden re-pin, generator
or born-identity change, history rewrite, world-meta/hinge pin or era-bank change.
No caller controls another player. Both clients retain one Act surface. No merge,
deployment or Batch 2 work is included.


## Final review follow-up

The partial-effect review reproduced Cultivate reporting less danger at the minimum
and Relax reporting a redward shift at the maximum wavelength. Declarative outcome
clauses now follow the actual changed fields. Five retained compound verbs receive
the same v3-only correction, keeping the node's aspect clause; v1/v2 semantics and
stored historical notes remain unchanged. Engrave no longer guarantees the mark's
future permanence.

The six remaining threads are addressed: predicted availability fields and their
client branch are removed, legacy `accept()` rejects v3 before writing, recap rows
are decoded once, receipt lookup shares one mismatch check, and blank intention
submission performs no position/receipt/commit request. The existing operational
`interventions.signal` field stores the latest observed v3 signal atomically with
completion; its single next hop no longer relies on chronicle content. Pre-upgrade
v3 rows recover from the preceding historical observation when necessary. If that
old input is already missing, recovery is still required; it is never recomputed.

Recovery fault tests use disposable databases only: they remove observation data
from the fixture after settlement and confirm that continuation and receipt replay
survive reinitialization. Another variant starts with the old empty operational
signal and verifies its transition to the independent delivery path. This makes no
claim that erased history can be restored, and authorizes no history pruning.

`ENFOLDED_E2E=1 ./scripts/check.sh` passed Ruff, **1,358 Python** (246.05 s), **123 Vitest** (13 files), byte-fresh production bundle, installed-wheel smoke and **70 Playwright** (2.6 min). The added coverage includes **16** partial-effect narration cases, endpoint/history/retry checks, operational-signal and pre-upgrade recovery, nullable receipt replay, and blank intentions plus truthful history in both real clients. Both corrected rendered views were inspected; documentation references and diff whitespace passed.
No live model was invoked. The original playtest database was not opened by these
follow-up tests; all endpoint and browser verification used disposable worlds.
