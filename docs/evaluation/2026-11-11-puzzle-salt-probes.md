# Puzzle salt probes: what a deployment salt hides, measured on seed 382

**Status:** evaluation record, 2026-11-11. It is the evidence behind Proposed
[ADR-038](../decisions/ADR-038-deployment-puzzle-salt.md) (#164) findings 4
and 5, D2, D3, D5 and D7, and the method its Revisit trigger reruns. It
ratifies nothing and authorizes no build. **Counts only:** no puzzle answer,
candidate or prompt appears here, and the probes below print none.

## Why this record exists

The first draft of ADR-038 (`7482379`) measured one thing: how many answers
match the unsalted answer under a test salt (about 14%). It read that 14% as
answers the world fixes. Two adversarial checks found otherwise:
- **Most of those matches are chance,** and a different salt matches a
  different set.
- **There is a stronger offline attack:** an attacker who builds the world
  under salts of their own and publishes ranked guesses.
- **"Off any list" overclaimed.** The protection depends on how many guesses
  the attacker gets.

This record defines that attacker and scores it at four guess limits. It
measures three ways of keying the generator. The comparison changed D2 from
keying the three content draws to keying every draw.

## Setup

- **Code:** branch `claude/adr-038-puzzle-key`, whose code is `main` at
  `e8081c0`; Python 3.11.18 from `./setup.sh`.
- **World:** seed 382 generated in memory at full depth, all 4,208 nodes, as
  born, at epoch 0. A puzzle first opened after players change its evidence
  follows the changed properties instead (ADR-038 finding 2).
- **The salt** (prototype, not product code): `hashlib.sha256` calls in
  `puzzles/generators.py` go through a shim that makes them
  `HMAC-SHA256(salt, <same domain string>)`. An empty salt is byte-identical
  to the shipped generator, and the probe asserts it. Three variants:
  - **`content`:** the three content draws (epoch 0, renewal, Augury content)
    are keyed; difficulty and the Augury election are not. This was the first
    draft's D2.
  - **`content+election`:** the Augury election is keyed as well.
  - **`all`:** difficulty is keyed as well, so every draw is. This is
    ADR-038's D2.
- **Salts:** three deployment salts, `adr038-test-salt-1` to `-3`, and 400
  attacker salts per variant, `adr038-attacker-0` to `-399`. They are test
  values, not production secrets.
- **The offline attacker** never sees a deployment salt. For each node it
  ranks the answers its own builds produce, most frequent first. It is scored
  against each deployment salt at four list lengths:
  - its first guess;
  - its first 3–5 guesses: the deployed puzzle's `max_attempts`, the pooled
    attempts each puzzle has today;
  - its first 12 guesses: ADR-036's proposed daily cap per player;
  - anywhere in its candidate list.

  Its success is a floor on what an offline attacker can do. More salts
  already do better.
- **Run time:** about 9 minutes for 1,211 puzzle-set builds: 403 salts in each of
  the three variants, plus two unsalted builds.

## Results

### All three variants

| | `content` | `content+election` | `all` |
|---|---:|---:|---:|
| same as the unsalted answer | 575–593 (13.7–14.1%) | 267–287 (6.3–6.8%) | 193–211 (4.6–5.0%) |
| 100 attacker salts: first guess | 975–1,031 (23.2–24.5%) | 710–738 (16.9–17.5%) | 595–634 (14.1–15.1%) |
| 100 attacker salts: within 3–5 pooled attempts | 1,563–1,647 (37.1–39.1%) | 1,409–1,486 (33.5–35.3%) | 1,245–1,300 (29.6–30.9%) |
| 100 attacker salts: within 12 guesses | 1,817–1,867 (43.2–44.4%) | 1,753–1,828 (41.7–43.4%) | 1,565–1,582 (37.2–37.6%) |
| 100 attacker salts: anywhere in the candidate list | 2,493–2,572 (59.2–61.1%) | 2,428–2,491 (57.7–59.2%) | 2,185–2,199 (51.9–52.3%) |
| 400 attacker salts: first guess | 985–1,056 (23.4–25.1%) | 719–768 (17.1–18.3%) | 623–670 (14.8–15.9%) |
| 400 attacker salts: within 3–5 pooled attempts | 1,621–1,685 (38.5–40.0%) | 1,464–1,528 (34.8–36.3%) | 1,308–1,351 (31.1–32.1%) |
| 400 attacker salts: within 12 guesses | 1,888–1,957 (44.9–46.5%) | 1,828–1,926 (43.4–45.8%) | 1,658–1,694 (39.4–40.3%) |
| 400 attacker salts: anywhere in the candidate list | 3,410–3,437 (81.0–81.7%) | 3,349–3,398 (79.6–80.8%) | 3,124–3,139 (74.2–74.6%) |
| same under every one of 403 salts | 242 | 0 | 0 |
| two deployment salts agree (3 pairs) | 575–615 (13.7–14.6%) | 266–309 (6.3–7.3%) | 208–238 (4.9–5.7%) |
| ecology-gate failures of 403 | 0 | 0 | 0 |
| `kind_count` at its floor of 8 | 29 of 403 | 32 of 403 | 23 of 403 |

Under salt 1, matches with the unsalted answer by family: `content`
`causal_augury` 319, `keeper_witness` 99, `lineage` 81, `sealed_lock` 39, `bond` 22, `numeric_pattern` 10, `anagram` 4, `ancestral_compass` 3, `enfold` 1; `all` `lineage` 78, `sealed_lock` 39, `keeper_witness` 29, `bond` 20, `causal_augury` 20, `ancestral_compass` 3, `anagram` 2, `enfold` 1, `numeric_pattern` 1.

In variant `content`, the 242 answers that are the same under every salt are all
`causal_augury`. By the unsalted difficulty, 1 to 4: 94, 6,
78 and 64. These are the Augury nodes with a single valid question form.

### ADR-038's D2 (`all`): right within 3–5 guesses, by family

100 attacker salts. Family sizes differ by salt, since the family draw is
keyed.

| Family | Salt 1 | Salt 2 | Salt 3 |
|---|---:|---:|---:|
| `anagram` | 5/527 | 4/510 | 7/507 |
| `ancestral_compass` | 5/835 | 3/821 | 4/842 |
| `bond` | 217/217 | 260/262 | 235/236 |
| `causal_augury` | 267/391 | 285/389 | 253/365 |
| `cipher` | 0/433 | 0/440 | 0/415 |
| `enfold` | 15/15 | 20/22 | 8/9 |
| `handwritten` | 2/53 | 0/45 | 1/43 |
| `keeper_witness` | 313/845 | 304/808 | 328/838 |
| `lineage` | 267/267 | 276/276 | 298/298 |
| `numeric_pattern` | 14/485 | 8/495 | 10/515 |
| `sealed_lock` | 140/140 | 140/140 | 140/140 |

### The ecology gate

Every salt passes in every variant.

| Metric | Limit | Unsalted | `content` | `content+election` | `all` |
|---|---|---|---|---|---|
| `decode_family_ratio` | ≤ 0.50 | 0.337215 | 0.3306–0.3676 | 0.3344–0.3726 | 0.3322–0.3712 |
| `world_reading_family_ratio` | ≥ 0.55 | 0.656131 | 0.6248–0.6623 | 0.6205–0.6599 | 0.6219–0.6618 |
| `largest_family_ratio` | ≤ 0.25 | 0.199382 | 0.1875–0.211 | 0.1875–0.2146 | 0.1849–0.2122 |
| `unique_prompt_ratio` | ≥ 0.99 | 0.999049 | 0.9967–1.0 | 0.9967–1.0 | 0.9962–0.9998 |
| `unique_answer_ratio` | ≥ 0.45 | 0.540637 | 0.5238–0.5625 | 0.5259–0.5675 | 0.5257–0.5646 |
| `family_count` | ≥ 10 | 11 | 11 | 11 | 11 |
| `kind_count` | ≥ 8 | 9 | 8–9 | 8–9 | 8–9 |

### Public sources (finding 5)

On the unsalted world:
- **Anagrams:** 496 of 496 answers are word-bank words.
- **Hand-written pool:** 47 of 47 answers are in the static pools. By kind: ANAGRAM 15, CIPHER 1, NAVIGATION 2, PATTERN 3, RIDDLE 24, SEQUENCE 2.

### ADR-036's band searchers under two salts

The first source block of the
[band-searcher record](2026-11-07-puzzle-band-searchers.md), run unchanged
through the wrappers below, reproduces that record unsalted (lineage's typo
band names 54 of 301 within the 12-miss cap, blind search 0). Within C12:

| Family, model | Unsalted | `content`, salt 1 | `content`, salt 2 | `all`, salt 1 | `all`, salt 2 |
|---|---|---|---|---|---|
| lineage typo (blind 0) | 54 of 301 | 51 of 274 | 49 of 287 | 47 of 267 | 45 of 276 |
| bond typo vs blind | 247 vs 247 | 228 vs 228 | 271 vs 271 | 217 vs 217 | 262 vs 262 |
| sealed_lock typo vs blind | 128 vs 128 | 132 vs 132 | 127 vs 127 | 132 vs 132 | 127 vs 127 |
| ancestral_compass typo vs blind | 602 vs 303 | 578 vs 322 | 582 vs 303 | 573 vs 325 | 582 vs 296 |

ADR-036's pass bar allows at most a fifth of a family's answers more than
blind search names, within `C`.
- **Lineage passes everywhere:** +17.9% unsalted; +18.6% and +17.1% in
  `content`; +17.6% and +16.3% in `all`.
- **Bond and sealed_lock** add nothing.
- **Compass still fails:** +31.1% and +33.8% in `content`; +29.7% and +34.8%
  in `all`.

No verdict changes. In `all`, ADR-036's temperament and difficulty cells
stay balanced: the smallest cells are 234 and 240, and the largest 299 and
289, against 241 and 282 unsalted.

### Sentry frame locals

Under the options `server/observability.py:58-62` passes to
`sentry_sdk.init` (SDK 2.66.1), the capture probe below printed:

```
repo options:               events 2 | salt sent True | answer sent True
include_local_variables=False: events 2 | salt sent False | answer sent False
```

Both values are built at runtime, so neither is in the source lines Sentry
also sends by default.

## Sources

### The salt probe

Run from the repository root: `.venv/bin/python salt_probe.py`. It prints
the JSON the tables above were filled from.

```python
"""ADR-038 salt probe: what a deployment puzzle salt hides, measured on seed 382.

Run from the repository root:  .venv/bin/python salt_probe.py
Reads the repository only; writes nothing; prints counts only, never an answer.

Prototype of ADR-038 D2, not product code: every hashlib.sha256 call in
puzzles/generators.py goes through a shim that makes it HMAC-SHA256(salt, same
string), except the draws a variant leaves unkeyed. Variant "content" keys the
three content draws (the epoch-0 draw `{level}:{name}`, the renewal draw and
`augury-content:`) and leaves difficulty (`difficulty:`) and the Augury
election (`augury-election:`) unkeyed. Variant "content+election" also keys
the election. Variant "all" also keys difficulty. An empty salt is
byte-identical to the shipped generator. The world is seed 382 as born, at
epoch 0.
"""
import collections
import hashlib
import hmac
import json
import sys
import types

sys.path.insert(0, ".")
from multiverse.generator import generate_node_hierarchy  # noqa: E402
from puzzles import generators as g  # noqa: E402
from puzzles import quality  # noqa: E402
from puzzles.data import DEFAULT_POOL, LEVEL_POOLS  # noqa: E402

SEED = 382
DEPLOYED = [b"adr038-test-salt-1", b"adr038-test-salt-2", b"adr038-test-salt-3"]
VARIANTS = {"content": (False, False), "content+election": (True, False), "all": (True, True)}
ATTACKERS = 400                                  # attacker salts per variant
SCORED_AT = (100, 400)
LIST_12 = 12                                     # ADR-036's proposed daily cap C
REAL_HASHLIB = g.hashlib


def shim(salt, key_election, key_difficulty):
    def sha256(data=b""):
        if not salt or (data.startswith(b"difficulty:") and not key_difficulty) or (
                data.startswith(b"augury-election:") and not key_election):
            return hashlib.sha256(data)
        return hmac.new(salt, data, hashlib.sha256)
    return types.SimpleNamespace(sha256=sha256)


def walk(node, out):
    out.append(node)
    for child in node.children:
        walk(child, out)
    return out


NODES = walk(generate_node_hierarchy(seed=SEED, max_depth=11), [])
BUILDS = 0


def build(salt=b"", key_election=False, key_difficulty=False):
    global BUILDS
    BUILDS += 1
    g.hashlib = shim(salt, key_election, key_difficulty)
    try:
        return [g.build_puzzle(n) for n in NODES]
    finally:
        g.hashlib = REAL_HASHLIB


def answers(puzzles):
    return [str(p.answer).strip().lower() for p in puzzles]


base = build()
shipped = [g.build_puzzle(n) for n in NODES]
assert [p.answer for p in base] == [p.answer for p in shipped], "empty salt must match"
base_ans = answers(base)
base_fam = [quality.puzzle_family(p) for p in base]
out = {"nodes": len(NODES),
       "unsalted": quality.summarize_puzzles(base, seed=SEED)["metrics"],
       "unsalted_families": dict(collections.Counter(base_fam))}

# Finding 5's public-source checks, unsalted (counts only).
bank = {w.lower() for words in g._WORD_BANKS.values() for w in words}
pool = {str(p.answer).strip().lower() for ps in [*LEVEL_POOLS.values(), DEFAULT_POOL] for p in ps}
ana = [a for a, f in zip(base_ans, base_fam) if f == "anagram"]
hand = [(a, p) for a, p, f in zip(base_ans, base, base_fam) if f == "handwritten"]
out["public_sources"] = {
    "anagram": f"{sum(a in bank for a in ana)} of {len(ana)} answers are word-bank words",
    "handwritten": f"{sum(a in pool for a, _ in hand)} of {len(hand)} answers are in the static pools",
    "handwritten_by_kind": dict(collections.Counter(p.kind.name for _, p in hand)),
}

for variant, (key_election, key_difficulty) in VARIANTS.items():
    v = out[variant] = {}
    metrics = collections.defaultdict(list)

    def run(salt):
        puzzles = build(salt, key_election, key_difficulty)
        summary = quality.summarize_puzzles(puzzles, seed=SEED)
        for k, val in summary["metrics"].items():
            metrics[k].append(val)
        return puzzles, summary["passed"]

    deployed, passed = zip(*(run(s) for s in DEPLOYED))
    dep_ans = [answers(p) for p in deployed]
    attacker, apassed = [], []
    for i in range(ATTACKERS):
        puzzles, ok = run(f"adr038-attacker-{i}".encode())
        attacker.append(answers(puzzles))
        apassed.append(ok)
    salts = len(DEPLOYED) + len(attacker)
    v["salts"] = salts
    v["gate_failures"] = sum(not x for x in (*passed, *apassed))
    v["gate_ranges"] = {k: [round(min(x), 4), round(max(x), 4)] for k, x in metrics.items()}
    v["kind_count_at_floor"] = sum(1 for x in metrics["kind_count"]
                                   if x <= quality.MINIMUMS["kind_count"])
    # 1. Coincidence with today's unsalted answer, per deployed salt.
    v["same_as_unsalted"] = [sum(a == b for a, b in zip(d, base_ans)) for d in dep_ans]
    v["same_as_unsalted_by_family_salt1"] = dict(collections.Counter(
        quality.puzzle_family(p) for p, a, b in zip(deployed[0], dep_ans[0], base_ans) if a == b))
    # 2. The same answer under every salt built in this variant.
    every = [all(run_[i] == base_ans[i] for run_ in dep_ans + attacker) for i in range(len(NODES))]
    v["invariant"] = sum(every)
    v["invariant_by_family"] = dict(collections.Counter(base_fam[i] for i in range(len(NODES)) if every[i]))
    v["invariant_by_difficulty"] = dict(collections.Counter(
        g.node_difficulty(NODES[i]) for i in range(len(NODES)) if every[i]))
    # 3. An offline attacker who never sees a deployed salt ranks, per node, the
    #    answers its own N builds produce, most frequent first, and is scored at
    #    four list lengths: 1; the node's pooled attempts today (max_attempts,
    #    3 to 5, from the unkeyed difficulty); 12, ADR-036's proposed daily cap
    #    per player; and every candidate it has seen.
    v["attack"] = {}
    for n in SCORED_AT:
        ranked = [[a for a, _ in collections.Counter(run_[i] for run_ in attacker[:n]).most_common()]
                  for i in range(len(NODES))]
        rows = []
        for d, dp in zip(dep_ans, deployed):
            rows.append({
                "top1": sum(r[:1] == [a] for r, a in zip(ranked, d)),
                "within_pool": sum(a in r[:p.max_attempts] for r, a, p in zip(ranked, d, dp)),
                "within_12": sum(a in r[:LIST_12] for r, a in zip(ranked, d)),
                "any_candidate": sum(a in r for r, a in zip(ranked, d)),
            })
        v["attack"][n] = rows
    n0 = SCORED_AT[0]
    ranked = [[a for a, _ in collections.Counter(run_[i] for run_ in attacker[:n0]).most_common()]
              for i in range(len(NODES))]
    by_fam = []
    for d, dp in zip(dep_ans, deployed):
        fam = collections.defaultdict(lambda: [0, 0])
        for r, a, p in zip(ranked, d, dp):
            f = quality.puzzle_family(p)
            fam[f][0] += a in r[:p.max_attempts]
            fam[f][1] += 1
        by_fam.append({f: f"{h}/{t}" for f, (h, t) in sorted(fam.items())})
    v[f"within_pool_by_family_{n0}"] = by_fam
    # 4. Staging vs production: two independent salts, same place, same answer.
    v["salt_pairs_same"] = [sum(a == b for a, b in zip(dep_ans[i], dep_ans[j]))
                            for i, j in ((0, 1), (0, 2), (1, 2))]

out["puzzle_set_builds"] = BUILDS + 1   # + the shipped-generator comparison build
print(json.dumps(out, indent=1, sort_keys=True))
```

### The band-searcher wrappers

`.venv/bin/python <wrapper> <salt or ""> band_searchers.py`, where
`band_searchers.py` is the first source block of the band-searcher record.
The first wrapper is variant `content`; the second is variant `all`.

```python
import hashlib, hmac, sys, types, runpy
sys.path.insert(0, '.')
import puzzles.generators as G
salt = sys.argv[1].encode()
real = hashlib
m = types.SimpleNamespace()
def sha256(data=b''):
    s = data.decode('utf-8', 'replace')
    if s.startswith('difficulty:') or s.startswith('augury-election:'):
        return real.sha256(data)
    return hmac.new(salt, data, real.sha256)
m.sha256 = sha256
if salt:
    G.hashlib = m
sys.argv = [sys.argv[2], '382']
runpy.run_path(sys.argv[0], run_name='__main__')
```

```python
"""Run a script with every hashlib.sha256 call in puzzles/generators.py keyed:
HMAC-SHA256(salt, same string) - ADR-038 D2 as revised (difficulty, Augury
election and the three content draws all keyed). An empty salt changes nothing.
Usage: python salted_run_all.py <salt or ""> <script.py>"""
import hashlib
import hmac
import runpy
import sys
import types

sys.path.insert(0, ".")
import puzzles.generators as G  # noqa: E402

salt = sys.argv[1].encode()
if salt:
    G.hashlib = types.SimpleNamespace(
        sha256=lambda data=b"": hmac.new(salt, data, hashlib.sha256))
sys.argv = [sys.argv[2], "382"]
runpy.run_path(sys.argv[0], run_name="__main__")
```

### The Sentry capture probe

```python
"""Does the repo's Sentry init send frame locals (a salt, a Puzzle's answer)?

The salt and the answer are built at runtime, so neither appears in source
lines that Sentry's default source context also sends. Each run uses a fresh
client with a capturing transport and sends nothing over the network.
"""
import json
import sys

sys.path.insert(0, ".")
import hashlib  # noqa: E402
import hmac  # noqa: E402

import sentry_sdk  # noqa: E402
from sentry_sdk.transport import Transport  # noqa: E402

from puzzles.types import Puzzle, PuzzleKind  # noqa: E402

SALT = "".join(["probe", "-salt-", "ab" * 16])
ANSWER = "".join(["probe", "-answer-", "xyz"])


def keyed_draw(domain):
    salt = SALT.encode()
    hmac.new(salt, domain.encode(), hashlib.sha256).digest()
    raise RuntimeError("failure after a keyed draw")


def puzzle_frame():
    puzzle = Puzzle(name="Probe", kind=PuzzleKind.RIDDLE, prompt="?", answer=ANSWER)
    raise RuntimeError(f"failure in a frame holding {type(puzzle).__name__}")


def capture(**options):
    events = []

    class Capture(Transport):
        def capture_envelope(self, envelope):
            events.extend(i.payload.json for i in envelope.items if i.type == "event")

    # The options server/observability.py:58-62 passes, plus any override.
    sentry_sdk.init(dsn="https://k@o0.ingest.sentry.io/1", transport=Capture,
                    traces_sample_rate=0.0, send_default_pii=False,
                    environment="production", **options)
    for fn in (lambda: keyed_draw("Room:x"), puzzle_frame):
        try:
            fn()
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
    sentry_sdk.flush()
    blob = json.dumps(events)
    return f"events {len(events)} | salt sent {SALT in blob} | answer sent {ANSWER in blob}"


print("repo options:              ", capture())
print("include_local_variables=False:", capture(include_local_variables=False))
```
