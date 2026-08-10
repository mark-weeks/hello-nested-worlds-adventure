# The Pre-Launch Window

Nothing is deployed: the hosted server does not exist yet, the chronicle
is empty, and the heartbeat has never run in production. That makes this
a bounded window in which certain decisions are cheap that will be
impossible or expensive forever after. **The window closes the moment the
first production history exists.**

This document records what was decided in the window, sequences the
development batches before launch, and lists what was deliberately
declined so future sessions don't relitigate it. Like
`phase-2-scale.md`, it is a living document — edit in place; when a batch
ships, fold its description into the CHANGELOG entry and mark it here.
When the window closes, this document is history and
`phase-2-scale.md` governs.

Decisions and analysis originate in the 2026-08-10 design thread —
synthesis in `docs/evaluation/2026-08-10-recursion-and-time.md`.

---

## Decisions settled in the window (2026-08-10)

| Decision | Where recorded |
|---|---|
| The hierarchy closes into a traversal-layer loop: every particle descends to the Multiverse root; the root ascends to one seed-chosen hinge particle. Causality does not wrap in v1. | ADR-008 |
| Every material change to node substance chronicles its delta (with event strength) at write time; state-at-T is born row + fold of deltas. Must land before any history exists. | ADR-009 |
| The launch world stays **seed 382** as born. No ratified decision requires re-birth — the loop needs nothing from generation, delta-fidelity is write-path only — so the census and ecology audits remain valid. | ADR-007 unchanged; this doc |
| Evolution mechanics stay parked on ADR-006's "evolution mechanics are wanted" trigger. ADR-009 lays the event stream they will ride; the grammar (drift kinds, breadth growth, cadence) is designed when the trigger fires. | ADR-006 unchanged; this doc |
| No second dimensional scale (see "Declined" below). | This doc |

---

## The pre-launch sequence (one batch per session/PR)

### Batch 1 — Chronicled deltas (ADR-009) · must precede any deploy

Record property deltas + event strength in the chronicle at every
substance-writing site (`causality/wiring.py` effects handler, the verb
producer path, constellation lighting, entanglement resolution). Add the
fold-equals-overlay invariant test. Small diff, one conscious touch of
the chronicle write surface. Everything later in the sequence — and the
completeness of the world's remembered past — depends on this landing
while the chronicle is still empty.

### Batch 2 — The wrap passage (ADR-008)

The loop, traversal layer only: leaf-descend → root, root-ascend → hinge
(pure function of seed; rule tuned so 382's hinge is a worthy node).
Transit runs through the standard seal gate. Both clients gain the
passage affordance; the hinge particle's lore knows what it is; first
crossings get an authored line. Parent links and causality untouched.

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
the existing deterministic art/sound functions — past appearances are
derived, not stored, and render identically for every player.
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
