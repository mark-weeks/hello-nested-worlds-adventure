# ADR-006: An Evolving World With Memory — the Freeze as Scaffolding, Not Covenant

**Status:** Accepted 2026-07-19 — **Option A ratified by the project
owner** (materialize before launch), chosen over the staged Option B this
ADR recommended: with no permanent history yet in production, the owner
judged pre-launch the cheapest moment for the data-model change and
accepted the launch delay. The pivot shipped the same day; see the
Decision record below and the CHANGELOG batch "The world is data now."

---

## Context

The 2026-07-19 expert ensemble evaluation converged on "the frozen content
ceiling is the biggest unmade decision," and the project owner has
challenged the premise directly: *the goal of the project is an evolving
world; the freeze seems to be a construct manufactured to serve persistence
and memory. Is there a path to both? Do we truly need a freeze?*

This ADR answers that question from the mechanics up.

### What the freeze actually is

The runtime **regenerates the entire world from code on every request** —
`server/handlers.py::_build_world` calls `generate_node_hierarchy` with no
cache; no table stores the nodes themselves. Every durable surface keys on
`(world_seed, node_name)`: the chronicle (`world_mutations`, migration
0001), property overlays and ripple (`node_runtime_state`, 0006), staged
cascades (0007), verb maturation (0010), saved positions, agent memory,
solved-puzzle rehydration (via puzzle names derived from node identity).

Node identity is derived from generation content: each node draws
name → properties → breadth in fixed order from one RNG stream seeded
`SHA-256(seed:path)`. So **the content banks are the world's storage
medium** — editing a bank shifts the draws, which renames nodes, which
severs every history row keyed on the old names (measured: +1 syllable
renames 77/83 nodes). The freeze is not a design goal. It is the integrity
mechanism forced by using code as storage: since the world lives nowhere
but the generator, the generator must never change.

### The separation the freeze conflates

Persistence and memory require exactly two properties:

1. **Stable identity** — a place must remain the same addressable thing
   across time, so history can attach to it.
2. **Append-only history** — what happened is never rewritten.

They do **not** require the third property the freeze actually pins:

3. **Byte-identical regenerability of content from the banks.**

The current name format already contains the split: every name is
`<content base>-<path digits>` (bank words may not contain `-`;
`generator.py` enforces it). The path suffix *is* identity; the base *is*
content. The freeze pins (3) to guarantee (1). Store the world as data,
and (1) is guaranteed by the row itself — (3) becomes a birth-time event,
and the banks are free.

One further alignment worth stating: an evolving world serves the memory
thesis *better* than a frozen one, if evolution is witnessed. The renewal
system already proves the pattern — `PUZZLE_REARM` is change-as-chronicled-
event, not silent drift. A world where places can visibly change, and the
chronicle records that they changed, has more memory than a world where
change is impossible. What memory cannot survive is *silent* change — a
bank edit renaming the Vault out from under its own history. The freeze
prevents silent change by preventing all change; materialization prevents
silent change by making change an event.

---

## Decision record (what shipped under Option A)

- **The store** (`multiverse/store.py`, migration 0013 `world_nodes`):
  the generator runs once per seed as a birthing tool; rows are the
  node's identity; births are lazy (first visit), idempotent, and
  race-safe (`persistence.save_world_nodes` refuses to overwrite — a
  born world is never re-born).
- **The read-path swap**: `server/handlers.py` (`_build_world`, node
  resolution, WS root/resume/move), `server/heartbeat.py`,
  `causality/staging.py`, `main.py`, `interface/` all read the stored
  world; nothing outside `store.birth_world` calls the generator at
  runtime.
- **Equivalence and immunity pinned** (`tests/test_world_store.py`):
  stored ≡ generated at depths 6 and 11; resolution parity including
  every forgery refusal; birth discipline; and **bank-edit immunity** —
  a prepended syllable that would rename essentially every node under
  regeneration changes nothing about a born world, while a world born
  after the edit expresses it (banks govern births, nothing else).
