# ADR-033: The Scale Registry — scale as a versioned charter, not twenty-five tables

**Status:** Proposed draft, 2026-10-03, written at the owner's request after the
[ambition-and-boundaries assessment](../evaluation/2026-10-03-ambition-and-boundaries.md)
(decision D5). Not ratified. This document introduces no runtime behavior,
migration, or write path. It keeps [ADR-008](ADR-008-wrap-passage.md)'s
refusal of a twelfth depth and the per-node difficulty covenant unchanged. It
supplies the `direction_version` [ADR-030](ADR-030-render-contract.md) keys on,
the charter kinds [ADR-031](ADR-031-model-authorship.md) may propose under its
tiers, and the place [ADR-029](ADR-029-evolution-grammar.md) reserved for new
kinds of place.

---

## Context

"Scale is meaning, not decoration" is a covenant: new verbs must change real
properties at their own scale; sound must distinguish scales through form and
timbre; generic operations renamed per scale do not satisfy it. The codebase
honors the covenant by hand, once per surface. The eleven scales are
enumerated by name in about twenty modules, as roughly twenty-five literal
tables that must agree with each other and are kept in agreement by tests:

| Surface | Table | Location |
|---|---|---|
| Birth | `LEVELS`, `BREADTH_BY_LEVEL`, `NAME_FORMS`, `_LEVEL_GENERATORS`, `_NAME_SPACE` | `multiverse/generator.py:32,59,123,419,178` |
| Verbs | `VERBS`, `MATURATION_SECONDS` (one verb per scale), `EXTRA` (three more per scale), v3 prose | `multiverse/verbs.py:267,26`, `multiverse/interventions_v2.py:23`, `multiverse/interventions_v3.py` |
| Description and senses | per-scale description rules; ancestor stops at Region and Planet | `multiverse/description.py`, `multiverse/senses.py` |
| Voice | `LEVEL_VOICES`, `LEVEL_LORE`, `LEVEL_FALLBACKS`, the premise's "eleven nested scales", `_SCORE_FORMS` | `consciousness/__init__.py:77,141,751,370,908` |
| Puzzles | `CANONICAL_LEVELS`, `_WORD_BANKS`, `_ENFOLD_LEVELS`, `_TOTAL_SCALES = 11`, `_LINEAGE_LEVELS`, `_AUGURY_LEVELS`, `LEVEL_POOLS` | `puzzles/generators.py:54,86,714,719,739,954`, `puzzles/data.py:332` |
| Mechanics | `CONSTELLATION_LEVELS`, entanglement only at particles, the wrap's two literals | `server/world_mechanics.py:20,97`, `multiverse/wrap.py:63-64` |
| Image direction | `HIERARCHY_STYLES` | `server/imageprompt.py:22` |
| Census | per-scale property keys and expected cardinalities | `multiverse/quality.py:28-55` |
| Cast | `home_levels` | `agents/roster.py:39` |
| Terminal | `_LEVEL_STYLES` | `interface/__init__.py:25` |
| Browser | `LEVEL_BASE`, `SCORE_PROFILES` and its per-scale switch, `LEVEL_R`, wrap literals, `MAX_WORLD_DEPTH = 11` | `static/nodeart.js:38`, `static/score.js:7,62-113`, `static/explorer.js:40`, `static/clientlogic.js:139`, `frontend/src/App.jsx:21` |
| Pins | voice forms equal score profiles with exactly eleven entries; both golden depths | `tests/test_frontend_contract.py:303`, `tests/test_continuity_freeze.py` |

Depth, level and index are the same number everywhere: `len(path)` must equal
`LEVELS.index(level) + 1`; `_path_ordinal` is a mixed radix over each parent
scale's maximum breadth; the name scheme's injectivity proof (6,912 phrases
per scale against at most 6,144 nodes) depends on every scale having disjoint
form words. Adding a *kind* of place today, say a vault among Rooms with its
own verbs, voice, puzzle flavor and musical variant, means editing most of the
tables above, bumping `GENERATOR_VERSION`, and re-pinning both golden suites.
That cost is why the world has eleven kinds of place and will otherwise keep
eleven. The assessment's finding stands: scale as meaning is a design
covenant, but scale as twenty-five literal tables is an incidental choice the
sacred layer never depended on.

Two decisions already assume this one. ADR-030 keys paid renderers on a
`direction_version` and says it "move[s] into the registry record" when the
registry lands. ADR-031 lists "art-direction text per scale" and "scale
charters" among the things a model may propose under its tiers, which is only
coherent if a charter is data.

## Decision

### D1. A charter per scale, versioned, stored as data

