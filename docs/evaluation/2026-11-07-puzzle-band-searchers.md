# Puzzle band searchers: what warmth and patience leak in a day

**Status:** evaluation record, 2026-11-07, measured 2026-11-10. It is the
evidence behind Proposed
[ADR-036](../decisions/ADR-036-puzzle-temperament.md) (#159) D2's daily cap
and D3's warmth bands, and the definition batch 3's searcher test re-runs. It
ratifies nothing and authorizes no build. **Counts only:** no puzzle answer,
candidate or prompt appears here, and the probes below print none.

## Why this record exists

The owner-requested review of ADR-036 at `d716cc3` found three gaps in D3's
figures. The searchers behind them lived in a scratch directory that is gone,
so no figure could be re-derived and batch 3's "searcher bounds" test had no
searcher or pass bar (finding L5). The figures were counted within `b`
guesses while the record said "patience window" (L7). And one window is the
wrong horizon: strikes count only inside the window, so a player who paces
their guesses is never sent away (M3). This record defines each searcher,
re-implements it against the current code, and measures it at each horizon,
including the 24-hour cap ADR-036 now proposes. A follow-up check found that
the cap's first send-away rule let a returning player reach `C + 1` misses
in a day, and that this record did not say the cap bounds one player's day,
not several; the rule, its proof, the models and a second results table now
cover both.

## Setup

- **Code:** branch `claude/adr-036-puzzle-temperament` at `d716cc3`, whose
  code is `main` at `3200eed` (#153); Python 3.11.18 from `./setup.sh`.
- **World:** seed 382 generated in memory at full depth
  (`generate_node_hierarchy(seed=382, max_depth=len(LEVELS))`), each node's
  epoch-0 puzzle (`build_puzzle(node)`): 4,208 puzzles. No database is used;
  the world is unborn.
- **Families:** `puzzles.quality.puzzle_family`; an augury puzzle whose
  answer is all digits is counted as "augury reach".
- **Per puzzle:** `b` is `max_attempts` (3, 4, 4, 5 by difficulty); the
  temperament is ADR-036 D1's draw; calm patience is `P = max(2, b + t)`,
  with `t` +1, 0, −1 and 0 for patient, proud, prickly and playful. Over the
  census `P` is 2 for 246 puzzles, 3 for 1,049, 4 for 1,642, 5 for 1,002 and
  6 for 269, so the largest calm patience is 6.

## Candidate domains

The searchers are generous: each knows the bank of every reading its puzzle
names. A **bank** is the set of distinct string values, lower-cased, that
the world's nodes at one level hold under one property key.

| Family | What the searcher guesses from | Median domain |
|---|---|---|
| lineage | one first letter from each of the three banks in `_LINEAGE_SOURCES`, every combination | 910 |
| ancestral_compass | the two readings the prompt names; for each, the two-letter edge marks (`_edge_marks`) of its bank's values; every pair | 56 |
| bond | the one parent reading the prompt names (geometry or compound nature): that bank | 10 |
| sealed_lock | the one parent reading the prompt names (weather, terrain or faction control): that bank | 14 |
| numeric_pattern | the integers above the sequence's last term, up to four times it; all 499 answers lie there | — |

## Searchers

- **blind:** guesses the domain in sorted order (numeric_pattern: smallest
  first). A reply says only right or wrong.
- **typo:** hears ADR-036 D3's typo band: *very close* when the guess is at
  Levenshtein distance 1 or less from the answer, or under 15% of the
  answer's length; otherwise *not close*.
- **parts:** hears how many positions of the guess match the answer: the
  per-part metric D3 rejects.
- **bands** (numeric_pattern only): hears the rejected directionless
  magnitude band, `|guess − answer| / answer` cut at 5%, 20% and 50%
  (difficulty 1 and 2), at 5% and 20% (difficulty 3) or at 20%
  (difficulty 4).
- **How the informed searchers choose:** typo, parts and bands are minimax.
  Each guess is the remaining candidate, first in sorted order among ties,
  whose worst-case reply leaves the fewest candidates; the searcher then
  keeps the candidates consistent with the reply. A searcher **names** an
  answer on the guess that is right, and "within `h`" counts the answers
  named on guess `h` or earlier.

## Horizons

`b` (what ADR-036 called a "first window" until this revision), `P`, `2b`,
`2P`, and a 24-hour cap `C` of 8, 12, 16 or 24 judged misses. Under the cap
no player makes more than `C` judged misses at a puzzle in any 24 hours,
however they pace them (proved below). Where `2b` exceeds 8 the `2b` count
can exceed the `C = 8` count. The cap bounds one player's day only: a player
who returns on `n` days, or `n` players who pool what they hear, reach `nC`,
so the 24 column is also two days at 12. Three and seven days at 12 (36 and
84), and each puzzle's own day with no cap (the day model's most for its
temperament and `b`, 32 to 360), are a second table.

## Results

Answers named, seed 382; final run 2026-11-10T19:39:32Z to 19:42:08Z,
whose first table matches the runs at 18:16:12Z, 18:27:20Z and 18:30:19Z
(the last from the earlier version of the block below, extracted from this
file) line for line; the second table is new in that run.

| Family (puzzles) | Searcher | within `b` | `P` | `2b` | `2P` | `C` 8 | 12 | 16 | 24 |
|---|---|---|---|---|---|---|---|---|---|
| ancestral_compass (828) | blind | 137 | 135 | 242 | 231 | 248 | 303 | 351 | 421 |
| | typo | 279 | 273 | 483 | 466 | 495 | 602 | 666 | 760 |
| | parts | 490 | 464 | 800 | 781 | 821 | 828 | 828 | 828 |
| lineage (301) | blind | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 8 |
| | typo | 1 | 2 | 12 | 15 | 9 | 54 | 85 | 153 |
| | parts | 3 | 4 | 82 | 92 | 75 | 256 | 301 | 301 |
| bond (247) | blind, and typo the same | 96 | 97 | 176 | 178 | 183 | 247 | 247 | 247 |
| sealed_lock (140) | blind, and typo the same | 52 | 54 | 89 | 92 | 89 | 128 | 140 | 140 |
| numeric_pattern (499) | blind | 45 | 47 | 176 | 172 | 160 | 272 | 380 | 416 |
| | bands | 268 | 249 | 478 | 467 | 478 | 493 | 493 | 499 |

Over several days at a cap of 12, and in one day with no cap:

| Family (puzzles) | Searcher | 2 days at 12 (the 24 column) | 3 days | 7 days | own day, no cap |
|---|---|---|---|---|---|
| ancestral_compass (828) | blind | 421 | 521 | 726 | 762 |
| | typo | 760 | 804 | 828 | 825 |
| | parts | 828 | 828 | 828 | 828 |
| lineage (301) | blind | 8 | 13 | 28 | 46 |
| | typo | 153 | 235 | 301 | 292 |
| | parts | 301 | 301 | 301 | 301 |
| bond (247) | blind, and typo the same | 247 | 247 | 247 | 247 |
| sealed_lock (140) | blind, and typo the same | 140 | 140 | 140 | 140 |
| numeric_pattern (499) | blind | 416 | 435 | 452 | 469 |
| | bands | 499 | 499 | 499 | 499 |

**Bounds where no searcher was run.**

- **anagram (496):** the generator's word-bank words (`_WORD_BANKS`) that
  share an answer's letters number one for 485 answers and two for 11, so a
  word list names 485 in one guess with no band at all. Without a word list, the letter-arrangement bound
  (`log2(arrangements) / log2(bands at the difficulty)`, with 4, 4, 3 and 2
  bands) exceeds `b` for 458.
- **cipher (405):** the alphabet shift is 1 to 3, 5, 7 or 9 by difficulty
  (`puzzles/generators.py:392-394`, *read*), so at most 9 candidates, inside
  every cap.
- **phrases** (keeper_witness, augury names): replacing one word of a
  multi-word answer with every other distinct name word in the world gives
  493,536 substitutions, of which the typo band reads 4,976 (1.0%) *very
  close*. No phrase searcher exists yet.
- **Census:** 644 generated integer answers (15.30%); temperaments 24.60% to
  25.24%, with 241 to 282 puzzles in every temperament × difficulty cell.

**Against the reviewer's searcher.** The reviewer's independent greedy
minimax searcher on right-mark counts over the same compass domains gave 490
within `b`, 797 within `2b`, 471 within `P` and 778 within `2P`, and blind
alphabetical enumeration 137 within `b`. This searcher gives 490, 800, 464,
781 and 137: equal at `b`, and a few apart elsewhere because equally good
guesses are tie-broken differently.

## A day of paced guessing

One player, calm (a lone player's own load is capped at `b`, below the
testy threshold `2b`), each temperament's strike window `W` and first
send-away from ADR-036 D1, and no daily cap; time spent guessing is not
counted. A player who keeps to `P − 2` misses a window is
never warned; one who keeps to `P − 1` is warned and never sent away; each
gets that many misses in each of the day's `1440 / W` windows. A player who
guesses whenever heard misses `P` times, is sent away for `first × 3^k`
minutes, at most 240 (`k` = earlier send-aways that day), and returns: day one holds `P` misses per send-away until 1,440 minutes have
passed, and later days, with every send-away at the cap, `6P`.

| Temperament | `b` | `P` | `W` (min) | never warned | warned, kept | whenever heard, day one | later days |
|---|---|---|---|---|---|---|---|
| patient | 3 | 4 | 20 | 144 | 216 | 40 | 24 |
| patient | 4 | 5 | 20 | 216 | 288 | 50 | 30 |
| patient | 5 | 6 | 20 | 288 | 360 | 60 | 36 |
| proud | 3 | 3 | 30 | 48 | 96 | 30 | 18 |
| proud | 4 | 4 | 30 | 96 | 144 | 40 | 24 |
| proud | 5 | 5 | 30 | 144 | 192 | 50 | 30 |
| prickly | 3 | 2 | 45 | 0 | 32 | 18 | 12 |
| prickly | 4 | 3 | 45 | 32 | 64 | 27 | 18 |
| prickly | 5 | 4 | 45 | 64 | 96 | 36 | 24 |
| playful | 3 | 3 | 30 | 48 | 96 | 30 | 18 |
| playful | 4 | 4 | 30 | 96 | 144 | 40 | 24 |
| playful | 5 | 5 | 30 | 144 | 192 | 50 | 30 |

Patience bounds a burst, not a day: the paced columns reach 288 and 360
misses, and the window figures above say nothing about them.

## The cap and the pass bar (proposals in ADR-036)

- **The cap.** No player has more than `C` judged misses at a puzzle in any
  24 hours; forgiveness and a send-away ending do not reset the count
  (ADR-036 D2, open question 7). The rule that holds it: a miss at or past
  the `(C − 1)`-th of the day that does not send the player away is warned;
  the `C`-th after a warned miss sends them away; and every send-away lasts
  until at most `C − 2` of their judged misses lie in the last 24 hours.
- **Why that holds.** Suppose a miss `m` is the first to put `C + 1` judged
  misses in some 24-hour span, and let `m1` and `m2` be the two misses
  before it in that span, `m2` the later. The span's other misses all fall
  within the day before `m2`, so `m2` was at least the `C`-th of its day
  and, `m` being the first breach, exactly the `C`-th; likewise `m1` was at
  least the `(C − 1)`-th. If `m1` was warned, `m2` sent the player away
  until at most `C − 2` of the misses up to `m2` lay in the last 24 hours,
  so `m` was at most the `(C − 1)`-th. If `m1` was not warned, it was itself
  a send-away, lasting until at most `C − 2` of the misses up to `m1` lay in
  the last 24 hours, so `m2` was at most the `(C − 1)`-th. Either way, a
  contradiction. The earlier rule, ending the cap's send-away once only the
  oldest counted miss is a day old, fails the first branch: the returning
  player's next miss is the `C`-th but follows the unwarned send-away, so it
  is only warned, and the miss after it is the `(C + 1)`-th.
- **A day, not a campaign.** The cap bounds one player's day. Over several
  days at 12 (the second table), lineage's band names 153, 235 and 301 of
  301 in two, three and seven days, against 8, 13 and 28 blind: the cap
  slows that search and does not stop it, and `n` players pooling what they
  hear do as one player does over `n` days. Keeping lineage's band on a
  one-day bar is ADR-036's default, which the owner can veto (open question
  7). With no cap, each puzzle's own day lets lineage's band name 292
  against 46 blind (+246, 81.7%), so lineage would fail the bar; bond and
  sealed_lock add nothing at any horizon measured.
