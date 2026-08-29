# ADR-010: The Causal Augury — puzzles that predict the world's dynamics

**Status:** Accepted 2026-08-29 — ratified by the owner's merge of the
implementing PR (pre-launch batch 3), exactly as ADR-008 and ADR-009
were. Drafted the same day from the recursion-and-time design thread
(`docs/evaluation/2026-08-10-recursion-and-time.md` §4) and the owner's
design interview (coverage, gate class, Inverted-law behavior, and the
re-pin path each ratified in conversation before building).
As built: 430 of 4,077 eligible nodes elected (10.55%), **396 served at
every epoch** (9.41% of all 4,208 puzzles; 34 elected nodes declined
structurally and fall through byte-identically; a form whose answer
leaks is retried with the node's other valid forms, so family identity
survives every renewal — hardened in the PR #80 review round); the
ecology gate passes with world-reading at 65.6% (was 61.5%), decode at
33.7% (was 37.8%), largest family 19.9%, answers 54.1% unique, 11
families, 9 kinds.

---

## Context

The world-reading families (seals, lineage, bond, enfold, Keeper
Witnesses, Ancestral Compasses — 61.5% of the launch ecology) teach the
world's *structure*: what encloses what, what each scale is. The world's
*dynamics* — the twelve per-Universe law profiles in `causality/laws.py`
that route every cascade — are discoverable only by acting and being
surprised. The design thread's verdict: a causal-prediction family, its
answers "server-computable from the deterministic engine," makes the laws
learnable the way science is — hypothesis, tested against the world.

Three facts of the codebase shape everything:

- **Families may read ancestors only.** `build_puzzle` must yield the
  same puzzle for a node built from the full tree and one resolved by
  name — the seal gate builds puzzles from resolver nodes, which carry
  their ancestor chain and never children ("a divergent view could yield
  a differently-named puzzle and a door that no recorded solve can
  open"). So the family predicts the UPWARD arm: a disturbance rising
  from the node through its enclosing scales.
- **The engine is already pure.** Dampening patterns cycle by hop; the
  stochastic-flavored laws (tunnel, drop, drawn dampening) hash
  (law, origin, landing, hop) — no clock, no global RNG. An upward
  forecast over the ancestor chain is therefore a pure function of node
  identity, computable at puzzle-build time and *provably equal* to what
  the live bus and the staged queue would do.
- **Puzzle identity is pinned.** `tests/test_continuity_freeze.py` pins
  epoch-0 puzzle digests at both depths plus renewal epochs; anything
  that changes which puzzle a node serves is a conscious pre-launch
  re-pin (the door the world-becomes-the-puzzle batch walked, legal only
  while production is unborn — which it still is).

The launch world's own physics, measured from the born rows: seed 382's
four universes carry **Fractal (1,189 nodes), Threadbare (1,133), Tidal
(786), Palindromic (1,099)**. No Quantum, no Inverted — so question
forms are chosen to be alive in THIS world, and the full twelve-law
surface is exercised by synthetic-tree tests rather than launch content.

## Decision

A new puzzle family, **the Causal Augury**, serving Region and deeper:

- **The forecast is the physics.** A pure `causality.forecast
  .up_arm_forecast(node)` restates the up-arm walk of
  `CausalityBus._walk` / `staging.drain_due_hops` over the ancestor
  chain — per-hop dampening under the law of the landing scale, the 0.5
  fallback above universes, Threadbare frays, Quantum tunnels, the
  MIN_STRENGTH floor. A behavior test pins forecast ≡ live bus across
  all eleven walkable laws on synthetic trees and across sampled
  launch-world nodes (Inverted is not equivalence-tested — its up-arm
  flips into children, which is exactly why the family declines there;
  that decline is pinned as its own contract); the family does not ship
  without that equivalence.
- **Three question forms**, drawn per node from the forms its forecast
  makes valid, difficulty-shaped per the covenant (difficulty stays the
  node's own 1–4 draw; scale sets flavour only):
  - **REACH** (gentle): how many enclosing scales does the cry still
    sound in? Numeric answer.
  - **TERMINUS**: the living name of the last scale the cry sounds in —
    a world-reading answer that requires traveling (or knowing) the
    lineage AND the law.
  - **ECHO** (hard, where the forecast shows an undimmed hop — the
    Fractal universe's signature): the living name of the first
    enclosing scale where the cry rings undimmed, exactly as loud as at
    the step before.
- **Prompts stay in fiction; hints teach the law.** Gentle prompts name
  the sky's law outright (it is a readable property of the Universe
  node); harder prompts point at the universe by its living name and let
  the player read the law there. Hint 1 is an authored temperament line
  per law ("Fractal skies: every second step keeps its full voice");
  hint 2 is mechanical guidance; hint 3 the usual first mark. Answers
  are counts or living names, never law words or scale words (which
  appear in prompts and would leak).
- **Hash-gated election, not weighted selection.** A seed-pure hash of
  node identity elects ~10% of Region-and-deeper nodes *before* the
  weighted family draw (the lock branch's pattern; locked Rooms keep
  their LOCK — that branch still short-circuits first). Elected nodes
  serve the Augury; every non-elected node falls through
  **byte-identically** to the puzzle it serves today. The re-pin's blast
  radius is exactly the elected set.
- **The family declines under Inverted law** (and wherever the chain
  has no law or no valid form). Flip sends the live one-armed act into
  children the ancestor-chain contract cannot see; on the staged
  both-arm path — production's actual physics — flip is explicitly a
  no-op, so an Inverted up-arm behaves like plain default physics and
  teaches nothing Inverted. Inverted skies keep their surprise for
  act-and-watch learning. A declined elected node falls through to the
  weighted draw like any other.
- **Ecology class: world-reading.** The answer derives from this world
  as born — lineage identity plus the Universe's law made mechanical —
  the same epistemics as Keeper and Compass, applied to dynamics. The
  gate's census classifier, `WORLD_READING_FAMILIES`, and the
  family-count minimum learn the new family; the re-audited numbers land
  in the CHANGELOG.
- **A conscious pre-launch puzzle-identity re-pin**, via the
  `repin-goldens` procedure: the elected nodes' puzzle digests change at
  both depths and renewal epochs. Production is unborn; the owner's
  merge ratifies the re-pin together with this ADR.

## Trade-offs accepted

- **~1 in 12 universes (none on seed 382) never serve the family.**
  Inverted declines by design; the pool narrows, the purity contract
  holds.
- **Answer repetition is structural.** REACH answers are small counts;
  TERMINUS answers are shared by subtrees whose cascades die at the same
  ancestor. The election rate is tuned against the gate's ≥45%
  unique-answer floor, and the census re-audit is the arbiter.
- **The launch world teaches four temperaments, not twelve.** Seed 382
  carries Fractal, Threadbare, Tidal, Palindromic; the other eight laws
  live in the engine and the tests, waiting for any future world that
  draws them. Question forms were chosen to be alive in the world we
  actually launch.
- **Two implementations of one physics.** The forecast restates the
  walk rather than refactoring the bus (touching the live cascade path
  for a puzzle family is the greater risk). The equivalence test is the
  contract that keeps them one physics; if the engine's walk ever
  changes, that test fails before any puzzle lies.

## Revisit when…

- **The engine's walk changes** (new law, changed dampening, staged-path
  physics) → the equivalence test trips; update forecast and pins
  together, consciously.
- **Evolution (ADR-006) ships anything that changes a born lineage or a
  universe's law** → elected nodes' answers derive from born rows; any
  evolution write path that could touch `laws_of_physics` or reshape a
  chain must revisit this family's purity claim first.
- **A future world draws Quantum** → a tunnel question form (the silent
  passage) becomes worth authoring; the forecast already computes it.
- **Downward prediction is wanted** → requires either serving only
  tree-built nodes (breaking the resolver-identity contract) or
  materializing child summaries; a separate decision.

## Rejected alternatives

- **Appending to the weighted family draw.** Perturbs the RNG sequence
  for every node at the affected difficulties, reshuffling most of the
  world's puzzles for no product gain; the hash-gated election changes
  exactly the nodes that serve the family.
- **Renewal-epochs-only (no re-pin).** The family would be invisible at
  launch and invisible to the ecology gate, which audits epoch 0 —
  defeats the batch.
- **A direction question under Inverted law.** One answer word repeated
  across every Inverted node in a world; drags the unique-answer floor
  for a fact a player learns once.
- **Reading children via the full tree for flip laws.** Breaks the
  resolver-identity contract the seal gate depends on.
- **Strength-value answers ("0.147").** Real but hostile: float
  formatting burdens the player with arithmetic transcription, not
  understanding; counts and living names carry the same physics
  legibly.
- **A third ecology class for the family.** Counting it as neither
  decode nor world-reading grows the census denominator and dilutes the
  world-reading floor from 61.5% toward its 55% minimum — a definitional
  purity bought by weakening a covenant metric, when the classification
  ("it reads this world") is true anyway.
