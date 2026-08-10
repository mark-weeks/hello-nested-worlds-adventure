# ADR-009: Chronicled Deltas — event-sourced node substance

**Status:** Proposed 2026-08-10 — drafted from the recursion-and-time design
thread (`docs/evaluation/2026-08-10-recursion-and-time.md`), owner-directed.
Owner ratification lands at the merge gate of the implementing PR. This is
the **first batch of the pre-launch sequence**: it must land before any
production history exists.
Revised 2026-08-10 after the owner's PR #76 review: the decision now
specifies one atomic, totally ordered persistence contract, a versioned
fold cursor, the corrected writer inventory, and honest wayback
rendering semantics.

---

## Context

The chronicle records *events*, not *changes*. `make_record_handler`
(`causality/wiring.py`) stores only `event.payload` in the mutation row;
`strength` is a separate field on `CausalEvent` and is never recorded. The
effects handler computes each material property delta and persists it into
the overlay — but never chronicles it. And the overlay
(`persistence.upsert_node_properties`, table `node_runtime_state`) is a
`json_patch` merge holding only *current* state, with no history.

Consequence: **node-state-at-time-T is not reconstructible.** Not from the
overlay (no history), and not by replaying `apply_event_effects` over the
log — the threshold test needs the strength the rows don't carry, and
replay would tie reconstructed history to the *current* effects code, so a
future edit to `effects.py` would silently rewrite every node's remembered
past. The repo already learned this lesson with era names: anything
historical must be **stored at write time, never recomputed at read time**.

Two wanted capabilities depend on reconstruction:

1. **The wayback surface** — observing a node's past states and how it
   evolved. Because art and sound are deterministic functions of node
   state (`nodeart.js`, `nodesound.js`), the archive stores no
   appearances: reconstruct state-at-T and render it through the
   *current* senses — the node as it was, seen with today's eyes. The
   mappings are deliberately tunable, so this is reinterpretation, not
   playback (see Decision). Evolution animation is that derivation
   scrubbed across a timeline — reproducible identically for every
   player at any given deploy.
