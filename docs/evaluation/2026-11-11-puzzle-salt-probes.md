# Puzzle salt probes: what a deployment salt hides, measured on seed 382

**Status:** evaluation record, 2026-11-11. It is the evidence behind Proposed
[ADR-038](../decisions/ADR-038-deployment-puzzle-salt.md) (#164) findings 4
and 5, D2, D5 and D7, and the method its Revisit trigger reruns. It ratifies
nothing and authorizes no build. **Counts only:** no puzzle answer,
candidate or prompt appears here, and the probes below print none.

## Why this record exists

The first draft of ADR-038 (`7482379`) measured one thing: how many answers
match the unsalted answer under a test salt (about 14%). It read that 14% as
answers the world fixes. An adversarial check of that draft found otherwise.
Most of those matches are chance, and a different salt matches a different
set. It also found a stronger offline attack the draft had not measured: an
attacker who builds the world under salts of their own and publishes ranked
guesses sized to each node's public attempt budget. This record defines that
attacker, re-implements the salt the ADR proposes, and measures both, so the
ADR's figures can be re-derived.

## Setup

- **Code:** branch `claude/adr-038-puzzle-key`, whose code is `main` at
  `e8081c0`; Python 3.11.18 from `./setup.sh`.
- **World:** seed 382 generated in memory at full depth, all 4,208 nodes, as
  born. Epoch 0 only.
- **The salt** (ADR-038 D2, prototyped, not product code): every
  `hashlib.sha256` call in `puzzles/generators.py` goes through a shim. The
  epoch-0 content draw, the renewal draw and the Augury content draw become
  `HMAC-SHA256(salt, <same domain string>)`. Difficulty stays unkeyed. The
  Augury election stays unkeyed in variant **D2** and is keyed in variant
  **D2+election**. An empty salt is byte-identical to the shipped generator,
  and the probe asserts it.
- **Salts:** three deployment salts, `adr038-test-salt-1` to `-3`, and 100
  attacker salts, `adr038-attacker-0` to `-99`. They are test values, not
  production secrets.
- **The offline attacker** never sees a deployment salt. For each node it
  ranks the answers its 100 builds produce by frequency. It is scored two
  ways against each deployment salt: its most frequent answer, and its top
  answers up to the node's attempt budget (`max_attempts`, which follows the
  unkeyed difficulty and is 3 to 5).
- **Run time:** about 3 minutes for both variants (206 world builds plus
  the gate summaries).

## Results

### Matches with today's unsalted answers

| | Deployment salt 1 | Salt 2 | Salt 3 |
|---|---:|---:|---:|
| D2: same as unsalted | 578 | 575 | 593 |
| D2+election: same as unsalted | 278 | 267 | 287 |

Under salt 1 in variant D2, by family: `causal_augury` 319, `keeper_witness` 99, `lineage` 81, `sealed_lock` 39, `bond` 22, `numeric_pattern` 10, `anagram` 4, `ancestral_compass` 3, `enfold` 1.

**The same under every one of the 103 salts:** 242 answers in variant D2, all
`causal_augury`. By difficulty 1 to 4: 94, 6, 78 and
64. In variant D2+election: 0.

### The offline attacker

| | Salt 1 | Salt 2 | Salt 3 |
|---|---:|---:|---:|
| D2: most frequent answer right | 975 | 983 | 1031 |
| D2: right within the attempt budget | 1563 | 1621 | 1647 |
| D2+election: most frequent answer right | 710 | 729 | 738 |
| D2+election: right within the attempt budget | 1409 | 1486 | 1467 |

Variant D2, right within the attempt budget, by the deployed puzzle's
family (family sizes differ by salt):

| Family | Salt 1 | Salt 2 | Salt 3 |
|---|---:|---:|---:|
| `anagram` | 4/528 | 8/521 | 9/478 |
| `ancestral_compass` | 5/823 | 3/825 | 6/827 |
| `bond` | 227/228 | 271/271 | 227/228 |
| `causal_augury` | 396/396 | 396/396 | 396/396 |
| `cipher` | 0/426 | 0/430 | 0/441 |
| `enfold` | 14/14 | 21/22 | 5/7 |
| `handwritten` | 1/45 | 1/48 | 0/53 |
| `keeper_witness` | 431/857 | 413/783 | 482/854 |
| `lineage` | 274/274 | 287/287 | 300/300 |
| `numeric_pattern` | 71/477 | 81/485 | 82/484 |
| `sealed_lock` | 140/140 | 140/140 | 140/140 |

### Staging and production

Two independent salts give the same answer at the same place for
590, 575 and 615 of 4,208 places (salt pairs 1–2, 1–3 and 2–3, variant
D2).

