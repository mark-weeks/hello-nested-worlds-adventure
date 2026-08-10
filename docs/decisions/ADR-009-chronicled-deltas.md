# ADR-009: Chronicled Deltas — event-sourced node substance

**Status:** Proposed 2026-08-10 — drafted from the recursion-and-time design
thread (`docs/evaluation/2026-08-10-recursion-and-time.md`), owner-directed.
Owner ratification lands at the merge gate of the implementing PR. This is
the **first batch of the pre-launch sequence**: it must land before any
production history exists.

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
   state (`nodeart.js`, `nodesound.js`), past *appearances* need no
   storage: reconstruct state-at-T and derive how the node looked and
   sounded then. Evolution animation is that derivation scrubbed across
   a timeline — reproducible identically for every player.
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

- The effects handler records the changed-properties dict, together with
  the triggering event's kind and **strength**, in the chronicle.
- Event rows carry strength generally, so ripple-at-T is also derivable
  from the record.
- Every other `upsert_node_properties` call site — the scale-verb
  producer path, constellation lighting, entanglement resolution, and any
  future site — chronicles its delta the same way. The rule is total:
  *no substance change without a chronicled delta.*
- **State-at-T is defined as:** the born row (`world_nodes`, immutable)
  plus a fold of chronicled deltas with `recorded_at <= T`. Effect logic
  is never replayed to answer a historical question.
- An invariant behavior test pins the two paths together: folding all
  chronicled deltas must reproduce the current overlay exactly. A write
  path that changes substance without a delta row is a bug this test
  catches.
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
- **A standing discipline.** Every future substance-writing path must
  chronicle its delta or the archive silently forks from reality. The
  fold-equals-overlay invariant test is the enforcement, not reviewer
  vigilance.

## Revisit when…

- **The evolution grammar ships** → its event kinds join this stream;
  that is the intended payoff, not a change to this decision.
- **Chronicle volume threatens storage** → prefer widening storage.
  Pruning remains double-gated and continuity-violating; deltas do not
  change that calculus.
- **A substance write without a delta row is discovered** → treat as a
  P0-class defect against the archive; fix the path and backfill only if
  the delta is derivable from surviving records.

## Rejected alternatives

- **Read-time replay of effects code.** History rewritten by code edits —
  the era-names trap, at world scale.
- **Periodic overlay snapshots.** Stores state without causes: loses
  attribution, blurs ordering between snapshots, and still cannot answer
  *why* a node changed.
- **Defer until the wayback surface ships.** The record cannot be
  completed retroactively; deferral converts a cheap pre-launch write
  into a permanent gap.
