# The Pre-Launch Window

Nothing is deployed: the hosted server does not exist yet, the chronicle
is empty, and the heartbeat has never run in production. That makes this
a bounded window in which certain decisions are cheap that will be
impossible or expensive forever after. **The window closes the moment the
first production history exists.**

This document records what was proposed and affirmed in the window,
sequences the development batches before launch, and lists what was
deliberately declined so future sessions don't relitigate it. Like
`phase-2-scale.md`, it is a living document — edit in place; when a batch
ships, fold its description into the CHANGELOG entry and mark it here.
When the window closes, this document is history and
`phase-2-scale.md` governs.

Decisions and analysis originate in the 2026-08-10 design thread —
synthesis in `docs/evaluation/2026-08-10-recursion-and-time.md`.

---

## Decisions proposed in the window (2026-08-10)

Direction affirmed in the owner's PR #76 review; each ADR's **formal
ratification lands at its implementing PR's merge gate**. Until that
gate these are commitments of plan, not walked-through doors — a future
session may reopen one, but must do so against the ADR's argument and
the review record, not from a cold start.

| Decision | Where recorded |
|---|---|
| The hierarchy closes into a traversal-layer loop: every particle descends to the Multiverse root; the root ascends to one hinge particle — selected once by a seed-pure rule constrained to an unsealed lineage, then pinned immutably in world metadata. Causality does not wrap in v1. | ADR-008 |
| Every material change to node substance chronicles its delta (with event strength) through one atomic, per-node-versioned write API; state-at-T is born row + ordered fold of deltas. Must land before any history exists. | ADR-009 |
| The launch world stays **seed 382** as born. No ratified decision requires re-birth — the loop needs nothing from generation, delta-fidelity is write-path only — so the census and ecology audits remain valid. | ADR-007 unchanged; this doc |
| Evolution mechanics stay parked on ADR-006's "evolution mechanics are wanted" trigger. ADR-009 lays the event stream they will ride; the grammar (drift kinds, breadth growth, cadence) is designed when the trigger fires. | ADR-006 unchanged; this doc |
| No second dimensional scale (see "Declined" below). | This doc |

---

## The pre-launch sequence (one batch per session/PR)

Only batch 1 is architecturally forced into the window: faithful
recording cannot be retrofitted once history exists. Batches 2–4 carry
no such dependency — the loop and the prediction family could ship
after launch, and the wayback surface reads history whenever recording
began. Sequencing them before launch is a **product decision** — open
with the loop closed, the laws teachable, and the archive running from
the world's first moment — accepted with its cost in launch delay and
integration risk, and re-scopeable without breaking any architecture.

### Batch 1 — Chronicled deltas (ADR-009) · must precede any deploy · SHIPPED

Shipped 2026-08-10, PR #77 (see the CHANGELOG's batch entry for the
measured record and the review-hardening round); ADR-009 ratified Accepted
at its merge gate. As built: one atomic write API
(`persistence.record_substance_change` for absolute deltas,
`record_substance_transition` computing transition deltas under the
serialization lock) with the six writers routed through it; producer-owned
origin events land their one attributed row + delta + overlay change in a
single transaction (`causality.wiring.record_origin_event` /
`record_verb_act`); strength on every fired event's single trace row; the
fold helpers and the ripple rebuild; the migration runner made atomic per
file — all four test families landed, plus same-key concurrency and
interrupted-migration recovery probes. The plan, as it stood:

One atomic write API: a single transaction chronicles the delta + event
strength, applies the overlay merge patch, and allocates a per-node
monotonic version (additive migration if columns). The verified writer
inventory routes through it: the causal effects handler
(`causality/wiring.py:70`), the scale-verb immediate branch on three
surfaces (`server/handlers.py:1215`, `interface/__init__.py:213`,
`server/heartbeat.py:194`), the maturation drain
(`server/heartbeat.py:409`), and constellation lighting
(`server/world_mechanics.py:60`); entanglement resolution writes no
properties. The persisted `ripple_score` is declared a derived,
rebuildable cache (ripple-equals-fold invariant), staying outside the
transaction. Tests: injected-failure, concurrent-writer,
fold-equals-overlay, ripple-equals-fold. Historical completeness — and
the wayback surface (batch 4) that reads it — depends on this landing
while the chronicle is still empty; batches 2–3 do not depend on it,
only on the sequence's product scope.

### Batch 2 — The wrap passage (ADR-008)

The loop, traversal layer only: leaf-descend → root, root-ascend →
hinge. The hinge is selected once by a seed-pure rule constrained to a
fully unsealed lineage (the liveness invariant — on seed 382, 46.9% of
particles sit beneath a locked Room and are ineligible), tuned so 382's
hinge is a worthy node, then pinned immutably in world metadata. Transit
runs through the standard seal gate. Both clients gain the passage
affordance; the hinge particle's lore knows what it is; first crossings
get an authored line. Parent links and causality untouched.

### Batch 3 — Causal-prediction puzzle family

Puzzles that teach the world's *dynamics* the way the existing
world-reading families teach its *structure*: predict how a cascade
carries under the local universe's law (which scale rings loudest,
whether it tunnels, where it dies). Answers are server-computable from
the deterministic engine and never leak. Must pass the ecology gate
(`scripts/puzzle_quality.py` re-audited: family percentages, prompt and
answer uniqueness) and honor the per-node difficulty covenant — scale
flavors, never a depth curve.

### Batch 4 — The wayback surface

Read-only. State-at-T API (fold of chronicled deltas), a time-scrub in
the clients, and evolution animation by feeding reconstructed states to
the *current* deterministic art/sound functions — past state through
present senses (reinterpretation, not playback: a renderer edit changes
how the past appears, exactly as it changes the present), derived
rather than stored, identical for every player at any given deploy.
First-witness display derives from each node's earliest chronicled
interaction (no new write path). Open sub-decision for this batch:
whether pure arrival without interaction should chronicle — default no.
The archive UI honors the chronicle-blurring covenant: it shows *that*
and *how* a node changed, never taxonomizing human vs agent.

### Then: launch prep resumes

Fly setup per `docs/infrastructure/fly-deployment.md` (§8 checklist),
backups, invite minting — and from first history onward,
`phase-2-scale.md` governs.

---

## Declined in the window (recorded to prevent relitigation)

- **A second dimensional scale.** The payoff sought — different
  possibilities, different fundamental laws — is already mechanically
  real in the per-Universe law profiles (`causality/laws.py`), including
  physics changing at universe boundaries. Every scale is a full content
  vertical (voices, lore, puzzle generators, art, sound), so the marginal
  scale costs what each of the eleven cost. Dimensionality is a *reading*
  the lore offers, not a structure the generator needs. Revisit only
  alongside a deliberate second-realm design (ADR-007's revisit clause).
- **Wrapped causality in v1.** See ADR-008 — no convergence guarantee
  under full-strength law profiles.
- **Extensive frontier growth.** The world's stance is intensive
  infinity: finite extent, closed by the loop, with unbounded deepening
  under attention (history, ripple, overlays, transcripts, art, sound
  all already accrue). Observation-born nodes remain parked on ADR-006's
  trigger; if it fires, growth is breadth-only — ADR-008 forecloses
  depth 12, because below the particle is the whole.
