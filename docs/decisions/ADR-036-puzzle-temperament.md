# ADR-036: Puzzle temperament — moods, send-aways and warmth instead of a fixed attempt pool

**Status:** Proposed, 2026-11-07; revised 2026-11-10 after the owner-requested
review of `d716cc3`. **Owner:** Mark Weeks. Records the owner's puzzle
decisions of 2026-11-06 and 2026-11-07 and designs them against the code. Not
ratified; it writes no code, migration or write path and authorizes no
implementation, deployment or merge. Cited ranges were read at `f3ead74` and
are byte-identical at `3200eed` (#153), except `_history_block`, two lines
lower there; ranges first cited in the revision were read at `3200eed`.
Claims are *executed*, *read* or *inferred*; the searchers and fold models
behind D2 and D3 are defined, with their source, in the
[band-searcher record](../evaluation/2026-11-07-puzzle-band-searchers.md).
Not on `main`, so named, not linked: #156
(`docs/evaluation/2026-11-06-next-build.md`), #155 (`scripts/beta_metrics.py`
on `claude/pilot-measurement`, read at `8f8e969`) and ADR-037 (#160, Proposed,
`docs/decisions/ADR-037-agents-as-conversational-players.md` on
`claude/adr-037-agents-in-chat`, read at `4267eba`).

## Context

**The owner's decisions, verbatim.**

