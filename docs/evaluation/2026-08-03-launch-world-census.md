# Launch World Census — 2026-08-03

## Decision

**Seed 382 is the one shared launch world.** It ranked first among seeds 1–512
after generator v2 removed invented-syllable names. The census generated trees
in memory only; it did not call the materialized store, create a database row,
or birth a production world.

This is the last seed-selection window. After the production world is born,
changing `NESTED_WORLDS_CANONICAL_SEED` would point players at a different
persistent history and requires the ADR-007 continuity process.

## Why generator v2 was required first

Seed selection could not cure the old naming system. Across sampled v1 worlds,
roughly 79% of display names were one-word syllable constructions such as
`Fenolos`, `Ulauide`, and `Veriunon`; seed 42 contained 100 repeated base names.
The path suffix made those identities technically unique, but did not make them
human-readable or memorable.

Generator v2 assigns every node a three-word semantic phrase from curated
English banks. A mixed-radix path ordinal and seed/level-specific permutation
allocate the 6,912 phrases at each level without replacement. The widest
possible level contains 6,144 nodes, so base-name uniqueness is guaranteed for
every valid world shape. Name, property, and breadth randomness are also
domain-separated: changing one surface in a future generator revision cannot
silently reshuffle the other two.

Examples from seed 382's first-child traversal:

- Elder Reed Cosmos
- Ashen Ember Sphere
- Mossbound Bell Disc
- Golden Anchor Accord
- Quiet Salt Anchorage
- Emberlit Orchard Terraces
- Broken Ember Gallery
- Elder River Instrument
- Distant River Chain
- Distant Tide Nuclide
- Cedar Anchor Quark

## Executable gate

Run:

```bash
python scripts/world_quality.py --seed 382
python scripts/world_quality.py --candidates 512 --top 10
```

The gate measures qualities a player can perceive rather than seed numerology:

| Measure | Hard gate | Seed 382 |
|---|---:|---:|
| Names composed only of curated readable words | 100% | 100% |
| Unique base names, before path suffix | 100% | 100% |
| Unique node aspects | ≥99% | 99.64% |
| Unique full property fingerprints | 100% | 100% |
| Experientially distinct sibling pairs | ≥99% | 99.67% |
| Categorical-bank coverage | ≥95% | 99.28% |
| Variable-branching outcomes represented | ≥90% | 100% |
| All eleven levels present | required | yes |
| Full node count within 2,000–20,000 envelope | required | 4,208 |

510 of 512 candidates passed every hard gate. The score then weighted sibling
distinction and categorical/branching coverage most heavily. Seed 382 scored
99.5973, first overall. Provisional seed 42 passed but scored 97.4487: 96.80%
categorical coverage and only 91.67% branching coverage, versus seed 382's
99.28% and 100%.

## Sensory and puzzle checks

The soundscape is not a shared generic loop. `soundscapeParams(seed, node)`
derives register from all eleven scales, harmony from danger/condition/state,
tonal center from the node's art, texture from its atmosphere or unique aspect,
and timing/space from a node-keyed deterministic stream. A full seed-382 census
found **4,208 distinct parameter fingerprints for 4,208 nodes** and **1,524 of
1,524 sibling pairs sonically distinct**. Existing Vitest behavior specs also
pin determinism, scale-register separation, sibling differentiation, property
response, and safe master gain.

Puzzle selection remains deterministic and was checked because names are part
of its key. The verification pass exposed a legacy static “four-digit lock”
still competing with the upgraded keeper-key mechanic. That duplicate is now
retired, and every `locked` Room deterministically serves the contextual LOCK
whose answer is readable in its parent Region. The epoch-0/full-world plus
renewal-1/renewal-2 digests were consciously re-pinned.

**2026-08-04 follow-up:** the systemic content gate identified here is now
closed. `scripts/puzzle_quality.py` measures the full unborn world; Keeper
Witness and Ancestral Compass families make readable ancestor names and
multi-scale properties playable. Decode families fell from 70.68% to 37.79%,
world-reading families reached 61.57%, and no mechanic family exceeds 21.93%.
The measured design and pre-launch re-pin are recorded in
`2026-08-04-prelaunch-puzzle-ecology.md`.

## Traversal reachability

Both clients initially fetch six levels to keep response and render costs
bounded. Previously that presentation window looked like the end of the world,
making Rooms through SubatomicParticles unreachable through normal exploration.
At a rendered horizon, both clients now show **Look within** and fetch exactly
one additional prefix level while keeping the player on the same materialized
node. Traveler jumps deepen directly to the required level. All eleven scales
are therefore playable without sending or rendering the entire 4,208-node tree
at once.

## One-way-door record

- `GENERATOR_VERSION` intentionally changed 1 → 2.
- Golden birth pins now describe launch seed 382 under generator v2.
- Epoch-0 and renewal puzzle pins changed because node identities changed.
- No production world existed and the census used generator output directly.
- Already-born local/dev worlds remain immutable under ADR-006 and are not
  rewritten or re-born by this change.
