# ADR-008: The Wrap Passage — the hierarchy closes into a loop

**Status:** Proposed 2026-08-10 — drafted from the recursion-and-time design
thread (`docs/evaluation/2026-08-10-recursion-and-time.md`), owner-directed.
The topology choice below follows the thread's recommendation; owner
ratification lands at the merge gate of the implementing PR.
Revised 2026-08-10 after the owner's PR #76 review: the hinge is pinned
immutably at first selection, its lineage carries a liveness invariant,
and the loop's topology claim is stated honestly.

---

## Context

The eleven scales currently have hard edges: ascending from the Multiverse
root goes nowhere, and descending from a SubatomicParticle answers
"leaf node — no deeper paths." Yet the game already abandoned top/bottom
privilege everywhere else: entry is non-linear (no fixed root start —
players drop into the middle of the world), and difficulty is a per-node
property precisely *because* traversal has no canonical direction. The
edges are the last place the hierarchy still behaves like a ladder.

The title's thesis — Bohm's implicate order, *every part enfolds the
whole* — has so far lived in fiction and lore. A particle that opens onto
the Multiverse makes it mechanical: a strange loop in Hofstadter's
spirit, where moving consistently in one direction through a hierarchy
returns you somewhere the hierarchy says you cannot be, while every
local step remains ordinary. Stated precisely: the closed traversal
graph returns every consistent descent to the *whole* — not, in general,
to the traveler's origin. Repeated ascent cycles through the hinge's
ancestor chain, so an off-hinge origin is never re-entered from above,
and descent below the root branches rather than retracing. The loop is a
cyclic traversal graph closing through the root, not an origin-return
guarantee — and the fiction must not promise one. The loop lives in the
*path*; containment stays a hierarchy.

One alternative was considered and dismissed during design: landing wrap
traversal in an *alternate* multiverse tree. Beyond taste, ADR-007 forbids
it — an alternate tree is a second durable world, the exact fracture that
decision closed.

## Decision

The hierarchy closes into a loop **at the traversal layer only**:

- **Descending below ANY SubatomicParticle surfaces at the Multiverse
  root.** Many-to-one: every part enfolds the whole, uniformly — this is
  a property of matter, not of one special place.
- **Ascending beyond the Multiverse root lands at ONE hinge particle** —
  the same monument for every participant, discoverable and shareable in
  the single canonical world. The selector (a pure function of the world
  seed) runs **once**: the chosen hinge is persisted as an explicit
  first-selection record in immutable world metadata, and from then on
  **the stored hinge is the hinge** — mirroring the store's
  born-row-is-identity rule. Permanent world identity must not depend on
  mutable code: once crossings, lore, puzzle state, and player memory
  attach to the hinge, an edited selector would silently move the
  monument. Changing a pinned hinge is an ADR-level continuity decision.
  Selector tuning (so seed 382's hinge lands on a worthy node) happens
  before the first pinning, never after.
- **The hinge must sit on a fully unsealed lineage** — no seal-capable
  locked Room among its ancestors — pinned as a **liveness invariant**
  by a behavior test in the implementing PR. This is not a playtest
  refinement: a root-side traveler arrives from *outside* every seal on
  the hinge's lineage, so the transit seal gate would refuse the
  crossing and the loop would ship dead in one direction. On seed 382,
  **706 of 1,505 particles (46.9%)** sit beneath a generated locked Room
  (owner-measured, PR #76 review) — near coin-flip odds of a dead loop
  without the constraint.
- **The wrap is a passage affordance**, wired through the same movement
  rules as every other transit — including the seal gate
  (`puzzles/gates.py`). A hinge inside a sealed subtree must not become a
  wormhole past the gate. The seal-never-imprisons covenant is untouched:
  the wrap only ever delivers a traveler *in*.
- **Containment stays a well-founded tree.** Parent/child links are never
  mutated to express the loop. Everything that walks `node.parent`
  expecting a finite chain — `causality/laws.py::law_for`,
  `puzzles/gates.py::sealing_room`, the lineage/Keeper/Compass puzzle
  families, `__repr__` — is untouched by construction.
- **Causality does not wrap in v1.** Cascades still terminate at the root
  and at leaves. The Fractal and Recursive law profiles carry
  full-strength hops; a cascade crossing the wrap under them has no
  guaranteed convergence, and the staged `causal_queue` could never
  drain. Wrapped causality is a separate, convergence-analyzed decision
  (see Revisit).
- **Crossings are chronicled and voiced in fiction.** A wrap transit is a
  move like any other in the chronicle; the hinge particle's lore may
  know what it is (consciousness layer), and the first crossing deserves
  an authored line — the world's voice, never mechanism-speak, per the
  fiction covenant.
- **No generation change.** The world needs nothing at birth for this:
  no `world_nodes` change, no re-birth, no `GENERATOR_VERSION` bump, no
  golden re-pin — seed 382 remains the launch world as born. The hinge
  pin itself IS new durable storage: one first-selection record in world
  metadata (an additive migration unless an existing metadata surface
  fits), written once at selection time — traversal-layer metadata
  beside the world, never a rewrite of it.

## Trade-offs accepted

- **Asymmetry.** Many leaves descend to one root; one leaf receives the
  root's ascent. Deliberate: it mirrors the many-one structure of
  unfoldment, and the forced choice (root ascent must land *somewhere*)
  becomes a gift — a pilgrimage site in a world all players share.
- **The loop forecloses depth-frontier growth.** Below the particle is
  the whole, by design. If the ADR-006 evolution grammar ever ships
  frontier growth, it is breadth-only; there is no depth 12.
- **Traversal-only at first.** The loop is experientially a passage, not
  a causal fact — a cascade does not chase a traveler around the loop.
  Accepted so v1 carries no convergence-analysis burden.
- **The hinge concentrates attention.** One particle's puzzle and voice
  carry more weight than an average leaf's. The selector bears that
  curation load — once, before the pin.
- **The liveness constraint narrows the candidate pool.** Excluding
  sealed lineages leaves 799 of 1,505 particles (53.1%) eligible on
  seed 382 — ample, and permanent for any pinned hinge.

## Revisit when…

- **Wrapped causality is wanted** → require a convergence argument per
  law profile (Fractal and Recursive especially: full-strength hops must
  provably decay across the wrap) before any cascade may cross it.
- **The evolution grammar ships** → the pinned hinge cannot move by
  construction (it is stored, not recomputed), but confirm no evolution
  write path can make one of its ancestors newly seal-capable without
  revisiting the liveness invariant.
- **A second communal realm is ever designed** (ADR-007's revisit
  clause) → decide whether realms share one loop or each closes its own.

## Rejected alternatives

- **Alternate-tree landing.** A second durable world; fractures the
  population; forbidden by ADR-007.
- **Mutating parent links to close the loop.** Infinite loops in
  `law_for`, `sealing_room`, lineage puzzle walks, and `__repr__`; turns
  every finite-ancestor assumption in the codebase into a bug.
- **Wrapped causality in v1.** Non-convergent under full-strength law
  profiles; the staged queue never drains.
- **Symmetric every-leaf-both-ways.** Root ascent must still choose a
  single landing per crossing, so the symmetry is illusory — and a
  rotating landing spends the monument without buying real uniformity.
- **One-hinge-only, both directions.** Weaker metaphysics: only one part
  would enfold the whole, demoting the loop from a property of matter to
  a single secret.
- **A code-derived, tunable hinge (the pre-review draft).** Permanent
  world identity depending on mutable code — a selector edit would
  silently relocate the monument after crossings, lore, and player
  memory attached to it; the same trap the materialized store closed for
  node identity (ADR-006).
