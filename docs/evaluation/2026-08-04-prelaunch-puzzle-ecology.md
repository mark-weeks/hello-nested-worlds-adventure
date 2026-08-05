# Pre-launch Puzzle Ecology — 2026-08-04

## Decision

The launch world must make exploration knowledge useful. Puzzle variation is
therefore a release gate over the full unborn seed-382 world, not an impression
formed from a few hand-picked nodes. Two new deterministic families ship before
production birth, and puzzle identity pins are deliberately re-established.

## Baseline finding

The seed census had already shown that seed choice could not correct puzzle
composition. Across all 4,208 launch nodes, the previous generator produced:

| Family/kind | Count |
|---|---:|
| Anagram | 1,112 |
| Numeric pattern | 1,004 |
| Caesar cipher | 858 |
| Contextual/relational LOCK | 1,146 |
| Riddle | 51 |
| Navigation | 32 |
| Sequence | 5 |

Anagram + cipher + numeric pattern accounted for **2,974 / 4,208 = 70.68%**.
The individual prompts were deterministic and mostly distinct, but the action
the player performed was predictable: decode another token or extrapolate
another number. A different seed would only reshuffle that same grammar.

## Mechanics added

### Keeper Witness

Ancestor names intentionally remain visible in both clients: they are shared
landmarks, not secrets. At one and two stars a player reads one enclosing place
and returns with its three-word living name (the readable words before its path
suffix). At three stars the witness composes a new two-word phrase from named
positions in two ancestors; at four stars it composes three words from three
ancestors. The harder answers therefore cannot be copied whole from the tree,
while the world remains orientable. This turns the generator-v2 name investment
into navigation, observation, and memory rather than decoration.

### Ancestral Compass

A player visits two enclosing scales, reads one immutable categorical property
at each, takes the first and last letter of both readings, and joins the four
marks in outer-to-inner order. It requires multi-scale observation while
remaining compact to enter. Only property keys the overlay never rewrites are
eligible, so an answer cannot change after player or agent actions.

Both families depend only on node identity and the ancestor chain. The
materialized resolver reconstructs that chain without descendants, and behavior
tests prove a full-tree node and a directly resolved stored node produce the
same name, prompt, and answer. Contextual locked Rooms remain authoritative and
cannot be displaced by the weighted selector.

## Executable gate

Run:

```bash
python scripts/puzzle_quality.py --seed 382
```

The hard gate is intentionally systemic:

| Measure | Gate | Seed 382 |
|---|---:|---:|
| Decode-family share | ≤50% | **37.81%** |
| World-reading-family share | ≥55% | **61.50%** |
| Largest single family | ≤25% | **21.91%** |
| Unique prompts | ≥99% | **99.86%** |
| Unique answers | ≥45% | **54.42%** |
| Mechanic families represented | ≥9 | **10** |
| Puzzle kinds represented | ≥7 | **8** |

Final family counts:

| Family | Count |
|---|---:|
| Keeper Witness | 922 |
| Ancestral Compass | 903 |
| Numeric pattern | 557 |
| Anagram | 556 |
| Cipher | 456 |
| Lineage | 332 |
| Bond | 281 |
| Sealed lock | 140 |
| Hand-written | 51 |
| Enfold | 10 |

The thresholds prevent a future vocabulary expansion from being mistaken for
mechanic diversity, and prevent either new family from simply becoming the new
monoculture. The family classifier strips renewal suffixes, identifies the
static authored pool before generated naming conventions, and fails loudly on
an unregistered future family instead of silently counting it as hand-written.

## Launch evidence

The four pitch captures were also rebuilt from generator v2 / seed 382. The
capture command births an isolated temporary database, drives the real explorer
in Chromium, solves a real Keeper Witness, observes its durable staged cascade,
runs a deterministic Tessera heartbeat in the same live room, and draws the
eleven NodeArt families. It chooses an ephemeral loopback port, verifies both
the served seed and capture manifest are 382, and never opens the user's normal
world database.

```bash
npm --prefix frontend run capture:pitch
```

`docs/pitch/assets/capture-metadata.json` records the exact arrival node,
cascade node and puzzle, art chain, heartbeat origin, and feed lines shown.

## One-way-door record

- Production is undeployed and seed 382 is not born in production.
- Puzzle generation changes epoch-0 and renewal puzzle identity, which keys
  durable solved state. The depth-6, full-world, renewal-1, and renewal-2
  digests are consciously re-pinned in this pre-launch window.
- No migration, generator-version change, stored-node rewrite, or new
  `world_mutations` write path is introduced.
- Already-born local/development worlds keep their stored nodes, but this
  pre-release branch deliberately changes their generated puzzle identities;
  prior local solved-state associations do not carry to the new names/answers.
- After production birth and play, changing these families or weights for
  existing epochs requires the same continuity review as any puzzle-identity
  change; future additive puzzle evolution belongs in the renewal/evolution
  grammar.
