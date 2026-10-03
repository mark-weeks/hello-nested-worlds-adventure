# ADR-029: The Evolution Grammar — a born world that changes shape, as chronicled events

**Status:** Proposed draft, 2026-10-03, written at the owner's request after the
[ambition-and-boundaries assessment](../evaluation/2026-10-03-ambition-and-boundaries.md)
(decision D1). Not ratified. This document introduces no runtime behavior,
migration, or write path. On ratification it supersedes the exclusion clause in
[ADR-013](ADR-013-versioned-situations-and-delivery.md) ("Do not add renames,
reparenting, new scales, era-bank changes, or new geography to this first
contract") for everything except new scales, which belong to the scale-registry
decision (D5, not yet drafted), and depth growth, which
[ADR-008](ADR-008-wrap-passage.md) forecloses.

---

## Context

[ADR-006](ADR-006-evolving-world-with-memory.md) materialized the world so
that change could become an event. Its Option B text named the grammar it
expected to follow: "frontier growth… Deliberate change to an existing node — a
rename, a re-aspect, a terrain shift — becomes a chronicled world event…
witnessed, era-stamped… Old chronicle rows keep the old name — that is what
memory *is*." Its evolution trigger fired on 2026-09-07. ADR-013 answered with
"the minimum contract" and excluded structure. At HEAD the world can change the
*properties* of existing places through roughly fifty-five verbs and operations
and one authored situation; it cannot grow a place, rename one, re-aspect one by
decision, open a passage, retire a place, turn an era, or change a universe's
law.

What makes structure immutable today is not the chronicle. It is five
implementation facts:

1. **Identity is the display name.** `multiverse/store.py:145`
   (`resolve_node_by_name`) parses the path from the name's digit suffix, then
   refuses when the stored row's `name` differs. Every durable table keys on
   `node_name` (`world_mutations`, `node_runtime_state`, `node_images`,
   `causal_queue`, `verb_maturation`, `agent_attention`, `puzzle_instances`,
   `journal_notes`, situation tables, `interventions`, `invite_keys.last_node`,
   `agent_memory.visited_ids`). `world_nodes.path` is the primary key, and no
   history reader joins through it.
2. **The chronicle knows one change kind.** Deltas are RFC 7396 property
   patches ([ADR-009](ADR-009-chronicled-deltas.md)); `get_wayback_state`
   (`persistence/__init__.py:1693`) folds one name's properties.
3. **Birth is whole-world or nothing.** `save_world_nodes`
   (`persistence/__init__.py:1966`) returns 0 if any row exists for the seed;
   there is no path that adds one child to a born parent. `GENERATOR_VERSION`
   (`multiverse/store.py:41`) is a stamp nothing reads back.
4. **Topology is rebuilt from paths.** The only non-tree passage is the wrap,
   which lives in the traversal layer (`static/clientlogic.js`, `App.jsx`
   `crossWrap`) and is pinned to stay out of containment
   (`tests/test_wrap_passage.py::TestContainmentUntouched`).
5. **Generation derives from the name.** `puzzles/generators.py:245`
   (`node_rng`), the renewal-epoch hash (`:1142-1144`) and the augury content
   hash (`:1167`) all seed from `node.name`; era names are recomputed at read
   time from two frozen banks (`multiverse/chronicle.py:22-52`).

What must stay true, verbatim from the covenants: the chronicle is append-only
with three maintenance mechanisms; born rows are never rewritten; one canonical
world; the hinge is pinned; the seal never imprisons; the chronicle carries no
actor-type flag; difficulty is per node; causality is tree-bounded.

Timing is the point, as it was for ADR-009. Nothing is deployed and the
chronicle is empty. The identity layer below cannot be retrofitted honestly
after production history begins: a rename recorded without lineage is exactly
the *silent* change ADR-006 says memory cannot survive.

## Decision

### D1. Identity is the path; the name is an alias

- The stable identity of a place is `(world_seed, path)`, the existing primary
  key of `world_nodes`. The born row never changes. The **born name remains the
  generation identity**: `node_rng`, the renewal and augury hashes, art and
  sound keep deriving from it, so a place stays a pure function of birth plus
  served state whatever it is currently called.
- An additive table `node_aliases(world_seed, path, name, valid_from_id,
  valid_to_id)`, seeded at migration with one open row per born node. The
  **display name** at any cursor is the alias row valid at that chronicle row
  id. Exactly one alias is open per path; a name is never reused by a different
  path within a world, so every historical chronicle row still names one place.
  Every alias keeps the mandatory path-digit suffix, so the ancestor-chain
  lookup in `resolve_node_by_name` is unchanged.
- `resolve_node_by_name` accepts any alias the world has ever had and serves the
  node under its current display name. A name that was never an alias of its
  path is still forged and still 404s.
- Readers of name-keyed tables resolve through the alias table to the path, and
  writers record the display name current at write time. Old rows keep the old
  name. The implementing batch adds additive `node_path` columns where a join is
  hot and joins through aliases where it is not; the acceptance test is
  behavioral: after a rename, solve state, seals, constellations, pinned puzzle
  instances, pending causal, maturation, intervention and situation work, saved
  positions, home bookmarks, agent memory and attention, and the overlay cache
  all answer identically.
- `GENERATOR_VERSION` becomes dispatchable: a single path can be generated
  under a named version, births record the version actually used, and frontier
  births (D2.a) are pure functions of `(seed, path, generator_version)`.

### D2. Seven structural event kinds, each a chronicle row through the atomic path

Every kind below is one `world_mutations` row written inside the ADR-009
atomic transaction (`_insert_substance_row` or a sibling sharing its
transaction), with a `node_version`, an `authority` (D4) and a `reason`. None
rewrites a born row or an earlier row. Redaction, double-gated pruning and
whole-DB restore remain the only maintenance mechanisms.

| Kind | Recorded on | Payload | What it changes | Invariants |
|---|---|---|---|---|
| `NODE_BORN` | the new child, paired with `FRONTIER_GROWN {child_path}` on the parent | born properties, generator version or ratified content ref | Inserts one `world_nodes` row via a new `save_frontier_node` that refuses an existing path; served breadth = born + grown − retired | Breadth ≤ 9 per parent (`MAX_GENERATOR_BREADTH`, single-digit suffix); depth ≤ 11 (ADR-008: below the particle is the whole); level is the parent's successor in `LEVELS`; name allocated by the injective scheme or validated unique across all aliases; a child born `locked` is a Room as today and never on the hinge lineage |
| `NODE_RENAMED` | the node | `{from, to}` | Closes the open alias and opens the new one in the same transaction; `delta` is null | Suffix unchanged; `to` never previously an alias of another path; generation identity unchanged |
| `NODE_REASPECTED` | the node | an RFC 7396 delta | A normal ADR-009 substance change with this `mutation_type`, so Wayback already folds it | Forbidden keys: `locked` (`puzzles/gates.py`: the gate is state, never mutation), `laws_of_physics` (that is `LAW_SHIFTED`), and anything a scale schema marks identity-bearing |
| `PASSAGE_OPENED` / `PASSAGE_CLOSED` | both endpoints | `{from_path, to_path, kind}` | Opens or closes a traversal-layer edge in an additive `world_edges(world_seed, from_path, to_path, kind, opened_id, closed_id)`; edges join the passage surface beside the wrap | Containment untouched (`parent`/`children` never express an edge); causality, forecast, lineage puzzles and `sealing_room` never traverse edges; the seal gate runs at transit, so an edge is never a wormhole past a lock (ADR-008's hazard) |
| `NODE_RETIRED` / `NODE_REOPENED` | the node | `{successor_path or null}` | The row stays; the place leaves passage lists and the puzzle ecology and accepts no further substance writes; it remains resolvable, readable and scrubbable in Wayback; a traveler standing there is not expelled and may leave outward or to the successor. A merge is a retirement with a successor plus, optionally, a re-aspect of the successor; nothing is copied | Forbidden on the root, on the hinge lineage, on a sealing Room with live sealed descendants, and on any node with pending accepted work until that work completes or is explicitly closed (ADR-013) |
| `LAW_SHIFTED` | the Universe node | delta on `laws_of_physics` to another `LawProfile` key | A substance change; staged hops already read the law at arrival (`causality/staging.py` `_apply_hop`), so no queue rewrite; every augury node in that universe is re-armed with a `PUZZLE_REARM` row, because [ADR-010](ADR-010-causal-prediction-puzzles.md)'s answers were forecasts under the old law; old pinned instances remain readable evidence (ADR-024) | ADR-010's purity claim is restated as "pure under the law current at instance creation" |
| `ERA_TURNED` | the Multiverse root | `{era_id, name}` | Materializes eras in an additive `eras(world_seed, era_id, name, opened_id, opened_at)`; the two display banks seed the first rows (every week already displayable is stamped with the name the banks would have produced, so nothing shown changes) and are then free for future turns; `era_name` reads the table first | Closes ADR-006's era-bank trigger; the freeze test's exact-string pin moves from the banks to the stamped rows |

Inverses are part of the grammar: a rename is its own inverse, passages open
and close, a re-aspect is reversed by the inverse delta, a retirement by a
reopening, a law shift by another shift. A birth has no inverse except
retirement; an era turn has none. Correction is always a new event, never a
deletion (ADR-013: "Corrections use explicit compensating events").

### D3. Invariants the validator enforces before any structural event commits

1. Containment stays a tree; no event changes a `parent`.
2. No depth 12; breadth ≤ 9 per parent; names unique across all aliases; the
   suffix always equals the path.
3. The hinge lineage, root to pinned hinge, is immune to retirement and to
   becoming seal-capable; the hinge may be renamed, never retired. This answers
   ADR-008's revisit clause.
4. An edge into a sealed subtree is gated at transit; a Room is retired only
   when its sealed subtree is retired or unsealed.
5. Pending accepted work blocks retirement, not renaming.
6. Per-node difficulty is unchanged by any event, because it derives from the
   born name.
7. Every event names its inverse or states that it has none.
8. The validator is deterministic code. Where ADR-031 later lets a model
   propose, the proposal passes the same validator; the validator is never a
   model.

### D4. Authority: who may evolve the world, and how the decision is recorded

- Structural events are never player traces. Each carries `authority` in its
  payload: `{"kind": "operator", "ref": <CLI invocation id>}` now, and
  `{"kind": "ratified", "ref": <proposal ledger id>}` once a model-authorship
  decision (D2 of the assessment, not yet drafted) exists. This is provenance of
  the *decision*, not a taxonomy of participants. `/chronicle` and Wayback keep
  carrying no human/agent flag on traces; a structural moment renders as a
  mechanical change exactly as a delta does today.
- The first triggering surface is an operator command, `python main.py evolve
  <kind> …`, dry-run by default, printing the validator's verdict and the exact
  rows it would write; `--commit` writes. This ADR adds no HTTP write path.
  Players and inhabitants cannot invoke structural events; their agency remains
  the Act grammar of [ADR-028](ADR-028-scale-native-autonomy.md).
- No automatic cadence is introduced. Era turns may be scheduled by the
  operator; model proposals are a separate decision.

### D5. History and Wayback across structural change

- State-at-T gains structure. The node-scoped fold returns the display name at
  the cursor, properties at the cursor, edges open at the cursor, children at
  the cursor (born, plus `FRONTIER_GROWN` rows at or before it, minus retired
  ones), the retired flag, and the era at the cursor. The cursor semantics of
  [ADR-011](ADR-011-wayback-surface.md) are unchanged.
- New moment kinds are `renamed`, `grown`, `passage`, `retired`, `reopened` and
  `era`, beside the existing `birth`, `trace`, `ripple` and `change`. None
  carries an actor.
- Renderers keep interpreting historical state through present senses. A
  retired place renders as it was.
- History rows display the name they were written under; the place's header
  shows its current name with its lineage ("formerly …"). Old rows are never
  rewritten to the new name.

### What this ADR does not decide

New scales or lateral kinds (scale registry); model-authored proposals
(authorship and ratification); player-authored structure; wrapped causality or
cascades along edges; a second canonical world. Each remains with its own
decision and its own revisit clause.

## Implementing batches and the doors they trip

| Batch | Scope | Doors (irreversibility check) |
|---|---|---|
| **1 — identity (must precede first production history)** | Migration 0028: `node_aliases` seeded from `world_nodes`, `node_path` columns where hot; readers through aliases; `resolve_node_by_name` accepting aliases; the behavioral parity suite; dispatchable generator versions | Additive migration, reviewed once here; no new write path; no re-pin |
| **2 — the first events** | `ERA_TURNED` with the `eras` table; `NODE_REASPECTED`; `NODE_RENAMED`; the `evolve` CLI; Wayback moments | New `mutation_type` write paths through the atomic API (covenant-level, reviewed once here); additive `eras` migration; the era freeze pin moves to stamped rows |
| **3 — shape** | `NODE_BORN`/`FRONTIER_GROWN` with `save_frontier_node`; `PASSAGE_OPENED`/`CLOSED` with `world_edges`; `LAW_SHIFTED` with augury re-arm; `NODE_RETIRED`/`REOPENED` | Additive `world_edges` migration; new write paths as above; no golden re-pin unless the generator itself changes |

Tests that gain cases: `TestBankEditImmunity` (frontier births express the
current banks while born rows stay identical), `TestSelectorEditImmunity`
(unchanged), `TestContainmentUntouched` (no edge ever appears in a parent link),
`tests/test_wayback.py` (structural moments and the name at cursor),
`tests/test_puzzles.py` (a rename changes no puzzle, difficulty or solve),
`tests/test_causal_delay.py` (edges are not traversed), `tests/test_wrap_passage.py`
(hinge-lineage immunity), and a new `tests/test_evolution.py` (every validator
refusal, alias uniqueness, inverses). The seed-382 golden digests do not change:
frontier births use the current generator and never re-birth existing rows.

## Trade-offs accepted

- **Two names for one place.** Generation identity (born name) and display name
  diverge after a rename. Accepted: that divergence is what memory looks like,
  and the alias table makes it legible rather than silent.
- **Alias joins on hot reads.** Measured in batch 1; `node_path` columns where
  it matters.
- **The world can be edited by an operator.** The covenant that prevented
  silent change by preventing all change is replaced by one that makes change
  loud: every structural event has an authority, a reason, a Wayback moment and
  an inverse. Nothing is ever deleted.
- **The world only grows.** Retired rows stay. Storage is cheap; forgetting is
  not.
- **A law shift re-arms a whole universe's augury puzzles.** Visible,
  chronicled and bounded to that universe; players standing on a re-armed
  puzzle see a renewal, which the world already does.
- **Breadth 9 and depth 11 remain.** Lateral richness is the registry's job.

## Revisit when…

- **Lateral kinds or new scales are wanted** → the scale-registry decision;
  this grammar gains no scale.
- **Model proposals are wanted** → the authorship decision adds the
  `ratified` authority and the proposal ledger; the validator here is reused
  unchanged.
- **Breadth 9 binds in practice** → a wider suffix encoding is a birth-scheme
  change: generator version bump, its own continuity note, existing names
  untouched.
- **Alias reads are measurably slow** → materialize `node_path` on every
  name-keyed table.
- **Players ask to author structure** → a separate decision; this ADR grants
  none.
- **Cascades along edges or around the loop are wanted** → ADR-008's
  convergence argument per law comes first.
- **The first structural event ships in production** → evaluate with the
  cohort whether change-as-event reads as world-life or as churn, as ADR-006
  already asks.

## Rejected alternatives

- **A surrogate integer node id.** The path is already the stable primary key;
  a second key invites drift between them.
- **Renaming by rewriting `world_nodes.name`.** Silent change: breaks ADR-006's
  bank-edit immunity and orphans every history row.
- **Reparenting in containment.** Breaks `law_for`, `sealing_room`, the lineage
  puzzle families, the forecast walk and `__repr__` (ADR-008's finding); the
  traversal layer already proves edges can live outside the tree.
- **Deleting retired nodes.** Violates append-only history and Wayback, and
  would strand a traveler, which the seal covenant forbids in spirit.
- **Structural state in overlays without event kinds.** ADR-009's rejected
  snapshot pattern: state without causes.
- **The model writing structure directly.** ADR-013 and ADR-027's rejection
  stands; authority arrives through ratification in a later decision.
- **An automatic evolution cadence in this ADR.** Grammar first, author second,
  which is ADR-006's own sequencing.