A **scale charter** is one record that holds everything a surface needs to
know about a scale. The eleven charters together form a **charter set**, with
a version. Charter set version 1 is a byte-for-byte transcription of the
literal tables above, which is how this decision ships without changing a
single birth, voice, puzzle, pixel or note.

Charter fields, grouped by the surface that reads them:

- **Identity**: name, ordinal in the ladder, plural and article forms, the
  disjoint form-word list (`NAME_FORMS`), the breadth range.
- **Birth**: the property schema (keys, types, ranges, defaults, which keys
  are identity-bearing and so excluded from re-aspecting), the generator
  function id and version that draws them, the census expectations
  (`multiverse/quality.py`).
- **Physics**: the scale's verb and its three v2 operations with their
  property semantics and maturation seconds; which causal mechanics apply
  (constellation container, entanglement, seal-capable, augury-eligible,
  enfold and lineage families).
- **Voice**: register, lore, fallback line.
- **Senses**: image direction baseline, musical form profile, procedural art
  family, material palette hints, the `direction_version` ADR-030 keys on.
- **Puzzles**: word banks, family weights per difficulty, which world-reading
  families apply, the static fallback pool.
- **Presentation**: terminal colour, explorer radius, passage labels.
- **Cast**: which inhabitants call it home.

Every surface in the table above reads the registry instead of its own
literal. The Python modules import from one `multiverse/registry.py`; the
browser receives the presentation and senses slice from a served `/scales`
document at load and keeps the current literals as the keyless fallback.

### D2. The ladder is fixed; kinds are lateral

- The **ladder** (the ordered eleven) does not change. Depth 12 stays
  foreclosed by ADR-008; depth, level and ordinal remain one number;
  `_path_ordinal`, the name scheme and the wrap are untouched.
- A **kind** is a lateral specialization *within* a scale: a charter overlay
  that may narrow or extend a subset of fields (form words, property ranges
  and defaults, verb semantics, lore, musical variant, image direction,
  puzzle flavor, home for an inhabitant) and may not change the scale's
  identity fields, breadth, mechanics eligibility, or ordinal. A vault, a
  workshop and a gallery are kinds of Room; a tidal world and an ice world
  are kinds of Planet. Kinds give the world more kinds of place without a new
  depth, which is the lateral richness the assessment asked for and ADR-029
  deferred here.
- The registry validator enforces, for every charter set: disjoint form words
  across scales (the injectivity proof survives); name space at least the
  maximum node count per scale; every kind's property schema a subtype of its
  scale's; every verb changing a real property of its own scale (the covenant
  made mechanical); musical form and image direction present and distinct per
  scale; a bounded number of kinds per scale so "scale is meaning" is not
  diluted into a taxonomy.

### D3. How a place gets a kind, and how it keeps it

- At birth, under a charter set that defines kinds for a scale, the
  generator draws a kind from the scale's seeded kind weights and records it
  as a born property `kind`. A place born before kinds existed has `kind =
  common`, which is the scale's base charter and is byte-identical to today.
- A kind changes only through ADR-029's `NODE_REASPECTED` event on the
  `kind` key, and only along transitions the registry permits (a workshop may
  fall to ruin; a Room does not become a Planet). Per-node difficulty,
  generation identity and the pinned puzzle instance are unaffected, because
  all three derive from the born name.
- ADR-030's `material` key includes `kind`, so a kind change re-renders the
  plate and cue, and its `structural` key counts `kind` among the
  scene-defining anchors, so a kind change regenerates the volume as well.

### D4. Versioning and the births it governs

- Charter sets are append-only and versioned. Editing one creates version
  n+1; nothing reads version n for a born place except through its recorded
  generator version.
- `GENERATOR_VERSION` becomes the charter set version plus the generator code
  version, dispatchable per ADR-029's D1: a born row records which set birthed
  it; frontier births use the current set; existing rows never change. The
  canonical world's charter set version at birth is pinned once in
  `world_meta` under a new key, write-once like the hinge, so a second realm
  could one day be born under a different ladder of kinds without touching
  this one.
- The golden suites pin two things from now on: that charter set version 1
  reproduces generator v2's births digest-for-digest at both depths (the
  no-change proof), and whatever later set the owner deliberately re-pins to.
  A charter change that alters births still requires the repin procedure and
  the owner's approval for that specific change; the registry does not relax
  the ceremony, it localizes it.
- The consciousness bibles are rendered from the charter set and cached with
  the existing minimum-prefix guard. Version 1 renders byte-identically to the
  current bibles, so the cache prefix does not move at adoption; a later set
  moves it once, deliberately.

### D5. Who may write a charter

- Operator edits, as today's bank edits, through a reviewed migration or a
  `python main.py scales` command with a dry-run validator.