- 2026-11-06 ("5" is puzzle failure, packet decision 3, as #156 records it):

  > On 5, the puzzles themselves can have personalities of sorts. So if there
  > are too many failed attempts the puzzle may get annoyed and tell the player
  > to go away and leave it alone. Conversely, if a player's answer is close
  > then perhaps the puzzle get excited by the progress and encourages the
  > player to try again. Puzzle attempts and lock periods can be dynamic in
  > this way rather than fixed and static. On 5, I suggest that AI agents do
  > not solve puzzles independently. However, they can cooperate with human
  > players to help solve puzzles.

- 2026-11-07:

  > 1. an annoyed player generally gets grumpier toward all players, but especially the player(s) that are annoying it
  > 2. agents can suggest puzzle answers if a human engages with the agent and proposes collaboration. Agents do not submit puzzle answers
  > 3. puzzles can give subtle hints like "you're getting warmer" or "you're way off" in their voice and personality
  > 4. I don't understand the question
  > 5. I don't understand the question

  **Interpretation, awaiting the owner's confirmation** (open question 8):
  answer 1 says "an annoyed player"; this record reads it as an annoyed
  **puzzle**, the subject of the question, as ADR-037 (#160) does, and D2 is
  built on that reading. Answers 4 and 5 are not read as decisions, and the
  open questions below are rewritten in plain language.
- Decided 2026-11-06 and recorded in ADR-037 (#160) and #156: structural
  parity (option (b)) and the disclosure guardrails (a) to (d). Still open,
  and not decided here: S5 chat permanence; S2's open parts, L3 and L4 (the
  owner set S2's policy on 2026-11-07, D5); the E2 spend ceiling; and the
  watch date (on 2026-11-07 the owner chose an expedited test build on the
  staging twin, #156; its date waits on the Fly account, checklist F1).

**Supersedes in part, on ratification.**
[ADR-022](ADR-022-m4-responsive-inhabitants.md)'s puzzle-eligibility paragraph
(lines 49-51, "one deterministic difficulty-weighted attempt per current
renewal epoch"), implemented though marked Proposed, retires with D5; the
attention marker's `puzzle_epoch` column (line 81) stays, unwritten and
unread, with no migration. [ADR-032](ADR-032-inhabitant-cognition.md) D4
(lines 132-136, an inhabitant "attempts a puzzle by answering it") is contrary
to "do not solve puzzles independently" and needs revising before
ratification, as ADR-037 (#160) Context also says.

**Today** (*read* unless marked).

- One pooled session per node (`server/rooms.py:109-122`) counts every guess
  and claims the first correct one (`:330-358`), rehydrated from
  `PUZZLE_ATTEMPT` rows (`:152-174`, `persistence/__init__.py:1045-1062`). At
  `max_attempts` the handler fails the puzzle (`server/handlers.py:2114`),
  writes `PUZZLE_FAILED` (`:2143-2153`) and returns the answer (`:2169`), which
  both clients print (`static/explorer.js:960-961`,
  `frontend/src/components/Interact.jsx:258-259`). **F10, *executed* at
  `3200eed`** (seed 42, difficulty-3 root, pool 4): guesses 4 to 6 each
  returned the answer and wrote `PUZZLE_FAILED`; a player who had never
  guessed then solved with it.
- The cast attempts puzzles by dice (`server/heartbeat.py:393-394`, `:481-490`;
  `agents/agent.py:23-26`, `:71-98`, `:113-123`; the CLI bus is wired to the
  chronicle, `interface/__init__.py:160-163`). Solve state skips rows carrying
  `agent` (`persistence/__init__.py:662-690`), but `_maybe_rearm` counts every
  `PUZZLE_SOLVED` (`causality/wiring.py:54-69`) and a solve stabilizes only an
  unstabilized node (`multiverse/effects.py:69-73`): an ambient roll takes
  the stabilizing half of a later human's reward (#156, finding 4; D4).
- Difficulty is `sha256("difficulty:{level}:{name}")`
  (`puzzles/generators.py:65-75`) and sets attempts 3, 4, 4, 5 (`:62`), pinned
  at first use per epoch (`puzzles/instances.py:46-69`,
  `persistence/puzzle_content.py:13-19`); the epoch counts `PUZZLE_REARM` rows
  (`persistence/__init__.py:1025-1041`). Era names are the frozen read-time
  precedent (`multiverse/chronicle.py:17-21`,
  `tests/test_continuity_freeze.py:254-261`); the Augury's `_LAW_TEMPERAMENT`
  (`puzzles/generators.py:959-985`) is unrelated.
- A wrong guess's text is stored only when moderation allows it, clipped to 32
  characters (`server/handlers.py:2061-2077`, `server/moderation.py:244-253`;
  the screen fails closed when disabled, capped or erroring, `:179-205`);
  redaction overwrites it (`persistence/__init__.py:917`). `/history` and
  `/chronicle` serve row data raw (`server/handlers.py:961-993`); no client
  renders it (grep).

**Census, *executed*** on the unborn seed-382 world (4,208 puzzles, epoch 0):
2-3 word phrases 26.1% (keeper_witness 839, augury names 261); 3-4 letter
marks 26.8% (ancestral_compass 828, lineage 301); words 21.4% (anagram 496,
cipher 405); categorical readings 9.2% (bond 247, sealed_lock 140); integers
15.3% (numeric_pattern 499, augury reach 135, enfold 10); hand-written
riddles 47, two with integer answers. Counts only: under the answer-secrecy
covenant this record states no answer, range or excerpt.

## Decision

Everything below, numbers and structure, is a recommendation the owner can
veto; only the quoted decisions above are the owner's.

### D1. Temperament: a frozen trait of the node, like difficulty

Each puzzle's temperament is
`("patient", "proud", "prickly", "playful")[sha256("temperament:{level}:{name}").digest()[0] % 4]`:
its own keyed domain, ignoring the epoch, so a renewed puzzle keeps its temper
as it keeps its difficulty (`puzzles/generators.py:1139`). *Executed* on seed
382: 24.6% to 25.2% each, 241 to 282 in every temperament × difficulty cell.
It sets tone and patience, never name, prompt, answer, hints or difficulty.

| Temperament (never shown) | Patience `t` | Strikes forgiven after | First send-away | Sample warm line | Sample send-away line |
|---|---|---|---|---|---|
| patient | +1 | 20 min | 3 min | "Closer. Breathe, and try again." | "Let us both rest. Come back when the light has turned." |
| proud | 0 | 30 min | 5 min | "Ha! You nearly had me." | "Enough. I will not be guessed at. Leave me be." |
| prickly | −1 | 45 min | 8 min | "Hm. Not wrong in every way." | "Go away. Leave me alone." |
| playful | 0 | 30 min | 5 min | "Ooh, you're getting warmer!" | "I'm bored of you now. Go and play somewhere else for a while." |

**Freeze, do not materialize.** Read at use like era names, the draw would
give every puzzle a new temper if the tuple or its order changed, so a new
class in `tests/test_continuity_freeze.py` pins both and the temperament of
fixed reference nodes (a new pin, not a re-pin). Numbers and lines stay
tunable. The pinned definition (`puzzle_instances`, which holds
`max_attempts`) could store it with no migration, protecting later epochs.
Not now: earlier epochs still fall back to the draw, so the freeze is needed
anyway, and the decoder builds `Puzzle(**data)` and refuses any
`definition_version` but 1 (`puzzles/instances.py:13-21`,
`puzzles/types.py:27-40`), so a new key or version strands those puzzles after
a same-schema rollback (#152) to an earlier binary (*inferred*).

### D2. Mood: grumpier toward everyone, sending away whoever annoys it

- **Base patience** `b` is the pinned `max_attempts`; `t` the offset above.
- **Load** (everyone): human wrong guesses at the current puzzle in the last
  60 minutes, at most `b` counted per player; rows carrying `agent` never
  count. Calm below `2b`, testy from `2b`, grumpy from `4b`: `g` = 0, 1 or 2.
  Mood sharpens every line and doubles a grumpy puzzle's send-aways: that is
  "grumpier toward all players". The per-player cap means one player failing
  a lot annoys the puzzle at them, not at everyone.
- **Strikes** (per player): every wrong guess of theirs here, within the
  temperament's window, since their last send-away ended. Patience
  `P = max(2, b + t − g)` is read at each guess.
- **Daily cap** (per player, per puzzle; proposed `C = 12`, open question 7).
  Patience limits a burst, not a day: strikes count only inside the window,
  so a player keeping to `P − 2` misses a window is never warned (up to 288
  misses a day, patient at `b = 5`) and one keeping to `P − 1` is warned but
  never sent away (up to 360), while a lone player's own load never makes the
  puzzle testy (*executed* day model). So no player has more than `C` judged
  misses at a puzzle in any 24 hours by `recorded_at`, and neither the window,
  forgiveness nor a send-away ending resets the count. To hold that, every
  send-away also lasts until at most `C − 2` of the player's judged misses
  here lie in the last 24 hours (after the `C`-th miss, until the
  second-oldest is a day old), so the next time they reach the cap, the miss
  before it is a warned `(C − 1)`-th. Ending it once only the oldest is a day
  old would not: the returning player's next miss would be the `C`-th but
  follow the unwarned send-away, so it would only be warned, and the one
  after it would be the `(C + 1)`-th (*executed* model at `C = 4`: 19,456 of
  898,776 sequences). The band-searcher record proves the bound for this
  rule and models it. The cap bounds one player's day, not a campaign (D3).
  `C = 12` is twice the largest calm patience (6), so every temperament
  allows a full window, a send-away and a second window first; of 8, 12, 16
  and 24 it is the largest at which the one measured band that beats blind
  search, lineage's, meets D3's bar.
- **Warning, then send-away.** A strike at or past `P − 1`, or a miss at or
  past the `(C − 1)`-th of the day, that does not send the player away is
  warned, and its row records `"warned": true`. A miss sends the player away
  when, and only when, their previous judged miss here carries `warned` and
  this miss's strike count reaches `P` or its daily count reaches `C`; the near-miss
  reprieve below is the one exception, and it never defers the cap. The fold
  reads these receipts and never recomputes a warning, so one always comes
  first, even when others' failures or a retune of `t`, a window or a mood
  threshold lower `P` between guesses. A patience send-away bars this puzzle
  only, for `first × 3^k` (`k` = their send-aways here in 24 hours), doubled
  while grumpy, capped at 4 hours unless the cap's rule above holds it
  longer, and a daily-cap send-away as above; guesses meanwhile are neither
  judged nor stored. Anyone else can still solve; a
  sent-away contributor is credited. Difficulty already sets `b`; longer
  send-aways for hard puzzles would make the hardest the harshest, against
  "Fair, never a wall" (`puzzles/generators.py:12-15`).
- **Excitement** (batch 3, whatever open question 6 decides). Every wrong
  guess is a strike, and the band (D3) of the guess being judged picks its
  line: a near miss, in a family that has a band, hears an excited or warm
  line in the puzzle's voice (D1's warm column), a far one a cooler line.
  This is the owner's decision; only the reprieve below is conditional.
- **Near-miss reprieve** (batch 3, and only once wrong-guess text is no
  longer stored). A top-band guess that patience, never the daily cap, would
  send away gets an excited warning instead ("Oh! So close. Try me once
  more.") unless two `warned` rows from the last 24 hours already follow the
  player's last send-away. Closeness buys at most one guess beyond patience
  in any 24 hours (a player who stops after a reprieve and returns more than a
  day later, with no send-away between, can earn another), and the fold never needs an earlier guess's band, which is
  not stored, nor reliably its text (*executed* 2026-11-07T05:25:57Z: one
  one-edit miss stored no `guess` with moderation disabled and a stored
  excerpt with it on). The reprieve is public all the same: its row carries
  `warned` like any warning's, but `b`, the published draw, loads, strikes
  and receipts are all served, so anyone can rerun the fold, and with `P`
  steady a warned row right after a warned row, with no send-away between,
  marks a near miss (*executed* model, every band sequence of up to eight
  guesses at `P` 2 to 6: 1,934 such rows, all top band). It therefore ships
  only with the end of stored wrong-guess text (open question 6), so it can
  say that a player came close, never which stored excerpt did; if the owner
  keeps that text, the reprieve is dropped.

**Fairness, revised.** "Harder puzzles get MORE attempts" (same comment) holds
within a temperament and mood: for fixed `t` and `g`, `P` never falls as
difficulty rises. Across temperaments it does not: prickly at difficulty 2 (3)
is less patient than patient at 1 (4). `test_attempts_track_puzzle_difficulty`
(`tests/test_puzzles.py:315-324`) reads `max_attempts`, which is `b`, so it
stays green without checking patience; batch 3 adds a test of the revised
invariant and rewords the comment.

**Only the player annoying it is sent away.** Answer 1 says "especially", not
"only": "grumpier toward all" is read as shorter patience, sharper lines and
longer send-aways for everyone, and the send-away as the annoyer's alone. A
puzzle-wide lockout would let one player's guessing decide everyone's access
and hold a sealed Room shut, breaking "every player owns their actions" and
arming griefers; here a griefer sends only themselves away. The seal never
imprisons (`puzzles/gates.py:81-82`): a send-away bars guesses, not movement.

**The clock** is the database's: `recorded_at` (`datetime('now')`,
`persistence/migrations/0001_initial.sql:39`) against `datetime('now')`. The
fold, a pure `(rows, now) → mood, strikes, daily count, away_until`, runs in
`will_store_guess` (`server/rooms.py:264-283`), which then returns false for
an away player so no screen or classify call is spent, and authoritatively in
`puzzle_attempt`'s writer transaction (`:286-311`) before `record_attempt`
claims a solver, so a right answer while away is not accepted and two quick
guesses cannot both slip under a limit. A send-away's `PUZZLE_FAILED` commits
in that transaction with its triggering attempt: today's append
(`server/handlers.py:2143-2153`) runs after the commit, outside the room lock
(*executed*), so another guess could be judged first or a crash lose it.
**Lock expiry is not puzzle selection:** which puzzle a node serves stays a
pure function of `(node, epoch)` and pinned rows; time decides only whether a
guess is heard and which line answers, as the rate limiter (`server/guard.py`
`RateLimiter`) and sanction expiry (`persistence/sanctions.py`) do. Lines are
chosen by a hash of node, puzzle, actor and attempt ordinal, never entropy;
moods are responses, not state, so Wayback shows none
([ADR-011](ADR-011-wayback-surface.md)).

### D3. Warmth: whole-answer bands in the puzzle's voice

The judge returns a band and an authored line, never a direction, position,
letter or count of right parts. Every metric reads the whole answer after the
correctness check's normalization (`server/handlers.py:2030`, `:2047`).
Per-part metrics are Mastermind: *executed*, a searcher told how many compass
marks are right names 490 of 828 answers within `b` guesses, 800 within `2b`
and all 828 within the daily cap `C = 12`. Every count below is "named within
`b` guesses" unless it names another horizon; `b` is what the earlier
"first window" meant.

| Family | Band | Why (*executed*, seed-382 census) |
|---|---|---|
| anagram, cipher | edit distance: *way off*, *cold*, *warm*, *very close* at difficulty 1-2; 3 folds way off into cold; 4 says only *not close* or *close* | A word list, not the band, is what a searcher needs: 485 of 496 anagrams have one bank word with their letters (11 have two), and a cipher has 3 to 9 shifts, all inside `C`. The letter-permutation bound (458 of 496 beyond `b` guesses) holds only without a word list |
| keeper_witness, augury names, lineage, bond, sealed_lock, word riddles | typo band only | A wrong word reads far: 4,976 of 493,536 one-word substitutions (1.0%) read very close. On lineage (910 candidates) a searcher using the band names 1 of 301 within `b`, 12 within `2b` and 54 within `C`, where blind search names 0; on bond and sealed_lock it names no more than blind search at any horizon |
| ancestral_compass | none: "not it" in voice | Small domains (median 56): blind enumeration names 137 of 828 within `b` and 303 within `C`; the typo band would raise those to 279 and 602 |
| numeric_pattern, enfold, augury reach, integer riddles | none: "not it" in voice | Four directionless magnitude bands made numeric_pattern a search (268 of 499 within `b`, 493 within `C`, against 45 and 272 blind), and no narrower integer band was measured; enfold and augury reach answer with a small count of scales or a child's position (*read*, `puzzles/generators.py:827-829`, `:1041`), and only two hand-written riddles have integer answers |

The typo band reads *very close* (*close* at difficulty 4) for one edit or
under 15% normalized distance. A band still discloses something: a near miss
says the answer is one edit away, and later bands narrow where. **The horizon
is a day, not a window**: the bound must hold over 24 hours of paced
guessing, which the daily cap (D2) limits to `C` judged misses per player.
**Pass bar** (proposed, vetoable): a family keeps a band only if, within `C`
guesses, the band lets the searcher name at most a fifth of the family's
answers more than blind enumeration names. At `C = 12`: lineage +54 of 301
(17.9%) and bond and sealed_lock +0 pass; the typo band on compass marks
(+299 of 828, 36.1%) and magnitude bands on numeric_pattern (+221 of 499,
44.3%) fail, which is why neither has one. Anagram and cipher bands add
nothing a word list or shift list does not. The phrase families
(keeper_witness, augury names, word riddles) have only the substitution
bound so far; batch 3 writes their searcher and applies the bar before they
keep a band.

**The cap bounds a day, not a campaign.** An unsolved puzzle stays the same
puzzle (D4, open question 1), so a player who comes back on `n` days, or `n`
players who pool what they hear, reach the `nC` horizon. At `C = 12`,
lineage's band names 153 of 301 answers in two days and 235 in three,
against 8 and 13 blind, and all 301 within a week, against 28: the cap slows
that search but does not stop it. The bar is a bar on one player's day, and
keeping lineage's band on it is a default the owner can veto under open
question 7 if warmth should never add up to an answer, however long the
search. If the owner declines the cap, a lone player's day at a lineage
puzzle without it (the day model's most, 32 to 360 misses by temperament and
`b`) lets the band name 292 of 301 against 46 blind, so lineage loses its
band; bond and sealed_lock add nothing at any horizon measured and keep
theirs (*executed*, band-searcher record).

The searchers are generous: they know each reading's bank and minimize the
worst case. The
[band-searcher record](../evaluation/2026-11-07-puzzle-band-searchers.md)
defines each searcher, horizon and band edge, gives the source and every
count, and is what batch 3's test re-runs.

**Wrong-guess text stops being public** (open question 6), and the near-miss
reprieve (D2) waits on it. Under warmth a stored excerpt is each player's path
to the answer, near misses included, and anyone can fetch it. New
`PUZZLE_ATTEMPT` and `PUZZLE_FAILED` rows stop storing
`guess` and `answer_given` (`server/handlers.py:2071-2073`, `:2146-2148`): an
existing call site writing less, old rows unchanged and still redactable, and
one fewer moderation screen per wrong guess. Separate from S5, still open.
Hints keep their content; each player climbs the ladder with their own wrong
guesses and the last rung repeats, where today's pooled index
(`server/handlers.py:2115-2118`) leaves a newcomer no hint once the room has
spent it.

### D4. No failure state, so no failure renewal

A puzzle is open or solved: `correct_answer` and `FAILED` leave every
response, closing F10; the answer goes first, in a release of its own
(D8, batch 1a). Packet option 3(b) re-armed failed puzzles through
decay, which stops once decay has disturbed and fractured a Room (#156,
finding 2); a puzzle that never fails for everyone needs no failure re-arm,
and an unsolved sealed Room stays sealed to outsiders until a human solves it.
Renewal after a solve keeps today's path and the epoch stays the
`PUZZLE_REARM` count, but "solves exceed re-arms" (`causality/wiring.py:64-66`)
becomes "the current epoch's puzzle has a human solve"
(`persistence.get_puzzle_solve`), which old ambient rows cannot satisfy. A
solve sets `stabilized` (`multiverse/effects.py:69-71`) and the next
`DANGER_ALERT` clears it (`:81-83`), so a solved Room can always renew (*read*;
#156 executed this). A renewed puzzle's new name starts its moods clean.
**Accepted, not fixed:** a solve sets `stabilized` only when it is unset, so
where an ambient solve already stabilized a node (its origin effect sets
`stabilized` when the event is emitted, before any staged hop,
`server/heartbeat.py:222-230`), a later human solve there does not set it
until a `DANGER_ALERT` clears it; it still lowers danger where danger can
fall, on a Region (`danger_level` 1 to 10, `multiverse/generator.py:328`)
above the minimum (`multiverse/effects.py:69-73`). *Executed* on seed 42:
after the heartbeat's ambient `PUZZLE_SOLVED`, a human HTTP solve at the
root, which has no danger, returned `changed: None` (without it,
`{"stabilized": True}`), and at a Region born at danger 4 it returned only a
lower `danger_level` (without it, `stabilized` and a lower danger). A world
first booted after batch 2 holds no ambient solves; changing the solve effect
for older worlds would be a causal change of its own.

### D5. Agents help when asked, never attempt, never see the answer

- **No ambient attempts.** The heartbeat's puzzle opportunity and the dice
  go; `Agent._act` treats a puzzle node as any interactive node
  (`agents/agent.py:124-126`).
- **Help only on a human's proposal**, by ADR-037 (#160) D7's trigger, which
  that record owns: a line addressing an agent at a place with an open
  puzzle, with a help or solve verb aimed at the puzzle by a fixed local
  pattern, for that player, agent and epoch. This record requires that it hold the same with AI
  on or off, that puzzle context reach a model only after it fires, and that
  no other player's words open one, chat quoted in the agent prompt's node
  history included (`consciousness/__init__.py:829-877`). The pattern alone
  opens a collaboration, with AI on as with it off; no model judges whether
  help was asked for. The agent may then discuss the puzzle and
  offer a guess as its own. It never submits: no server path gives an
  agent identity an attempt, and server identities are reserved names
  (`server/handlers.py:174-181`). With AI off it defers, willing and asking
  for nothing ("Gladly — though nothing comes to me today. It is yours to
  try.").
- **Agents never see the answer**, only what that player can read (`/puzzle`,
  their unlocked hints, `/puzzle/evidence`, the place as `/world` serves it)
  and what the human says. Puzzles left node properties because a voice could
  be asked to reveal them (`puzzles/engine.py:45-50`); an agent holding the
  answer would hand it to anyone and invite prompt injection, while from the
  same clues it is a peer whose guesses can be wrong. The AI-on path sends a
  player's words to a provider, so it waits on E2 and on S2's open parts: the
  owner set S2's policy on 2026-11-07 ("Information can only be shared with
  model providers to facilitate game play. Enfolded data must not be used to
  train frontier models.", recorded by #156), and naming the destinations
  (L3) and checking their terms (L4) stay open. An AI-on help line is
  model-written shared text: ADR-037 (#160) D6 passes it through the human
  line's screen, failing closed
  ([ADR-004](ADR-004-day-one-data-policy.md) §2), so a hold or block means no
  line and no row, and this record requires that whatever ADR-037's final
  wording.
- **Credit stays human.** Contributors are the humans who guessed; the solve
  row names who submitted. A helping agent is in neither: its help lives in
  the conversation (subject to S5) and the agent's short conversation buffer
  (ADR-037 (#160) D8), never `agent_memory`, and nothing labels a solve
  AI-assisted, without labelling who is human. The covenant then reads:
  agents never solve, and a human's solve is theirs even with an agent's
  help. The stored `agent` key and its exclusions stay.

### D6. What is stored, and the doors implementation trips

No new table or row kind; two new keys, `warned` and `away_s`, on existing
rows, which `/history` and `/chronicle` serve raw and the chronicle keeps.
Moods fold from mechanical fields, so moderation cannot change a count: wrong
`PUZZLE_ATTEMPT` rows at the current puzzle name (it carries the epoch) by
the player's identities (`persistence/participants.py:100-109`; display name
when keyless), their
`recorded_at` and `warned`, and the player's `PUZZLE_FAILED` rows carrying
`away_s`; redaction keeps these (`persistence/__init__.py:917`). Changed write
paths, each an existing call site: no `PUZZLE_ATTEMPT` for a guess refused
while away (`server/handlers.py:2074-2077`); `warned` on a warned strike's row;
`PUZZLE_FAILED` once per send-away as `{"puzzle", "contributors", "away_s"}`,
in the attempt's transaction (D2), not on every guess after a pool fails
(`:2143-2153`); no `guess` or `answer_given` in new rows, if open question 6
agrees; no ambient `PUZZLE_*` rows (`server/heartbeat.py:486-487`,
`agents/agent.py:122-123`); the CLI judged the same way, not printing the
answer (`interface/__init__.py:198-201`, `puzzles/engine.py:110`); the
restated `PUZZLE_REARM` trigger (`causality/wiring.py:66-69`).

The fold counts only `PUZZLE_FAILED` rows with `away_s` and no `agent`,
keeps each stored length and reads warnings only from `warned`, so a retune
never alters a running send-away or skips a warning, and legacy pool or
ambient rows never read as send-aways. From batch 1b a `PUZZLE_FAILED` means
"someone was sent away", not "the pool failed", and batch 1b settles each
other reader: art (`server/imageprompt.py:96`, two rows make a place
"oppressive") keeps the new meaning, since a puzzle that has sent travelers
away twice is tense, and one player can already write two rows today with
`b + 1` guesses; narration (`multiverse/history.py:77`, "a resisted puzzle")
names only cascaded arrivals, which only ambient rows produce
(`server/heartbeat.py:486-487`, `agents/agent.py:122-123`), so its legacy
text stands; the feed (`static/clientlogic.js:259`, "a puzzle resisted
{who}") keeps the new meaning, true of a send-away; and #155's
`scripts/beta_metrics.py` reads `away_s`, because its `failed_pools` (the
first `PUZZLE_FAILED` per seed, node and epoch) would count epochs with at
least one send-away and its `puzzle_failed_rows` every send-away, so it
reports send-aways apart from legacy pool failures for C2c.

Doors at implementation: those write paths (owner sign-off at merge); the
rollback floor (D8: once batch 1b has run, an image from before batch 1a
releases answers when rolled back to); the pool and ambient-attempt promises
in the guide (`static/guide.html:62`, `:114`, `:121-122`, `:146-147`),
`docs/design/game-design.md:125` and the
agent bible ("You attempt puzzles under the same rules as any traveler",
`consciousness/__init__.py:515-518`); AGENTS.md's agent-solve covenant; and a
new frozen read-time surface, the temperament draw, listed beside era names in
AGENTS.md, the irreversibility skill and the PR template, which change
together. No migration, golden re-pin, or change to `build_puzzle` or
`puzzle_instances`.

### D7. Surfaces: the existing result line speaks

The voice replaces "Wrong.", "N attempts left" and the answer release in the
existing result line, `#puzzle-result` (`static/explorer.js:912`, `:950-971`)
and `/app`'s result block (`frontend/src/components/Interact.jsx:247-266`),
with no new pane, meter or counter. A send-away is HTTP 200 with
`result: "AWAY"`, the line and `away_for_s`, never a 4xx, as both clients
render `error` verbatim; the input re-opens when time passes, and
`GET /puzzle` reports the reader's away state as it reports `solved`
(`server/handlers.py:1889-1896`). About 100 authored lines (temperament ×
band, warning, send-away, still-away, solved; calm and grumpy) cover every
case, each band line taking its scale's own image of distance, written once
per scale ("light-years off" in a Galaxy, "a shell away" in an Atom), as scale
sets a puzzle's flavour. The judge calls no model and counts no moderated
text: AI on and off behave the same.

Guide copy (proposed), changed by the batch that makes the old words false.
The Solve row (`static/guide.html:62`) becomes, in batch 1b, "Crack a node's
puzzle. Keep missing and it may send you away for a while. One correct answer
counts for everyone who tried."; batch 3, which brings tempers and warmth,
makes it "Crack a node's puzzle. Each one has a temper: it may tell you
you're getting warmer, or send you away for a while if you keep missing. One
correct answer counts for everyone who tried." Batch 1b drops "co-op attempts
already pool, so" (`:146-147`). ADR-037 (#160) D5(b) rewrites and owns "You
are not alone" (`:108-122`) in its batch 2, and this record supplies its
puzzle sentences, changed in place before that: batch 1b turns `:121-122`
into "Solving is better together: a puzzle that is tired of you will still
hear a friend.", and batch 2 drops `:114`'s "attempt puzzles under the same
rules you play by"; ADR-037's rewrite keeps both.

### D8. Batches, in order

Batches 1 and 2 open write-path doors and should land before the first
production boot (#156, finding 1). Batch 1 ships as two releases, 1a then 1b.

- **1a. No answer release, alone** (its own release; the pool, `FAILED` and
  every write path unchanged): `correct_answer` leaves every response, the
  CLI stops printing the answer (`puzzles/engine.py:110`) and both
  clients' failure line drops it. It is the first half of packet option (c),
  shipped as a rollback floor, not as the design. **Why first:** batch 1b adds
  no migration, so `scripts/deploy.sh --rollback` accepts any image on the
  live schema (`scripts/deploy.sh:337-356`), and an image from before 1a
  rebuilds the pool from every `PUZZLE_ATTEMPT` row
  (`persistence/__init__.py:1045-1062`), fails at `max_attempts`
  (`server/handlers.py:2114`) and returns the answer (`:2169`). *Executed*
  against today's handler (seed 42 root, `b = 4`): one HTTP miss, three
  misses stored as batch 1b stores other players', a restart, then a
  newcomer's first wrong guess returned `FAILED`, attempt 5 and the answer,
  and wrote a `PUZZLE_FAILED`. Rolled back from 1b to 1a, a puzzle past its
  pool says `FAILED` without the answer, and its unmarked `PUZZLE_FAILED`
  rows are ones the fold ignores (D6). Once 1b has run, no image from before
  1a is a rollback target, and 1b says so in the runbook's "Same-schema
  release rollback" (`docs/infrastructure/fly-deployment.md`); best, 1a
  reaches production before its first boot, so no production image ever
  releases an answer. Tests: invert `tests/test_server.py:272-281` (a failed
  pool returns no answer); stored misses from several players past the pool
  give a newcomer `FAILED` and no answer.
- **1b. Per-player send-aways** (one flat temperament): fold, handler (both
  away checks), `warned` receipts, the daily cap, marked `PUZZLE_FAILED` in
  the attempt's transaction, `FAILED` gone from responses, `GET /puzzle` away
  state, both clients, the guide's Solve row (interim copy, D7), pool
  sentence (`:121-122`) and constellation line,
  `docs/design/game-design.md:125`, the other
  `PUZZLE_FAILED` readers (D6) and the runbook's rollback floor. Tests: no
  `FAILED` (replacing 1a's); fold (window, floor, a warning before every
  send-away even when `P` drops, never more than `C` judged misses in 24
  hours and no reset of that count by forgiveness or a send-away ending, a
  guess after the cap's send-away refused while only the oldest counted miss
  is a day old (the model's failing case), escalation, grumpy factor, cap,
  per-player load cap, a zero-strike player never sent away after 50 others
  fail, unmarked rows ignored, a retune across
  a restart neither alters a running send-away nor reads an unwarned strike as
  warned); HTTP (away is 200; a guess while away makes no moderation call,
  writes no row and reveals nothing; a right answer while away is refused;
  another player solves; equal strikes with moderation disabled; of two
  concurrent sending strikes one sends away and one is refused; a
  transaction rollback keeps neither row; moods survive a restart as in
  `tests/test_server_rooms.py`); Vitest and Playwright.
- **2. Agents stop attempting; renewal on a human solve**: heartbeat,
  `Agent._act`, CLI, `_maybe_rearm`, the guide's "attempt puzzles" clause
  (`:114`), the bible's "You attempt puzzles" sentence, AGENTS.md. Tests: no
  `PUZZLE_*` from a tick, replacing the tests that expect ambient attempts
  (`tests/test_agent_attention.py:159`, one attempt at `:170` and `:175`;
  `:184`; `:394`; `tests/test_m4_review.py:128`, two); an old ambient solve
  does not re-arm (the lost `stabilized` is D4's accepted exception); epoch equals
  the `PUZZLE_REARM` count, with `tests/test_game_depth.py:136` rewritten to
  solve the node's current puzzle (`build_puzzle(node, epoch).name`), not the
  placeholder name "P", which the restated trigger rightly ignores (*executed*:
  with `_maybe_rearm` restated as D4 says, `tests/test_game_depth.py -k
  Renewal` gave 1 failed, 2 passed); a scratch soak records the danger spread
  before and after.
- **3. Temperaments, voice bank, warmth, per-player hints**, whatever open
  question 6 decides; the end of stored wrong-guess text if it agrees, and the
  near-miss reprieve only with that end. Tests: secrecy in
  `tests/test_puzzles.py` over every line and band on the seed-382 census; no
  band for integers or compass marks;
  equally distant guesses get one band whichever part differs; the searcher
  bounds at the 24-hour horizon (the
  [band-searcher record](../evaluation/2026-11-07-puzzle-band-searchers.md)'s
  searchers, plus the phrase searcher this batch writes, meet D3's pass bar
  within `C`); the reprieve (top band only; by patience, never the cap; at most
  once in any 24 hours; warned rows older than 24 hours not counted, so a
  player warned twice last week keeps it, as a newcomer does); the draw pin; patience
  never falls with difficulty for fixed `t` and `g`; the Solve row's warmth
  clause.
- **4. Agent collaboration**, shared with ADR-037 (#160)'s batch 4: its
  trigger, the public puzzle view in agent context only after it, the AI-off
  line, no agent prompt holding the answer, the bible's "never reveal an
  answer" sentence rewritten with ADR-037. Needs ADR-037 for chat, S2 and E2
  for AI on.

## Open questions for the owner (each changes the design)

1. *Should a puzzle nobody has solved ever turn into a new puzzle by itself?*
   Recommended: no; it stays the same puzzle until someone solves it.
2. *How long can the longest "go away" for running out of patience last?*
   Recommended: four hours, and a puzzle forgets a player's send-aways after a
   day. (The daily limit in question 7 can keep someone away longer.)
3. *Does each player climb their own hint ladder, or do everyone's wrong
   guesses unlock hints for whoever guesses next, as today?* Recommended:
   each player's own, so a newcomer is never left with nothing.
4. *Should an agent that helped appear in the solve credit, as "with
   Tessera"?* Recommended: no; credit stays with the humans who guessed.
5. *Should "go away" say roughly when to come back?* Recommended: yes, in the
   puzzle's voice, and the answer box re-opens by itself.
6. *Should other players be able to read your wrong guesses?* The world's
   history keeps a short excerpt of each one that passes moderation, which
   anyone can fetch, though no screen shows it; once puzzles say "warmer", a
   near miss there is most of the answer. Recommended: no; new records keep
   only whether a guess was right. The "so close, try once more" reprieve
   ships only if the answer is no: anyone could otherwise tell which stored
   guess was nearly right.
7. *Should a puzzle stop listening to one player, for up to a day, once
   they have made twelve wrong guesses at it in 24 hours, even if they space
   them out?* Without a daily limit, someone who paces their guesses is
   never sent away and can try hundreds of answers a day, which turns
   "warmer" into a search, and lineage puzzles would lose "warmer" (D3).
   With it, a determined player can be kept away for most of a day, much
   longer than question 2's four hours, though a friend can still try. The
   limit slows a search but does not end it: someone who comes back day
   after day, or friends who share what they hear, can still work out a
   lineage answer from "warmer" within a week. Recommended: yes, twelve a
   day per player per puzzle, and lineage puzzles keep "warmer"; if warmth
   should never add up to an answer, however slowly, they lose it.
8. *When you wrote "an annoyed player generally gets grumpier toward all
   players", did you mean an annoyed puzzle?* This record assumes so (as does
   ADR-037), and its moods are built on that reading. Recommended: confirm.

## Trade-offs accepted

- Patience differs by up to two guesses between equally difficult puzzles,
  and a prickly hard puzzle can be less patient than a patient easy one; the
  1-4 rating keeps meaning how hard a puzzle is to think through.
- The same guess can meet a different line an hour later; a puzzle can stay
  unsolved indefinitely; numbers and compass marks get no warmth; a near miss
  narrows the rest of the search; one pool becomes one mood and one solve.
- Ambient solves were staged cascades that stabilize places and lower danger
  (`server/heartbeat.py:222-230`, `:486-487`; `multiverse/effects.py:69-73`).
  Without them the four admission slots a tick (`server/heartbeat.py:444-446`)
  go to persona actions, destabilizers included: the world may drift toward
  danger (*inferred*).
- Once agents stop writing `PUZZLE_*` rows, anyone named in a new one is
  human: kind becomes inferable from row patterns, as ADR-037 (#160)
  Trade-offs accepts.
- The daily cap can keep a determined player away for most of a day; a
  burst still meets minutes.
- The daily cap bounds one player's day, not a campaign: a player who
  returns on later days, or friends who pool what they hear, still narrow a
  lineage answer, all 301 within a week at twelve a day (D3).
- The near-miss reprieve can be read from public rows; it is accepted only
  once those rows hold no guess text.
- Once batch 1b has run, batch 1a's image is the rollback floor; rolling
  back further releases answers.
- On worlds where ambient solves ran, a human's solve at a node an ambient
  solve already stabilized loses the stabilizing half of its reward until the
  next disturbance, and still lowers danger where danger can fall (D4).
- From the first production deploy, changing who is prickly needs an ADR.

## Revisit when

- The pilot (C2c) shows a family's solve rate outside the proposed 40-85%,
  testers call send-aways punitive or meet the daily cap in ordinary play,
  or warmth trivializes a family, including a phrase family once batch 3's
  searcher measures it against D3's bar.
- After batch 2 the share of places above the soak's median danger rises:
  give the freed admission slots to tenders' scale verbs.
- Temperaments must change for existing puzzles or evolve with history
  ([ADR-029](ADR-029-evolution-grammar.md)): store them in the pinned
  definition, with a decoder earlier binaries can read.
- The world leaves its single SQLite writer, which changes the clock.
- ADR-037 or ADR-032 lets agents act on stage (may one volunteer help
  unasked?), or ADR-022 or ADR-032 is revised (their puzzle paragraphs follow
  this record).

## Rejected alternatives

- **Fixed pools** (today, and packet option (a)): release the answer (F10)
  or close the puzzle for everyone; static. **Option (c)**, stop releasing
  the answer and keep accepting attempts: a static pool that still counts
  failures and gives no feedback, and "failure no longer ends anything" (the
  packet's own cost); this record keeps (c)'s open puzzle, adds moods,
  warmth and per-player send-aways, and ships (c)'s first half alone only as
  batch 1a's rollback floor. **Per-player pools only** (d): no shared mood,
  so not answer 1, and a pool still ends in release or close.
- **Patience without a daily cap**: it bounds a burst, not a day (D2).
- **A schema-marker migration in batch 1b**, so that `--rollback` refuses
  every older image: it turns any rollback of 1b into a restore that abandons
  history; batch 1a's release gives the floor without one.
- **Option 3(b)**, fail then re-arm through decay: cannot keep renewing a
  failed Room (#156, finding 2); superseded by the owner.
- **Puzzle-wide lockouts**: one player's guesses decide everyone's access.
- **A model deciding lockouts, writing the voice, or judging whether help was
  asked for**: a cost per guess, nondeterministic, different with AI off,
  steerable by quoted chat; a model holding the answer can leak it.
- **Per-part warmth** (words or marks right): measured as Mastermind.
  **Magnitude warmth on numbers**: measured to make them a search.
- **A stored near-miss flag** forgiving a strike later: rows are served raw,
  so it needs a new table and a migration.
- **Agents that see the answer, or submit behind a confirm button**: answer
  delivery, and an agent-originated action.
- **Materializing temperament** in a per-node table (a migration) or the
  pinned definition (D1: rollback-unsafe today; the freeze is needed anyway).