2. **The future evolution grammar** (ADR-006's gated write path) — any
   deliberate change to a born node should be an event in a legible
   change stream. Event-sourcing the substance now means evolution later
   is a new event kind in the same stream, automatically visible in the
   archive.

Timing is the point: nothing is deployed and the chronicle is empty. An
archive is only as complete as its earliest recording — this is the only
moment a complete record from t=0 is possible. Landing this after launch
leaves a permanent dark age at the beginning of the world's time.

## Decision

**Every write that materially changes a node's substance also chronicles
its delta at write time.**

- **One atomic write API.** A single transaction appends the chronicle
  row (the changed-properties merge patch, the triggering event's kind,
  and its **strength**), applies the same patch to the overlay, and
  allocates a **per-node monotonic version** in mutation order.
  Chronicling and applying are never separate transactions: a crash
  leaves neither half, and concurrent writers on one node serialize into
  distinct versions. `upsert_node_properties` becomes internal to this
  API — no substance writer may call it directly, so future compliance
  is structural, not a prose checklist.
- **The exact current writers, all routed through the API** (inventory
  verified 2026-08-10): the causal effects handler
  (`causality/wiring.py:70` — today the full gap: neither delta nor
  strength reaches the chronicle); the scale-verb immediate branch on
  its three surfaces (`server/handlers.py:1215`,
  `interface/__init__.py:213`, `server/heartbeat.py:194` — these already
  chronicle `changed` in their `SCALE_ACT` rows, but in a separate
  transaction with no ordering version); the maturation drain
  (`server/heartbeat.py:409`, `SCALE_ACT_MATURED` — same
  separate-transaction shape); and constellation lighting
  (`server/world_mechanics.py:60` — records `CONSTELLATION_COMPLETE`
  without its `{"constellated": true}` delta). Entanglement resolution
  writes no properties and needs nothing. The rule is total: *no
  substance change without a chronicled delta.*
- Event rows carry strength generally — including producer-attributed
  origin rows (the `record=False` paths), which are their event's only
  chronicle trace — so ripple-at-T is also derivable from the record.
  The version and strength ride the mutation row (additive migration if
  columns).
- **The persisted `ripple_score` is a derived cache, never
  authoritative.** Its live increment (the ripple handler in
  `causality/wiring.py`) is monotonic, non-negative, capped at 1.0, and
  has no decay path — a pure fold of chronicled strengths — so it stays
  *outside* the atomic transaction by design, including for events that
  carry no property patch. The implementing batch ships a rebuild
  function and a ripple-equals-fold invariant test beside
  fold-equals-overlay: cache drift is repairable by rebuild; only the
  chronicle is the record. (`upsert_ripple_score` is legacy/test-only
  and gains no new callers.)
- **Delta semantics are the overlay's own:** RFC 7396-style JSON merge
  patches — the same merge `json_patch` already applies, where a `null`
  value deletes a key — folded by sequential merge.
- **State-at-T is defined as:** the born row (`world_nodes`, immutable)
  plus a fold of chronicled deltas in **per-node version order**, up to
  the cursor `(recorded_at, node_version)` that T resolves to — the
  greatest version recorded at or before T. `recorded_at` alone is
  second-precision and cannot order non-commutative patches sharing a
  timestamp; the version defines the reproducible fold order and the
  exact scrub boundary. Effect logic is never replayed to answer a
  historical question.
- **Three test families enforce the contract:** injected-failure (a
  crash mid-write leaves neither the chronicle row nor the overlay
  change), concurrent-writer (two writers on one node serialize into
  distinct versions and the fold reproduces the final overlay), and the
  continuous fold-equals-overlay invariant. The invariant test is the
  net, not the guarantee — it detects divergence; only the atomic API
  prevents it.
- **Wayback shows past state through present senses.** State is
  historical; rendering is presentational. The archive stores what a
  node *was*; how that state looks and sounds is derived at view time by
  the current deterministic art/sound code — which is deliberately
  tunable, so a renderer edit changes the past's appearance exactly as
  it changes the present's. The surface must say so honestly ("the node
  as it was, seen with today's eyes"); it remains identical for every
  player at any given deploy. Versioning the renderers is rejected for
  now (below).
- The wayback surface itself is read-only and ships in a later batch;
  this ADR is the recording discipline it (and evolution) stand on.
- Redaction compatibility: deltas are mechanical fields and survive
  content-level redaction, consistent with the existing redaction
  covenant (mechanical fields survive so counters and epochs stay
  intact).

## Trade-offs accepted

- **A touched chronicle write surface.** Widening what mutation rows
  carry is a conscious, merge-gated change — accepted once, here, while
  the chronicle is empty.
- **Rows grow modestly, forever.** The append-only covenant already
  committed to unbounded history; deltas widen rows, they do not add a
  new growth dimension.
- **A wider refactor than "also chronicle."** Six call sites across five
  surfaces (HTTP, CLI, heartbeat agents, the maturation drain,
  constellation mechanics) route through one API in the implementing
  batch — accepted, because a prose rule over scattered writers is
  exactly what the review showed cannot hold.
- **A standing discipline, enforced structurally.** Every future
  substance-writing path must chronicle its delta or the archive
  silently forks from reality. The atomic API is the enforcement — there
  is no other door to the overlay; the fold-equals-overlay invariant is
  the net beneath it, not the guarantee.

## Revisit when…

- **The evolution grammar ships** → its event kinds join this stream;
  that is the intended payoff, not a change to this decision.
- **Chronicle volume threatens storage** → prefer widening storage.
  Pruning remains double-gated and continuity-violating; deltas do not
  change that calculus.
- **A substance write without a delta row is discovered** → treat as a
  P0-class defect against the archive; fix the path and backfill only if
  the delta is derivable from surviving records.
- **Faithful period rendering becomes a product goal** (wayback must
  show how a node *actually* rendered then, not today's
  reinterpretation) → version the renderers or store rendered parameters
  at write time; until then the surface's honesty line carries it.

## Rejected alternatives

- **Read-time replay of effects code.** History rewritten by code edits —
  the era-names trap, at world scale.
- **Periodic overlay snapshots.** Stores state without causes: loses
  attribution, blurs ordering between snapshots, and still cannot answer
  *why* a node changed.
- **Defer until the wayback surface ships.** The record cannot be
  completed retroactively; deferral converts a cheap pre-launch write
  into a permanent gap.
- **Chronicle-then-apply as separate transactions** (the pre-review
  draft's implicit shape). A crash between the halves leaves a
  half-event; concurrent writers can chronicle A→B while the overlay's
  last commit is A. The owner's PR #76 review blocked this: a
  fold-equals-overlay test detects that divergence but cannot prevent
  it.
- **Versioning the art/sound renderers now.** Real, permanent cost —
  every renderer edit becomes an archival event — bought for a surface
  that can be honest instead; revisit if faithful period rendering
  becomes a goal.