- Under ADR-031: voice, lore, image direction and musical-variant text are
  Tier 2 proposals; a new kind is a Tier 3 proposal, operator-ratified; a new
  scale is not proposable at all. Every charter proposal passes this ADR's
  validator and, for senses, the ADR-028 differentiation gate (blinded
  identification of scale, and of kind within scale, across places) before it
  becomes a default.

### D6. What this ADR does not decide

A twelfth scale or any change to the ladder; player-authored kinds; which
kinds to author first; whether kinds carry their own leaderboard dimensions
(ADR-017); any change to difficulty, seals, the wrap or the hinge.

## Implementing batches and the doors they trip

| Batch | Scope | Doors (irreversibility check) |
|---|---|---|
| **1 — the registry, with no visible change** | `multiverse/registry.py` and an additive `scale_charters` table seeded with set version 1 transcribed from every literal above; every Python surface reads the registry; a parity test asserts registry ≡ literals field by field; the freeze suites prove set 1 births equal generator v2 births at both depths; the voice bibles render byte-identically; `world_meta` pins the canonical world's charter set version | Additive migration; a new write-once `world_meta` key (reviewed once here); **no re-pin**, because births are proven identical; no chronicle write path |
| **2 — the browser reads it too** | `/scales` served from the registry; `nodeart.js`, `score.js`, `explorer.js`, `clientlogic.js`, `App.jsx` consume it with their current literals as fallback; the "voice equals score forms" test becomes "both come from the registry" | None beyond batch 1 |
| **3 — kinds** | the kind overlay schema and validator; seeded kind weights per scale for births under a kind-aware set; `kind = common` for every place born before kinds existed, including the whole set-1 parity world; permitted kind transitions as a registry field consumed by ADR-029's re-aspect validator; the first authored kinds under ADR-031's tiers; `GENERATOR_VERSION` dispatch so new worlds and frontier births use the new set | A charter set version 2 that changes births is a golden re-pin under the repin procedure with the owner's explicit approval; existing rows unchanged |

Tests that gain cases: registry ≡ literal parity for every field in set 1;
births identical under set 1 at depths 6 and 11; the validator's refusal
matrix (overlapping form words, undersized name space, a kind widening its
scale's schema, a verb that changes nothing at its scale, a missing musical
form, too many kinds); `kind = common` serving identically to today; a kind
change only through `NODE_REASPECTED` along a permitted transition; voice
bible byte-identity at set 1; `/scales` fallback to literals when the fetch
fails; and the ADR-028 gate extended to kinds.

## Trade-offs accepted

- **One more indirection on hot paths.** The registry is an in-process
  structure loaded once per charter set; the browser fetches one small
  document per load.
- **A new content-bank surface with the old discipline.** Charters govern
  births and presentation; they never touch a born row. The ceremony for a
  birth-changing edit is unchanged, only localized.
- **Kinds can dilute scale.** The validator caps kinds per scale and requires
  the senses gate; a kind must be heard and seen as its scale first and as
  itself second.
- **Duplicated literals persist as fallbacks for a while.** The parity test
  keeps them honest until the fallback is retired.
- **The voice cache prefix moves when a later set lands.** Once, recorded in
  the CHANGELOG, as any bible change is today.

## Revisit when…

- **The owner wants a kind that needs a field the charter lacks** → extend
  the charter schema by version; never special-case a kind in code.
- **ADR-031's authored charters pass audit for a period** → let Tier 2 charter
  text ratify automatically; new kinds stay operator-ratified.
- **A second realm is wanted (ADR-007's "designed relationship")** → the
  `world_meta` pin lets it be born under a different charter set; the ladder
  itself stays eleven unless an ADR changes ADR-008.
- **Breadth 9 binds for a kind-rich scale** → ADR-029's suffix-encoding
  revisit, not a registry change.
- **The parity fallbacks are never exercised for a release cycle** → retire
  the browser literals.

## Rejected alternatives

- **A twelfth depth or a configurable ladder length.** ADR-008 forecloses
  depth growth for a stated reason (below the particle is the whole); the
  marginal depth costs a full vertical and buys less than lateral kinds.
- **Kinds as a free-text property with no registry.** Nothing would read it;
  "scale is meaning" would become "kind is a word."
- **Per-kind code modules.** The vertical cost is the problem being solved.
- **A registry that may rewrite born rows to assign kinds retroactively.**
  Born rows are immutable; `kind = common` is the honest default and
  re-aspecting is the only path.
- **Letting the model write charters directly.** ADR-031's pipeline is the
  door; a scale is never proposable.
- **Skipping the byte-identity proof at set 1.** It is the whole reason the
  registry can land without a re-pin.