- **Starting value, `C = 12`.** From play: twice the largest calm patience
  (6), so every temperament allows a full window, a send-away and a second
  window before the cap. From the leak: the band's lift, what the band's
  searcher names within `C` beyond what blind search names, on lineage, the
  only searcher-measured family whose band adds anything, is 9 of 301 (3.0%) at 8,
  54 (17.9%) at 12, 81 (26.9%) at 16 and 145 (48.2%) at 24. Twelve is the
  largest cap tried that keeps it under a fifth.
- **Pass bar.** A family keeps a band only if, within `C`, the band's lift
  is at most a fifth of the family's answers. At `C = 12`: lineage 17.9%
  passes; bond and sealed_lock add nothing; the typo band on compass marks
  (+299 of 828, 36.1%) and magnitude bands on numeric_pattern (+221 of 499,
  44.3%) fail, matching D3's choice of no band for either. Anagram and cipher
  bands add nothing by the bounds above. Phrase families need a searcher
  before the bar can be applied, and batch 3 writes one.
- **Batch 3's test** re-runs these searchers (and the phrase searcher) on
  the seed-382 census and asserts the bar at `C`; a family that fails loses
  its band. A different `C` changes the bar's verdicts, so the test reads
  `C` from the code.

## Fold models

Two exhaustive models of ADR-036 D2's fold, in the second and third blocks
below.