### The ecology gate

Every one of the 103 salts passes in both variants (0 failures in each).
Variant D2:

| Metric | Limit | Unsalted | 103 salts |
|---|---|---|---|
| `decode_family_ratio` | ≤ 0.50 | 0.337215 | 0.3322–0.3676 |
| `world_reading_family_ratio` | ≥ 0.55 | 0.656131 | 0.6262–0.6604 |
| `largest_family_ratio` | ≤ 0.25 | 0.199382 | 0.1875–0.2108 |
| `unique_prompt_ratio` | ≥ 0.99 | 0.999049 | 0.9969–0.9995 |
| `unique_answer_ratio` | ≥ 0.45 | 0.540637 | 0.5238–0.5625 |
| `family_count` | ≥ 10 | 11 | 11 |
| `kind_count` | ≥ 8 | 9 | 8–9 |

`kind_count` sits at its floor of 8 under 7 of the 103 salts in variant D2
and 9 in variant D2+election.

### ADR-036's band searchers under two salts

The first source block of the
[band-searcher record](2026-11-07-puzzle-band-searchers.md), run unchanged
through the wrapper below, reproduces that record unsalted (lineage's typo
band names 54 of 301 within the 12-miss cap, blind search 0). Under the two
test salts:

| Family, model | Unsalted | `adr038-test-salt-1` | `adr038-test-salt-2` |
|---|---|---|---|
| lineage typo, within C12 (blind 0) | 54 of 301 | 51 of 274 | 49 of 287 |
| bond typo vs blind, within C12 | 247 vs 247 | 228 vs 228 | 271 vs 271 |
| sealed_lock typo vs blind, within C12 | 128 vs 128 | 132 vs 132 | 127 vs 127 |
| ancestral_compass typo vs blind, within C12 | 602 vs 303 | 578 vs 322 | 582 vs 303 |

Against ADR-036's pass bar (at most a fifth of a family's answers more than
blind search names, within `C`), lineage passes at +18.6% and +17.1%, bond
and sealed_lock add nothing, and compass still fails (+31.1% and +33.8%).
No verdict changes.

### Sentry frame locals

Under the options `server/observability.py:58-62` passes to
`sentry_sdk.init` (SDK 2.66.1), the capture probe below printed
`events: 2 | salt sent: True | answer sent: True`. A salt held in a frame and
a `Puzzle` built in a frame both reach the event as frame locals.

## Sources

### The salt probe

Run from the repository root: `.venv/bin/python salt_probe.py`. It prints
the JSON the tables above were filled from.

