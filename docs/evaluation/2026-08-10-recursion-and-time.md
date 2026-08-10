# Recursion and Time — design-thread synthesis (2026-08-10)

A design session with the project owner explored how recursion, strange
loops, tangled hierarchies, dimensionality, observer-driven growth, and
time relate to the game — and whether pursuing them now is core work or
distraction. This is the synthesis: what was asked, what the code showed,
what was decided, and what was deliberately declined. Decisions land in
ADR-008 and ADR-009; the batch sequence lands in
`docs/roadmap/pre-launch-window.md`.

Context that shaped everything: **nothing is deployed.** The project
lives entirely in the repository; the chronicle is empty. Several
decisions that would be one-way doors after launch are cheap in this
window — and one (recording fidelity) is *only* possible in it.

---

## 1. The traversal loop

**Asked:** What if ascending from the Multiverse lands at SubatomicParticle
scale, and descending below a particle lands at the Multiverse — an
infinite loop with no top or bottom? (An earlier variant — landing in an
*alternate* multiverse tree — was already dismissed by the owner.)

**Found:** The idea is the title made literal (Bohm: every part enfolds
the whole) and *completes* logic the repo already committed to:
non-linear entry abolished the fixed root start, and the per-node
difficulty covenant exists because traversal has no canonical direction.
The dismissed alternate-tree variant is also constitutionally forbidden —
ADR-007 treats a new durable tree as a second world.

The load-bearing implementation insight: **the loop must live in the
traversal graph, never the containment tree.** `law_for`,
`sealing_room`, the lineage puzzle families, and `__repr__` all walk
`node.parent` expecting a finite chain; a mutated parent link breaks all
of them. As a passage affordance the loop touches no stored rows, no
pins, no migrations. Two hazards identified: the seal gate must run at
wrap transit (else the hinge becomes a wormhole past a lock), and
causality must not wrap in v1 (Fractal/Recursive laws carry
full-strength hops — no convergence guarantee, and the staged queue
would never drain).

**Decided:** ADR-008 — many-one enfoldment: every leaf descends to the
root (a property of matter); the root ascends to one seed-chosen hinge
particle (a discoverable monument in the shared world). Traversal layer
only; causality tree-bounded; crossings chronicled in fiction.

## 2. Observer-driven richness vs. frontier growth

**Asked:** Doesn't a node grow richer the more players traverse and
engage it — and isn't that natural observer-driven frontier growth as
players move into undiscovered nodes?

**Found:** The deepening half is already implemented end-to-end:
interaction history feeds the voice prompt, per-speaker transcripts make
conversations multi-turn, ripple and causal pressure color the voice,
effects durably change substance, and art/sound/imagery all read history
and pressure. A node with empty history truthfully presents as
unwitnessed, so the gradient is real. But it is **intensive growth
(deepening), not frontier growth (extension)**: every node is fully
formed at birth; fresh territory is revealed, not caused to exist. The
distinction matters because the launch world's quality guarantees are
census-audits over a finite pre-born population — observation-born nodes
would trade that for per-birth invariants.

The stance adopted: **intensive infinity** — finite extent, closed by
the loop, unbounded deepening under attention — is the more Bohmian
architecture (the hologram is a finite plate with unbounded depth), and
it is what the game already is. Extensive growth stays parked on
ADR-006's evolution trigger; if it ever fires, ADR-008 forecloses depth
growth (below the particle is the whole), leaving breadth-only.

## 3. Dimensionality — a second scale?

**Asked:** Universe reads as 4D (possibility), Multiverse as 5D
(different laws). Should there be another dimensional scale?

**Declined.** The payoff is already mechanically real: twelve per-Universe
law profiles (`causality/laws.py`) with physics changing at universe
boundaries deliver the "different laws" experience. Every scale is a
full content vertical (voices, lore, puzzle generators, art, sound); the
marginal scale costs what each of the eleven cost. Dimensionality is a
reading for the lore, not a structure for the generator. Recorded in the
pre-launch roadmap so future sessions don't relitigate.

## 4. Puzzles as instruments of understanding

**Asked:** Should puzzles work the way science does — solving them
builds a predictive understanding of the world? Multi-disciplinary?

**Found:** Largely already true for *structure*: the world-reading
families (seals, lineage, bond, enfold, Keeper Witnesses, Ancestral
Compasses) are 61.5% of the launch ecology. The open frontier is
*dynamics*: the twelve causal laws are currently discoverable only by
acting. A causal-prediction family — hypothesis, tested against the
deterministic engine — makes the laws learnable with server-computable,
no-leak answers. Multi-disciplinary as flavor-per-scale is already the
house rule; out-of-fiction trivia would break the world's voice.
Scheduled as pre-launch batch 3, through the ecology gate.

## 5. The wayback machine, and the gap it exposed

**Asked:** An archive letting players observe a node's past states —
animations of its art evolving through time, sound tracking the same
evolution. And: should properties change through time with interaction?

**Found:** The architecture half-built this by constitution: the
append-only chronicle is the data substrate, and deterministic art/sound
mean past *appearances* are derivable from past *state* — the animation
is a derivation, not storage. Properties already change through
interaction in the punctuated, event-driven sense (`effects.py`:
stabilized, danger, condition decay; verbs; the renewal loop). The
accumulative sense (drift under sustained attention) is ADR-006's
evolution grammar — and the archive and the grammar turn out to be one
design seen from two ends: an event-sourced substance stream.

**The verified gap:** state-at-T is *not* reconstructible today. The
chronicle records event payloads without strength
(`causality/wiring.py:41`, `causality/__init__.py:26`); the effects
handler persists deltas to the overlay without chronicling them; the
overlay is a `json_patch` current-state merge with no history
(`persistence/__init__.py:805`). Replay is no fix — it needs the
unrecorded strength and would tie history to current effects code (the
era-names lesson: store at write time, never recompute history at read
time). **An archive is only as complete as its earliest recording**, so
the fix must precede any production history. Decided as ADR-009,
sequenced as pre-launch batch 1.

## 6. Verdict on the framing question

The ideas were not distractions: three of the four extend commitments
the repo already made (the loop completes non-linear traversal; the
archive is the first player-facing payoff of the append-only covenant;
prediction puzzles extend the world-reading ecology), and the one that
didn't pull its weight (a second scale) was declined and recorded. The
practical yield of the thread is the pre-launch window itself: a decision
deadline that turned philosophy into a sequenced plan.