- **Observer model** (finding M1). With `P` steady, a reader of public rows
  flags a warned row that directly follows a warned row with no send-away
  between. Over every band sequence (top band or other) of one to eight
  guesses, `P` 2 to 6, under the fold as `d716cc3` stated it: 1,934 rows
  flagged (698, 460, 312, 240 and 224 for `P` 2 to 6), none of them other
  than top band. The excited warning can be read from public rows, so
  ADR-036 now ships it only once rows hold no guess text.
- **Revised fold.** Strikes in the window since the last send-away; warning
  receipts; the reprieve limited by warned rows from the last 24 hours; and
  the daily cap, with `C = 4` so that short sequences reach it, and every
  send-away lasting until at most `C − 2` misses lie in the last 24 hours.
  Three gap sets, either band throughout: gaps of 0, 10, 35, 300 and 1,500
  minutes, `P` fixed at 2, 3 or 4 for up to six guesses or changing freely
  between 2 and 4 for up to four (4,171,260 sequences); gaps of 0, 1, 600
  and 840, `P` fixed, up to six (898,776); and gaps of 0, 1, 300, 700,
  1,100, 1,439 and 1,441, `P` fixed, up to five (1,737,582). Over all
  6,807,618: 0 send-aways without a warned miss just before them, 0 spans of
  24 hours holding more than `C` judged misses, and 0 spans of 24 hours with
  two excited warnings between two send-aways (run 2026-11-10T19:36:09Z to
  19:38:01Z).