- **Measured**: birth 4,439 rows in ~350 ms (once per seed ever);
  serving depth 6 ~8 ms and full depth ~82 ms vs ~7/~109 ms for the old
  regeneration — the pivot is not a performance trade. Full suite
  800 passed; E2E 3/3 in real Chromium.
- **One read-time generative surface deliberately remains**: era names
  (`multiverse/chronicle.py`) derive from their own two small display
  banks at read time, so those banks stay frozen (pinned by the freeze
  suite). Materializing eras is a small additive follow-up if era-bank
  evolution is ever wanted; out of scope here.
- **Launch consequence**: the ADR-005 staging rehearsal must exercise
  the store path (first-birth on a fresh volume, resume, seals) — it
  now rehearses the world's actual birth.

## Options (as proposed)

### A. Materialize before launch (world-as-data now)

Add a `nodes` table (`world_seed, path, name, level, properties_json,
born_at, generator_version`); birth the canonical world once per seed
(birth-on-first-visit for new seeds); swap every read path — `/world`,
`resolve_node_by_name`, puzzles, voice, verbs — to read the stored world
plus overlays. The generator retires to a birthing tool. Depth becomes a
*view* of the stored tree, so prefix-stability is free by construction.
Banks unfreeze the moment nothing re-reads them for existing nodes.

*For:* cleanest end-state before any permanent history exists (ADR-004:
"the current DB is pre-launch — no legacy burden"). *Against:* rewrites
the runtime read path and the determinism contract — the repo's most
defended invariant — days before launch, under deploy-freeze pressure.
This is precisely the rushed-external-seam profile of the repo's worst
shipped defects, and the exact reasoning ADR-005 used to defer Litestream.
Est. 1–2 weeks including test repointing; delays launch.

### B. Launch with the freeze as scaffolding; pivot to data early post-launch — **recommended**

Pre-launch (cheap, safe, additive):

1. **Re-word the covenant now, before it freezes.** CLAUDE.md and the
   freeze-suite docstrings currently say "post-launch there is no
   re-pinning — the banks are frozen," full stop. Re-scope in writing:
   *the freeze is temporary scaffolding guaranteeing identity stability
   until the world is materialized; its successor is the stored world of
   ADR-006.* This costs a paragraph and prevents the permanent-freeze
   language from becoming the thing that is permanent.
2. **Land the mirror.** An additive migration creates the `nodes` table;
   the server births it from the canonical generator per seed on first
   use; a behavior test asserts mirror ≡ generation at both depths (the
   existing freeze suite keeps running unchanged and now guards the
   mirror too). Nothing reads the mirror yet. Zero risk to launch.

Post-launch, first infrastructure batch (mechanical *because* the mirror
is already proven equivalent):

3. **Pivot the read path** to the stored world; `resolve_node_by_name`
   becomes a lookup (forged names still 404); the generator retires to
   birthing. History migration: none — every stored name already matches
   a birthed row.
4. **Open evolution, in the world's own grammar.** Banks unfreeze for
   new growth: new seeds, renewal-epoch content, frontier growth (new
   children appended to the stored tree — the path-suffix scheme supports
   up to 9 per node). Deliberate change to an existing node — a rename, a
   re-aspect, a terrain shift — becomes a **chronicled world event**
   (`WORLD_EVOLVED` or similar), witnessed, era-stamped, and rendered by
   the same narrator as everything else: "in the Vigil of Emberglass,
   Stillcrest Wastes took a new name." Old chronicle rows keep the old
   name — that is what memory *is* — while identity linkage (the path)
   lets voice, art, and history aggregate across the change.

*For:* achieves the full end-state of A with no launch delay and no
launch-week risk; each step is independently safe and testable; the pivot
happens against a mirror that has been continuously verified in
production. *Against:* the beta launches under the old ceiling for some
weeks; the pivot is a real batch that must actually be done (this ADR's
"Revisit when" makes it a named commitment, not an aspiration).

