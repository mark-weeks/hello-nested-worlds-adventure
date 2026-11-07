# ADR-036: Puzzle temperament — moods, send-aways and warmth instead of a fixed attempt pool

**Status:** Proposed, 2026-11-07. **Owner:** Mark Weeks. Records the owner's
puzzle decisions of 2026-11-06 and 2026-11-07 and designs them against the
code. Not ratified; it writes no code, migration or write path and authorizes
no implementation, deployment or merge. Cited ranges were read at `f3ead74`
and are byte-identical at `3200eed` (#153), except `_history_block`, two lines
lower there. Claims are *executed*, *read* or *inferred*. Not on `main`, so
named, not linked: #156 (`docs/evaluation/2026-11-06-next-build.md`) and
ADR-037 (Proposed, `docs/decisions/ADR-037-agents-as-conversational-players.md`
on `claude/adr-037-agents-in-chat`, read at `9059713`).

## Context

**The owner's decisions, verbatim.**

- 2026-11-06: "the puzzles themselves can have personalities of sorts. So if
  there are too many failed attempts the puzzle may get annoyed and tell the
  player to go away and leave it alone. Conversely, if a player's answer is
  close then perhaps the puzzle get excited by the progress and encourages the
  player to try again. Puzzle attempts and lock periods can be dynamic in this
  way rather than fixed and static." And: "I suggest that AI agents do not
  solve puzzles independently. However, they can cooperate with human players
  to help solve puzzles."
- 2026-11-07: "1. an annoyed player generally gets grumpier toward all
  players, but especially the player(s) that are annoying it"; "2. agents can
  suggest puzzle answers if a human engages with the agent and proposes
  collaboration. Agents do not submit puzzle answers"; "3. puzzles can give
  subtle hints like "you're getting warmer" or "you're way off" in their voice
  and personality". Answer 1 says "player"; this record reads it as an annoyed
  **puzzle**, the subject of the question. Two further answers were "I don't
  understand the question"; neither is read as a decision, and the open
  questions below are rewritten in plain language.
- Decided 2026-11-06 and recorded in ADR-037 and #156: structural parity
  (option (b)) and the disclosure guardrails (a) to (d). Still open, and not
  decided here: S5 chat permanence, S2 player-text destinations, E2 spend
  ceiling, watch timing.

**Supersedes in part, on ratification.**
[ADR-022](ADR-022-m4-responsive-inhabitants.md)'s puzzle-eligibility paragraph
(lines 49-51, "one deterministic difficulty-weighted attempt per current
renewal epoch"), implemented though marked Proposed, retires with D5; the
attention marker's `puzzle_epoch` column (line 81) stays, unwritten and
unread, with no migration. [ADR-032](ADR-032-inhabitant-cognition.md) D4
(lines 132-136, an inhabitant "attempts a puzzle by answering it") is contrary
to "do not solve puzzles independently" and needs revising before
ratification, as ADR-037 also says.

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
  unstabilized node (`multiverse/effects.py:69-73`): an ambient roll takes a
  later human's reward (#156, finding 4).
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
15.3% (numeric_pattern 499 in 8..324, augury reach 135 in 2..8, enfold 10 in
1..10); hand-written riddles 47 (two integers, 16..32).

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
- **Warning, then send-away.** A strike is *warned* when its count reaches
  `P − 1`, with `P` as it stood then. A strike sends the player away only if
  the previous one was warned and its own count reaches `P`, so a warning line
  always comes first, even when others' failures lower `P` between guesses.
  The send-away bars this puzzle only, for `first × 3^k` (`k` = their
  send-aways here in 24 hours), doubled while grumpy, capped at 4 hours;
  guesses meanwhile are neither judged nor stored. Anyone else can still
  solve; a sent-away contributor is credited. Difficulty already sets `b`;
  longer send-aways for hard puzzles would make the hardest the harshest,
  against "Fair, never a wall" (`puzzles/generators.py:12-15`).
- **Excitement.** Every wrong guess is a strike. The band (D3) of the guess
  being judged picks its line, and a top-band guess that would send the player
  away gets an excited warning instead ("Oh! So close. Try me once more."):
  their next strike at or past patience goes, whatever its band. Closeness
  buys at most one guess beyond patience, and the fold never needs an earlier
  guess's band, which is not stored, nor reliably its text (*executed*
  2026-11-07T05:25:57Z: one one-edit miss stored no `guess` with moderation
  disabled and `"guess": "50"` with it on).

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
fold, a pure `(rows, now) → mood, strikes, away_until`, runs in
`will_store_guess` (`server/rooms.py:264-283`), which then returns false for
an away player so no screen or classify call is spent, and authoritatively in
`puzzle_attempt`'s writer transaction (`:286-311`) before `record_attempt`
claims a solver, so a right answer while away is not accepted and two quick
guesses cannot both slip under a limit. **Lock expiry is not puzzle
selection:** which puzzle a node serves stays a pure function of
`(node, epoch)` and pinned rows; time decides only whether a guess is heard
and which line answers, as the rate limiter (`server/guard.py` `RateLimiter`)
and sanction expiry (`persistence/sanctions.py`) do. Lines are chosen by a
hash of node, puzzle, actor and attempt ordinal, never entropy; moods are
responses, not state, so Wayback shows none ([ADR-011](ADR-011-wayback-surface.md)).

### D3. Warmth: whole-answer bands in the puzzle's voice

The judge returns a band and an authored line, never a direction, position,
letter or count of right parts. Every metric reads the whole answer after the
correctness check's normalization (`server/handlers.py:2030`, `:2047`).
Per-part metrics are Mastermind: *executed*, a searcher told how many compass
marks are right names 490 of 828 answers in a first patience window, 800
within two.

| Family | Band | Why (*executed*, seed-382 census) |
|---|---|---|
| anagram, cipher | edit distance: *way off*, *cold*, *warm*, *very close* at difficulty 1-2; 3 folds way off into cold; 4 says only *not close* or *close* | A word list, not the band, is what a searcher needs: 485 of 496 anagrams have one bank word with their letters (11 have two), and a cipher has 3 to 9 shifts. The letter-permutation bound (458 of 496 beyond a first window) holds only without a word list |
| keeper_witness, augury names, lineage, bond, sealed_lock, word riddles | typo band only | A wrong word reads far: 4,976 of 493,536 one-word substitutions (1.0%) read very close. On lineage (910 candidates) a searcher using the band names 1 of 301 in a first window, 12 within two |
| ancestral_compass | none: "not it" in voice | Small domains (median 56): blind enumeration names 137 of 828 in a first window, and the typo band doubles that to 279 |
| numeric_pattern | *warm* only when the guess extends the last step's gap or ratio but not the pattern ("a rhythm, not its rhythm") | Four directionless magnitude bands made it a search: 268 of 499 found in a first window |
| enfold, augury reach, integer riddles | none | Small domains (1..10, 2..8, 16..32) |

The typo band reads *very close* (*close* at difficulty 4) for one edit or
under 15% normalized distance. A band still discloses something: a near miss
says the answer is one edit away, and later bands narrow where, bounded by
patience and the counts above. The searchers are generous: they know each
reading's bank and minimize the worst case (scripts named in the CHANGELOG).

**Wrong-guess text stops being public** (open question 6). Under warmth a
stored excerpt is each player's path to the answer, near misses included, and
anyone can fetch it. New `PUZZLE_ATTEMPT` and `PUZZLE_FAILED` rows stop storing
`guess` and `answer_given` (`server/handlers.py:2071-2073`, `:2146-2148`): an
existing call site writing less, old rows unchanged and still redactable, and
one fewer moderation screen per wrong guess. Separate from S5, still open.
Hints keep their content; each player climbs the ladder with their own wrong
guesses and the last rung repeats, where today's pooled index
(`server/handlers.py:2115-2118`) leaves a newcomer no hint once the room has
spent it.

### D4. No failure state, so no failure renewal

A puzzle is open or solved: `correct_answer` and `FAILED` leave every
response, closing F10. Packet option 3(b) re-armed failed puzzles through
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

### D5. Agents help when asked, never attempt, never see the answer

- **No ambient attempts.** The heartbeat's puzzle opportunity and the dice
  go; `Agent._act` treats a puzzle node as any interactive node
  (`agents/agent.py:124-126`).
- **Help only on a human's proposal**, by ADR-037 D7's trigger, which that
  record owns: a line addressing an agent at a place with an open puzzle, with
  a help or solve verb aimed at the puzzle by a fixed local pattern, for that
  player, agent and epoch. This record requires that it hold the same with AI
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
  owner set S2's policy on 2026-11-07 ("Information can only be shared with model providers to facilitate game play. Enfolded data must not be used to train frontier models.", recorded by #156), and naming
  the destinations (L3) and checking their terms (L4) stay open.
- **Credit stays human.** Contributors are the humans who guessed; the solve
  row names who submitted. A helping agent is in neither: its help lives in
  the conversation (subject to S5) and the agent's short conversation buffer
  (ADR-037 D8), never `agent_memory`, and nothing labels a solve
  AI-assisted, without labelling who is human. The covenant then reads:
  agents never solve, and a human's solve is theirs even with an agent's
  help. The stored `agent` key and its exclusions stay.

### D6. What is stored, and the doors implementation trips

No new table or row kind. Moods fold from mechanical fields, so moderation
cannot change a count: wrong `PUZZLE_ATTEMPT` rows at the current puzzle name
(it carries the epoch) by the player's identities
(`persistence/participants.py:100-109`; display name when keyless), their
`recorded_at`, and the player's `PUZZLE_FAILED` rows carrying `away_s`;
redaction keeps these (`persistence/__init__.py:917`). Changed write paths,
each an existing call site: no `PUZZLE_ATTEMPT` for a guess refused while away
(`server/handlers.py:2074-2077`); `PUZZLE_FAILED` once per send-away as
`{"puzzle", "contributors", "away_s"}`, not on every guess after a pool fails
(`:2143-2153`); no `guess` or `answer_given` in new rows, if open question 6
agrees; no ambient `PUZZLE_*` rows (`server/heartbeat.py:486-487`,
`agents/agent.py:122-123`); the CLI judged the same way, not printing the
answer (`interface/__init__.py:198-201`, `puzzles/engine.py:110`); the
restated `PUZZLE_REARM` trigger (`causality/wiring.py:66-69`).

The fold counts only `PUZZLE_FAILED` rows with `away_s` and no `agent`, and
keeps each stored length, so a retune never alters a running send-away and
legacy pool or ambient rows never read as send-aways. The key also tells the
eras apart for the other readers: art (`server/imageprompt.py:96`, two rows
make a place "oppressive"), narration (`multiverse/history.py:77`), the feed
(`static/clientlogic.js:259`, "a puzzle resisted {who}") and
`scripts/beta_metrics.py` after #155, whose failure count becomes a send-away
count (C2c).

Doors at implementation: those write paths (owner sign-off at merge); the
pool and ambient-attempt promises in the guide (`static/guide.html:62`,
`:114`, `:121-122`, `:146-147`), `docs/design/game-design.md:125` and the
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

Guide copy (proposed): the Solve row (`static/guide.html:62`) becomes "Crack
a node's puzzle. Each one has a temper: it may tell you you're getting warmer,
or send you away for a while if you keep missing. One correct answer counts
for everyone who tried."; `:146-147` drops "co-op attempts already pool, so".
ADR-037 D5(b) rewrites and owns "You are not alone" (`:108-122`); this record
supplies its puzzle sentences: `:114` drops "attempt puzzles under the same
rules you play by", and `:121-122` becomes "Solving is better together: a
puzzle that is tired of you will still hear a friend."

### D8. Batches, in order

Batches 1 and 2 open write-path doors and should land before the first
production boot (#156, finding 1).

1. **No answer release; per-player send-aways** (one flat temperament): fold,
   handler (both away checks), marked `PUZZLE_FAILED`, `GET /puzzle` away
   state, both clients, the guide's Solve row and constellation line, and
   `docs/design/game-design.md:125`. Tests: invert
   `tests/test_server.py:272-281`; fold (window, floor, a warning before every
   send-away even when `P` drops, one near-miss reprieve, escalation, grumpy
   factor, cap, per-player load cap, a zero-strike player never sent away
   after 50 others fail, unmarked rows ignored, a retune leaves a running
   send-away alone); HTTP (away is 200; a guess while away makes no
   moderation call, writes no row and reveals nothing; a right answer while
   away is refused; another player solves; equal strikes with moderation
   disabled; moods survive a restart as in `tests/test_server_rooms.py`);
   Vitest and Playwright.
2. **Agents stop attempting; renewal on a human solve**: heartbeat,
   `Agent._act`, CLI, `_maybe_rearm`, the guide's "attempt puzzles" clause,
   the bible's "You attempt puzzles" sentence, AGENTS.md. Tests: no
   `PUZZLE_*` from a tick (replacing `tests/test_agent_attention.py:184`,
   `:394`); an old ambient solve neither re-arms nor takes a human's reward;
   epoch equals the `PUZZLE_REARM` count (`tests/test_game_depth.py:136`); a
   scratch soak records the danger spread before and after.
3. **Temperaments, voice bank, warmth, per-player hints, wrong-guess text.**
   Tests: secrecy in `tests/test_puzzles.py` over every line and band on the
   seed-382 census; no band for integers or compass marks; equally distant
   guesses get one band whichever part differs; the searcher bounds; the draw
   pin; patience never falls with difficulty for fixed `t` and `g`.
4. **Agent collaboration**, shared with ADR-037's batch 4: its trigger, the
   public puzzle view in agent context only after it, the AI-off line, no
   agent prompt holding the answer, the bible's "never reveal an answer"
   sentence rewritten with ADR-037. Needs ADR-037 for chat, S2 and E2 for AI
   on.

## Open questions for the owner (each changes the design)

1. *Should a puzzle nobody has solved ever turn into a new puzzle by itself?*
   Recommended: no; it stays the same puzzle until someone solves it.
2. *How long can the longest "go away" last?* Recommended: four hours, and a
   puzzle forgets a player's send-aways after a day.
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
   only whether a guess was right.

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
  human: kind becomes inferable from row patterns, as ADR-037 accepts.
- From the first production deploy, changing who is prickly needs an ADR.

## Revisit when

- The pilot (C2c) shows a family's solve rate outside the proposed 40-85%,
  testers call send-aways punitive, or warmth trivializes a family.
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

- **Fixed pools** (today; packet options (a), (c)): release the answer (F10)
  or close the puzzle for everyone; static. **Per-player pools only** (d): no
  shared mood, so not answer 1, and a pool still ends in release or close.
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