- **The earlier cap rule.** An earlier version of this block ended the
  cap's send-away once the oldest counted miss was a day old and, on the
  first gap set alone, found no breach. Within six guesses that set cannot
  place a return between the two oldest misses' expiry; the second can. Replacing the cap
  branch's `day_out(day_times)` with `daily[0][0] + DAY` gives 19,456 of
  898,776 sequences on the second set with `C + 1` judged misses in a 24-hour
  span (never more), checks A and C still 0, and the first and third sets
  clean: the earlier block run on each set at 2026-11-10T19:36:09Z to
  19:37:59Z, and this block with that one swap, 19,456 over all three sets,
  at 19:43:58Z to 19:45:45Z.

## Reproducing

Copy a block to a file outside the checkout and run it with the checkout's
interpreter from the checkout root, for example
`.venv/bin/python /path/to/band_searchers.py 382` (about three minutes) or
`.venv/bin/python -I /path/to/model_fold.py` (about two minutes). The models
import nothing from the repository. Each prints counts only.

### `band_searchers.py`

```python
"""ADR-036 band searchers and day model (docs/evaluation/2026-11-07-puzzle-band-searchers.md).

Run from a checkout with its package installed:  python band_searchers.py [seed]
Prints counts only. It never prints an answer, a candidate or a prompt.
"""
import hashlib
import statistics
import sys
from collections import Counter, defaultdict
from itertools import product
from math import factorial, log2, prod

from multiverse.generator import LEVELS, generate_node_hierarchy
from puzzles.generators import (_ANCESTRAL_READING_KEYS, _LINEAGE_SOURCES, _WORD_BANKS,
                                _edge_marks, build_puzzle)
from puzzles.quality import _walk, puzzle_family

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 382
CAPS = (8, 12, 16, 24)                      # 24-hour miss caps compared
DAYS = (3, 7)                               # days of play at a cap of 12
TEMPERS = ("patient", "proud", "prickly", "playful")
T = {"patient": 1, "proud": 0, "prickly": -1, "playful": 0}       # D1 patience offset
WINDOW = {"patient": 20, "proud": 30, "prickly": 45, "playful": 30}  # strike window, min
FIRST = {"patient": 3, "proud": 5, "prickly": 8, "playful": 5}      # first send-away, min


def temper(n):
    return TEMPERS[hashlib.sha256(f"temperament:{n.level}:{n.name}".encode()).digest()[0] % 4]


def paced_day(t, b):
    """One calm player's judged misses in a day with no cap: never warned,
    warned but kept, and guessing whenever heard on day one and later days."""
    P, W, starts, k, clock = max(2, b + T[t]), WINDOW[t], 0, 0, 0
    while clock < 1440:
        starts += 1
        clock += min(240, FIRST[t] * 3 ** k)
        k += 1
    return (P - 2) * 1440 // W, (P - 1) * 1440 // W, starts * P, 1440 // 240 * P


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def typo_near(g, a):                      # D3's typo band: one edit, or under 15%
    d = lev(g, a)
    return d <= 1 or d / max(len(a), 1) < 0.15


def reply(model, g, a):
    if g == a:
        return "right"
    if model == "blind":
        return "no"
    if model == "typo":
        return "near" if typo_near(g, a) else "no"
    return sum(x == y for x, y in zip(g, a))  # "parts": marks right in place


def depths(cands, model):
    """Guess on which a minimax searcher names each candidate. Blind takes the
    candidates in sorted order; the others pick, in sorted order, the first
    guess whose worst-case reply leaves the fewest candidates."""
    out, stack = {}, [(sorted(cands), 1)]
    while stack:
        cs, depth = stack.pop()
        if model == "blind":
            out.update((c, i + depth) for i, c in enumerate(cs))
            continue
        best = None
        for g in cs:
            groups = defaultdict(list)
            for c in cs:
                if c != g:
                    groups[reply(model, g, c)].append(c)
            worst = max((len(v) for v in groups.values()), default=0)
            if best is None or worst < best[0]:
                best = (worst, g, groups)
        _, g, groups = best
        out[g] = depth
        stack.extend((sub, depth + 1) for sub in groups.values())
    return out


def mag_band(g, a, d):                    # the rejected directionless magnitude bands
    rel = abs(g - a) / a
    edges = {1: (.05, .2, .5), 2: (.05, .2, .5), 3: (.05, .2), 4: (.2,)}[d]
    return sum(rel > e for e in edges)


def numeric_depth(answer, last, d, banded):
    cands = sorted(set(range(last + 1, 4 * last + 1)) | {answer})
    for count in range(1, len(cands) + 1):
        if not banded:
            g = cands[0]                  # blind: smallest candidate first
        else:
            g = min(cands, key=lambda x: max(Counter(mag_band(x, c, d) for c in cands
                                                      if c != x).values(), default=0))
        if g == answer:
            return count
        cands = [c for c in cands if c != g and (not banded or mag_band(g, c, d) == mag_band(g, answer, d))]


root = generate_node_hierarchy(seed=SEED, max_depth=len(LEVELS))
nodes = _walk(root)
built = [(n, build_puzzle(n)) for n in nodes]
fams = Counter()
integers = 0
for n, p in built:
    f = puzzle_family(p)
    fams[f + (":reach" if f == "causal_augury" and p.answer.isdigit() else "")] += 1
    integers += p.answer.isdigit() and f != "handwritten"
print(f"seed {SEED}: {len(built)} puzzles; generated integer answers {integers} "
      f"({integers / len(built):.2%}); families {dict(fams.most_common())}")
spread = Counter((temper(n), p.difficulty) for n, p in built)
print("temperament x difficulty cells: min", min(spread.values()), "max", max(spread.values()),
      "| shares", {t: f"{sum(v for (x, _), v in spread.items() if x == t) / len(built):.2%}" for t in TEMPERS})
calm_p = [max(2, p.max_attempts + T[temper(n)]) for n, p in built]
print("calm patience P over the census:", dict(sorted(Counter(calm_p).items())),
      "median", statistics.median(calm_p))

print("\nday model (calm; a lone searcher's own load is capped at b, below 2b):")
for t in TEMPERS:
    for b in (3, 4, 5):
        unwarned, kept, first_day, later = paced_day(t, b)
        print(f"  {t:8s} b={b} P={max(2, b + T[t])}: paced unwarned {unwarned}/day, "
              f"warned but kept {kept}/day; sent away each cycle: "
              f"first day {first_day}, later days {later}")

bank = defaultdict(set)
for n in nodes:
    for key, value in n.properties.items():
        if isinstance(value, str):
            bank[(n.level, key)].add(value.strip().lower())
cache, results = {}, defaultdict(list)    # (family, model) -> [(b, P, guesses, domain, day)]
outside = 0                               # numeric answers outside (last, 4 x last]
for n, p in built:
    f, b, P = puzzle_family(p), p.max_attempts, max(2, p.max_attempts + T[temper(n)])
    day = max(paced_day(temper(n), b)[1:3])   # most misses in an uncapped day
    if f == "lineage":
        sets = [sorted({v[0] for v in bank[(lvl, key)] if v}) for lvl, key, _ in _LINEAGE_SOURCES]
    elif f == "ancestral_compass":
        found = sorted((p.prompt.find(f"the {lvl}, "), lvl, key)
                       for lvl, keys in _ANCESTRAL_READING_KEYS.items() for key in keys
                       if f"the {lvl}, read its {key.replace('_', ' ')};" in p.prompt
                       or f"the {lvl}, do the same with its {key.replace('_', ' ')}." in p.prompt)
        sets = [sorted({_edge_marks(v) for v in bank[(lvl, key)] if len(_edge_marks(v)) == 2})
                for _, lvl, key in found] if len(found) == 2 else None
    elif f in ("bond", "sealed_lock"):      # one categorical reading one scale up
        said = {"bond": {"geometry": "Name the geometry of", "compound_type": "Name the compound nature of"},
                "sealed_lock": {k: f"speak its {k.replace('_', ' ')}, and" for k in
                                ("weather", "terrain", "faction_control")}}[f]
        keys = [k for k, phrase in said.items() if phrase in p.prompt]
        sets = [sorted(bank[(n.parent.level, keys[0])])] if len(keys) == 1 else None
    elif f == "numeric_pattern":
        last = [int(x) for x in p.prompt.split(":")[-1].split("?")[0].replace(",", " ").split() if x.isdigit()][-1]
        outside += not last < int(p.answer) <= 4 * last
        for model in ("blind", "bands"):
            results[(f, model)].append((b, P, numeric_depth(int(p.answer), last, p.difficulty, model == "bands"),
                                        None, day))
        continue
    else:
        continue
    if not sets:
        results[(f, "unparsed")].append((b, P, 0, None, day))
        continue
    cands = frozenset("".join(t) for t in product(*sets)) | {p.answer}
    for model in ("blind", "typo") + (("parts",) if f in ("lineage", "ancestral_compass") else ()):
        if (cands, model) not in cache:
            cache[(cands, model)] = depths(cands, model)
        results[(f, model)].append((b, P, cache[(cands, model)][p.answer], len(cands), day))

print("\nsearchers: answers named within each horizon (b, P, 2b, 2P, then each 24-hour cap;\n"
      "  below, 3 and 7 days at a cap of 12, and each puzzle's own day with no cap)")
for (f, model), rows in sorted(results.items()):
    hz = [("b", lambda r: r[0]), ("P", lambda r: r[1]), ("2b", lambda r: 2 * r[0]),
          ("2P", lambda r: 2 * r[1])] + [(f"C{c}", lambda r, c=c: c) for c in CAPS]
    within = ", ".join(f"<={name} {sum(r[2] <= h(r) for r in rows)}" for name, h in hz)
    dom = [r[3] for r in rows if r[3] is not None]
    extra = f"; domain median {statistics.median(dom)}" if dom else ""
    print(f"  {f:17s} {model:6s} n={len(rows)}: {within}{extra}")
    later = ", ".join(f"<={d} days at 12 {sum(r[2] <= 12 * d for r in rows)}" for d in DAYS)
    print(f"  {'':17s} {'':6s} {later}, <=own uncapped day {sum(r[2] <= r[4] for r in rows)}")

print("  numeric_pattern answers outside (last term, 4 x last term]:", outside)
words = {w.lower() for b in _WORD_BANKS.values() for w in b}
key = Counter("".join(sorted(w)) for w in words)
ana = Counter(key["".join(sorted(p.answer.lower()))] for _, p in built if puzzle_family(p) == "anagram")
print("\nanagrams by bank words sharing their letters:", dict(sorted(ana.items())))
beyond = 0                                # without a word list: log2(arrangements) / log2(bands)
for _, p in built:
    if puzzle_family(p) == "anagram":
        w = p.answer.lower()
        arrangements = factorial(len(w)) // prod(factorial(c) for c in Counter(w).values())
        beyond += log2(arrangements) / log2({1: 4, 2: 4, 3: 3, 4: 2}[p.difficulty]) > p.max_attempts
print("anagrams whose letter-arrangement bound exceeds b guesses:", beyond, "of", ana.total())
name_words = sorted({w for m in nodes for w in m.name.rsplit("-", 1)[0].lower().split()})
sub = Counter()
for _, p in built:
    if puzzle_family(p) in ("keeper_witness", "causal_augury") and not p.answer.isdigit():
        ws = p.answer.split()
        for i, w in enumerate(ws if len(ws) > 1 else []):
            for alt in name_words:
                if alt != w:
                    sub["all"] += 1
                    sub["near"] += typo_near(" ".join(ws[:i] + [alt] + ws[i + 1:]), p.answer)
print("phrase one-word substitutions the typo band reads very close:", sub["near"], "of", sub["all"])
```