### C. Era-gated generative evolution only

Keep the pure-function runtime; admit new content only through surfaces
the pins don't cover: renewal epochs ≥ 3, later-generator-version frontier
growth, new seeds. No re-architecture. *For:* zero risk, preserves
offline regenerability. *Against:* existing nodes' base identity stays
frozen forever; version-map complexity compounds; the ceiling is raised,
not removed. This was the evaluation's "escape hatch" — it is the right
*mechanism* for pre-pivot content work, and strictly weaker than B as an
end-state.

### D. Keep the permanent freeze (status quo)

Evolution only via overlays and renewal within existing families.
Rejected by the premise of this ADR unless ratification says otherwise.

---

## What stays sacred under every option

The freeze was protecting real covenants, and they survive it:

- **Identity stability** — under B, guaranteed by the stored row instead
  of the pinned generator. Stronger, not weaker: an entire threat class
  ("a content-bank edit silently rewrites the world") becomes structurally
  impossible rather than test-guarded.
- **Append-only chronicle, additive migrations, redaction-not-deletion** —
  untouched. Evolution needs these *more*, not less.
- **Determinism where players feel it** — art, sound, and puzzles derive
  from the node as served, so co-op reproducibility and deterministic
  screenshots survive; they now follow evolution instead of being walled
  from it.

## What is genuinely lost (accepted — applies to A as shipped)

- **Offline regenerability**: "any client rebuilds the world from a seed"
  ends at the pivot. This is already fiction for browsers (they fetch
  `/world`); the CLI's locally generated worlds will diverge from
  production's evolved world, which is honest — production has history.
- **The freeze suite's current meaning**: pins change role from
  generation-drift alarms to birth-digest and migration-covenant
  invariants. The suite shrinks in threat coverage because the threat
  shrinks.
- **A second copy of the world to operate**: the DB becomes the sole
  authority for world content, raising the stakes on the backup posture —
  which ADR-005 §1 has already raised (hourly now, continuous replication
  scheduled). Litestream matters more now, not less.

## Revisit when…

- **Evolution mechanics are wanted** (frontier growth, new families via
  renewal epochs, deliberate change to a born node) → design the
  evolution-event grammar first (event kinds, cadence, operator-only
  triggering at first, how a rename records lineage) — the store makes
  these *possible*; nothing ships until the grammar is decided. New
  chronicle write paths remain one-way doors under the merge gate.
- **The generator's content or rules change meaningfully** → bump
  `GENERATOR_VERSION` (`multiverse/store.py`) and consciously re-pin the
  golden digests: they now describe what NEW worlds are born as, and a
  silent change to births is still drift worth catching.
- **Era-bank evolution is ever wanted** → materialize era names (small
  additive `eras` table, stamped on first display); until then the two
  chronicle display banks stay frozen and pinned.
- **The first deliberate evolution event ships** → evaluate whether
  change-as-event reads as world-life or as churn to the cohort
  (returning-visitor metric + direct ask).

## Rejected alternatives

- **Domain-separated RNG streams per draw** (name/properties/breadth each
  from their own keyed stream) — reduces blast radius of bank edits but
  any bank-length change still reshuffles that draw's selection across
  ~every node (`index = rng % len(bank)`); making growth non-disruptive
  requires per-node version stamps, which is materialization by another
  name. Converges on B with extra steps.
- **Content-addressed bank selection with stable hashing** — same modulo
  problem; consistent-hashing tricks trade it for partial reshuffles and
  permanent complexity in the hottest code path.
- **Never evolving, marketing the overlay layer as "the evolving world"**
  — the overlay/renewal layer is real evolution of *state*, but the
  ensemble's census is unambiguous about the *content* ceiling (74%
  decode puzzles, frozen banks), and the project owner has explicitly
  rejected the ceiling as a goal.