```python
"""ADR-038 salt probe: what a deployment puzzle salt hides, measured on seed 382.

Run from the repository root:  .venv/bin/python <this file>
Reads the repository only; writes nothing. Prototype of ADR-038 D2, not product
code: every hashlib.sha256 call in puzzles/generators.py is routed through a
shim. Difficulty (`difficulty:`) stays unkeyed. The Augury election
(`augury-election:`) stays unkeyed in variant "D2" and is keyed in variant
"D2+election". Every other call (the epoch-0 content draw `{level}:{name}`, the
renewal draw and `augury-content:`) becomes HMAC-SHA256(salt, same string).
An empty salt is byte-identical to the shipped generator.
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

SEED = 382
DEPLOYED = [b"adr038-test-salt-1", b"adr038-test-salt-2", b"adr038-test-salt-3"]
ATTACKER = [f"adr038-attacker-{i}".encode() for i in range(100)]
REAL_HASHLIB = g.hashlib


def shim(salt, key_election):
    def sha256(data=b""):
        if not salt or data.startswith(b"difficulty:") or (
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


def build(salt=b"", key_election=False):
    g.hashlib = shim(salt, key_election)
    try:
        return [g.build_puzzle(n) for n in NODES]
    finally:
        g.hashlib = REAL_HASHLIB


def answers(puzzles):
    return [str(p.answer).strip().lower() for p in puzzles]


base = build()
assert [p.answer for p in base] == [g.build_puzzle(n).answer for n in NODES]
base_ans = answers(base)
base_fam = [quality.puzzle_family(p) for p in base]
out = {"nodes": len(NODES),
       "unsalted": quality.summarize_puzzles(base, seed=SEED)["metrics"],
       "unsalted_families": dict(collections.Counter(base_fam))}

for variant, key_election in (("D2", False), ("D2+election", True)):
    v = out[variant] = {}
    deployed = [build(s, key_election) for s in DEPLOYED]
    attacker = [answers(build(s, key_election)) for s in ATTACKER]
    dep_ans = [answers(p) for p in deployed]
    # 1. Coincidence with the unsalted answer, per deployed salt.
    v["same_as_unsalted"] = [sum(a == b for a, b in zip(d, base_ans)) for d in dep_ans]
    v["same_as_unsalted_by_family_salt1"] = dict(collections.Counter(
        quality.puzzle_family(p) for p, a, b in zip(deployed[0], dep_ans[0], base_ans) if a == b))
    # 2. Answers identical under every one of 103 salts (3 deployed + 100 attacker).
    every = [all(run[i] == base_ans[i] for run in dep_ans + attacker) for i in range(len(NODES))]
    v["invariant_under_103_salts"] = sum(every)
    v["invariant_by_family"] = dict(collections.Counter(
        base_fam[i] for i in range(len(NODES)) if every[i]))
    v["invariant_by_difficulty"] = dict(collections.Counter(
        g.node_difficulty(NODES[i]) for i in range(len(NODES)) if every[i]))
    # 3. Offline attacker: 100 salts of their own, ranked candidates per node,
    #    scored against each unseen deployed salt. Budget = the deployed
    #    puzzle's max_attempts, which follows the unkeyed difficulty.
    counts = [collections.Counter(run[i] for run in attacker) for i in range(len(NODES))]
    ranked = [[a for a, _ in c.most_common()] for c in counts]
    v["attack"] = []
    for d, dp in zip(dep_ans, deployed):
        top1 = sum(r[:1] == [a] for r, a in zip(ranked, d))
        in_budget = [a in r[:p.max_attempts] for r, a, p in zip(ranked, d, dp)]
        by_fam = collections.defaultdict(lambda: [0, 0])
        for p, hit in zip(dp, in_budget):
            f = quality.puzzle_family(p)
            by_fam[f][0] += hit
            by_fam[f][1] += 1
        v["attack"].append({"top1": top1, "within_budget": sum(in_budget),
                            "within_budget_by_family": {f: f"{h}/{n}" for f, (h, n) in sorted(by_fam.items())}})
    # 4. Staging vs production: two independent salts, same place, same answer.
    v["salt_pairs_same"] = [sum(a == b for a, b in zip(dep_ans[i], dep_ans[j]))
                            for i, j in ((0, 1), (0, 2), (1, 2))]
    # 5. Ecology gate under every salt built in this variant (103).
    metrics, fails = collections.defaultdict(list), 0
    for puzzles in deployed + [build(s, key_election) for s in ATTACKER]:
        summary = quality.summarize_puzzles(puzzles, seed=SEED)
        fails += not summary["passed"]
        for k, val in summary["metrics"].items():
            metrics[k].append(val)
    v["gate_failures_of_103"] = fails
    v["gate_ranges"] = {k: [round(min(x), 4), round(max(x), 4)] for k, x in metrics.items()}
    v["gate_salt1"] = {k: (round(x[0], 4) if isinstance(x[0], float) else x[0]) for k, x in metrics.items()}
    v["kind_count_at_floor"] = sum(1 for x in metrics["kind_count"] if x <= quality.MINIMUMS["kind_count"])

print(json.dumps(out, indent=1, sort_keys=True))
```

### The band-searcher wrapper

`.venv/bin/python salted_run.py <salt or ""> band_searchers.py`, where
`band_searchers.py` is the first source block of the band-searcher record.

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

### The Sentry capture probe

```python
"""Does the repo's Sentry init send frame locals (a salt, a Puzzle's answer)?"""
import json, sys
sys.path.insert(0, ".")
import hashlib, hmac
import sentry_sdk
from sentry_sdk.transport import Transport
from puzzles.types import Puzzle, PuzzleKind
events = []
class Capture(Transport):
    def capture_envelope(self, envelope):
        events.extend(i.payload.json for i in envelope.items if i.type == "event")
# The options server/observability.py:58-62 passes.
sentry_sdk.init(dsn="https://k@o0.ingest.sentry.io/1", transport=Capture,
                traces_sample_rate=0.0, send_default_pii=False, environment="production")
SALT = "probe-salt-" + "ab" * 16
def keyed_draw(domain):
    salt = SALT.encode()
    digest = hmac.new(salt, domain.encode(), hashlib.sha256).digest()
    raise RuntimeError("failure after a keyed draw")
def handler():
    p = Puzzle(name="Probe", kind=PuzzleKind.RIDDLE, prompt="?", answer="probe-answer-xyz")
    raise RuntimeError("failure in a puzzle frame")
for fn in (lambda: keyed_draw("Room:x"), handler):
    try:
        fn()
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
sentry_sdk.flush()
blob = json.dumps(events)
print("events:", len(events), "| salt sent:", SALT in blob, "| answer sent:", "probe-answer-xyz" in blob)
```