### `model_m1.py` (observer model)

```python
"""Observer model: with P steady, can someone reading public rows (warned
flags, send-aways) tell which strike drew an excited (near-miss) warning?
The fold as ADR-036 D2 stated it at d716cc3; every guess in one window."""
from itertools import product


def fold(bands, P):
    rows, c, prev_warned, warned_since = [], 0, False, 0
    for band in bands:
        c += 1
        if c >= P and prev_warned:
            if band == "top" and warned_since < 2:
                rows.append(("warned", False, band)); warned_since += 1; prev_warned = True
            else:
                rows.append(("plain", True, band)); c, warned_since, prev_warned = 0, 0, False
        elif c >= P - 1:
            rows.append(("warned", False, band)); warned_since += 1; prev_warned = True
        else:
            rows.append(("plain", False, band)); prev_warned = False
    return rows


def observe(rows):
    """Flag a warned row that directly follows a warned row, with no send-away."""
    flags, prev = [], None
    for kind, sent, _ in rows:
        flags.append(kind == "warned" and prev == "warned")
        prev = None if sent else kind
    return flags


total = wrong = 0
per_p = {}
for P in range(2, 7):
    for L in range(1, 9):
        for bands in product(("top", "other"), repeat=L):
            rows = fold(bands, P)
            for flag, (_, _, band) in zip(observe(rows), rows):
                if flag:
                    total += 1; per_p[P] = per_p.get(P, 0) + 1
                    wrong += band != "top"
print("flagged rows", total, "per P", per_p, "flagged but not top band", wrong)
```

### `model_fold.py` (revised fold)

```python
"""ADR-036 D2 fold, as revised 2026-11-10: strikes in the window since the
last send-away; warning receipts; the near-miss reprieve limited by warned
rows from the last 24 hours; a 24-hour miss cap the window does not reset: a
miss at or past the (C-1)-th of the day is warned, the C-th after a warned
miss sends the player away, and any send-away lasts until at most C - 2 of
their judged misses lie in the last 24 hours. One player; times in minutes;
C = 4 here so that short sequences reach the cap.
Checks, over every sequence enumerated:
  A. every send-away directly follows a warned judged miss of the same player
  B. no 24-hour span holds more than C judged misses
  C. between two send-aways, no 24-hour span holds two excited warnings
"""
from itertools import product

W, DAY, FIRST, CAP_AWAY, C = 30, 1440, 5, 240, 4
RUNS = [  # (gaps in minutes, P fixed at 2, 3 or 4 up to this many guesses, P free 2-4 up to this many)
    ((0, 10, 35, 300, 1500), 6, 4),
    ((0, 1, 600, 840), 6, 0),
    ((0, 1, 300, 700, 1100, 1439, 1441), 5, 0),
]


def day_out(times):
    """Earliest return at which at most C - 2 of these misses lie in the last 24 hours."""
    i = len(times) - (C - 1)
    return times[i] + DAY if i >= 0 else -1


def run(steps):
    rows, sends, away_until, now = [], [], -1, 0     # rows: [time, warned, excited]
    for gap, band, P in steps:
        now += gap
        if now < away_until:
            continue                                  # refused: no row, not judged
        last_send = sends[-1][0] if sends else -1
        strikes = [r for r in rows if r[0] > now - W and r[0] > last_send]
        daily = [r for r in rows if r[0] > now - DAY]
        prev = rows[-1] if rows else None
        warned24 = sum(r[1] for r in rows if r[0] > max(now - DAY, last_send))
        k = sum(t > now - DAY for t, _ in sends)
        c, d = len(strikes) + 1, len(daily) + 1
        day_times = [r[0] for r in daily] + [now]
        prev_strike_warned = bool(strikes) and strikes[-1][1]
        prev_daily_warned = bool(daily) and daily[-1][1]
        if d >= C and prev_daily_warned:
            rows.append([now, False, False]); away_until = day_out(day_times)
            sends.append((now, prev)); continue
        if c >= P and prev_strike_warned:
            if band == "top" and warned24 < 2:
                rows.append([now, True, True]); continue
            rows.append([now, False, False])
            away_until = max(now + min(CAP_AWAY, FIRST * 3 ** k), day_out(day_times))
            sends.append((now, prev)); continue
        rows.append([now, c >= P - 1 or d >= C - 1, False])
    return rows, sends


bad = {"A": 0, "B": 0, "C": 0}
total = 0
for gaps, fixed_len, free_len in RUNS:
    configs = [(p, n) for p in (2, 3, 4) for n in range(1, fixed_len + 1)]
    configs += [(None, n) for n in range(1, free_len + 1)]
    for P_fixed, L in configs:
        choices = product(gaps, ("top", "other"), (2, 3, 4) if P_fixed is None else (P_fixed,))
        for steps in product(list(choices), repeat=L):
            total += 1
            rows, sends = run(steps)
            for t, prev in sends:                      # A: the receipt came first
                if prev is None or not prev[1]:
                    bad["A"] += 1
            times = [r[0] for r in rows]
            if any(sum(t - DAY < u <= t for u in times) > C for t in times):
                bad["B"] += 1
            bounds = [-1] + [t for t, _ in sends] + [10 ** 9]
            for lo, hi in zip(bounds, bounds[1:]):
                ex = [r[0] for r in rows if r[2] and lo < r[0] < hi]
                if any(sum(t - DAY < u <= t for u in ex) > 1 for t in ex):
                    bad["C"] += 1
print("sequences", total, "violations", bad)
```
