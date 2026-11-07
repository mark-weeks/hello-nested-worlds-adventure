# ADR-036: Puzzle temperament — moods, send-aways and warmth instead of a fixed attempt pool

**Status:** Proposed, 2026-11-07. **Owner:** Mark Weeks. Records the owner's
puzzle decisions of 2026-11-06 and 2026-11-07 and designs them against the
code. Not ratified. It writes no code, migration or write path and authorizes
no implementation, deployment or merge. Every cited range was read at
`3200eed` (#153) and is byte-identical at `f3ead74`. Claims are marked
*executed*, *read* or *inferred*. The 2026-11-06 record this builds on is in #156
(`docs/evaluation/2026-11-06-next-build.md`, not yet on `main`).

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
- Not decided here: structural parity (agents addressable in chat, option
  (b)) and the disclosure guardrails (a) to (d), which get their own record;
  S5 chat permanence, S2 player-text providers, E2 spend ceiling, watch timing.

**Today** (*read* unless marked).

- One pooled session per node (`server/rooms.py:109-122`) counts every guess
  and claims the first correct one (`:330-358`), rehydrated from
  `PUZZLE_ATTEMPT` rows (`:152-174`, `persistence/__init__.py:1045-1062`).
  At `max_attempts` the handler marks the puzzle failed
  (`server/handlers.py:2114`), writes `PUZZLE_FAILED` (`:2143-2153`) and
  returns the answer (`:2169`), which both clients print
  (`static/explorer.js:960-961`, `frontend/src/components/Interact.jsx:258-259`).
  **F10, *executed* at `3200eed`** on a scratch database (seed 42, difficulty-3
  root, pool 4): guesses 4, 5 and 6 each returned `FAILED` with the answer and
  wrote `PUZZLE_FAILED`; a player who had never guessed then solved with it
  and took the reward.
- The cast attempts puzzles by dice (`server/heartbeat.py:393-394`, `:481-490`;
  `agents/agent.py:23-26`, `:71-98`, `:113-123`); the CLI observer's bus is
  wired to the chronicle (`interface/__init__.py:160-163`). Solve state skips
  rows carrying `agent` (`persistence/__init__.py:662-690`), but
  `_maybe_rearm` counts every `PUZZLE_SOLVED` (`causality/wiring.py:54-69`) and
  a solve stabilizes only an unstabilized node (`multiverse/effects.py:69-73`):
  an ambient roll takes a later human's reward (#156, finding 4).
- Difficulty is `sha256("difficulty:{level}:{name}")`
  (`puzzles/generators.py:65-75`) and sets attempts 3, 4, 4, 5 (`:62`).
  Definitions, `max_attempts` included, pin at first use per epoch
  (`puzzles/instances.py:46-69`, `persistence/puzzle_content.py:13-19`); the
  epoch counts `PUZZLE_REARM` rows (`persistence/__init__.py:1025-1041`); the
  epoch-0 pin hashes name and answer (`tests/test_continuity_freeze.py:233-251`).
  Era names are the frozen read-time precedent (`multiverse/chronicle.py:17-21`,
  `tests/test_continuity_freeze.py:254-261`). The Augury's `_LAW_TEMPERAMENT`
  (`puzzles/generators.py:959-985`) is unrelated.

**Census, *executed*** on the unborn seed-382 world (4,208 puzzles, epoch 0)
with `puzzles.quality.puzzle_family` and scratch scripts:

| Answer shape | Families (puzzles) | Share |
|---|---|---|
| Phrase of 2-3 words | keeper_witness (839), causal_augury names (261) | 26.1% |
| 3-4 letter mark | ancestral_compass (828), lineage (301) | 26.8% |
| Word | anagram (496), cipher (405) | 21.4% |
| Categorical reading | bond (247), sealed_lock (140) | 9.2% |
| Integer | numeric_pattern (499, 8..324), augury reach (135, 2..8), enfold (10, 1..10) | 15.3% |
| Hand-written | riddles (47) | 1.1% |

A simulated blind searcher (never infers the rule, knows the answer lies in
(last term, 4 × last], minimizes the worst case) found the `numeric_pattern`
answer within its first patience window in **268 of 499** under four
directionless relative-error bands, two or three at difficulty 3-4 (d1
59/101, d2 45/106, d3 53/157, d4 111/135). For anagrams the information bound
(log2(bands) bits a guess against log2 of the distinct permutations) keeps
**458 of 496** beyond a first window. Magnitude warmth makes numbers a search.

## Decision

All numbers below are recommended defaults the owner can veto.

### D1. Temperament: a frozen trait of the node, like difficulty

Each node's puzzle draws one of four temperaments from its own keyed domain,
`sha256("temperament:{level}:{name}")[0] % 4`, ignoring the epoch, so a
renewed puzzle keeps its temper as it keeps its difficulty
(`puzzles/generators.py:1139`). *Executed* on seed 382: 24.6% to 25.2% each,
241 to 282 in every temperament × difficulty cell. It sets tone and patience,
never name, prompt, answer, hints or difficulty: `build_puzzle`, pinned
definitions and golden pins are untouched.

| Temperament (never shown) | Patience | Strikes forgiven after | First send-away | Sample warm line | Sample send-away line |
|---|---|---|---|---|---|
| patient | +1 | 20 min | 3 min | "Closer. Breathe, and try again." | "Let us both rest. Come back when the light has turned." |
| proud | 0 | 30 min | 5 min | "Ha! You nearly had me." | "Enough. I will not be guessed at. Leave me be." |
| playful | 0 | 30 min | 5 min | "Ooh, you're getting warmer!" | "I'm bored of you now. Go and play somewhere else for a while." |
| prickly | −1 | 45 min | 8 min | "Hm. Not wrong in every way." | "Go away. Leave me alone." |

**Freeze, do not materialize.** Read at use like era names, the draw would
give every puzzle a new personality if the tuple changed, so a new class in
`tests/test_continuity_freeze.py` pins the tuple and the temperament of fixed
reference nodes (a new pin, not a re-pin). Numbers and lines stay tunable: no
line is stored and send-aways are recomputed from rows (D6). Materializing
needs a per-node store (`puzzle_instances` is per epoch), so a migration for
a value derivable from identity. *Inferred.*

### D2. Mood: grumpy toward everyone, annoyed at whoever is failing

- **Base patience** `b` is the pinned `max_attempts`, so "harder puzzles get
  MORE attempts" (`puzzles/generators.py:12-15`) survives as patience and
  `TestDifficultyIsPerNode::test_attempts_track_puzzle_difficulty` holds.
- **Grumpiness** (everyone): wrong guesses at the current puzzle in the last
  60 minutes, at most `b` counted per player. *Testy* at `2b` and *grumpy* at
  `4b` cost everyone 1 or 2 patience and sharpen every line. The per-player
  cap means one player failing a lot annoys the puzzle, not everyone's mood.
- **Annoyance** (per player): strikes are the player's own wrong guesses here
  within the temperament's window since their last send-away ended.
  Patience is `max(2, b + temperament − grumpiness)`.
- **Send-away.** The guess that brings strikes to patience sends that player
  away from this puzzle only, for `first × 3^k` (`k` = their send-aways here
  in 24 hours), capped at 4 hours. The guess before always gets a warning
  line. While away, their guesses are neither judged nor stored. Anyone else
  can still solve, and a sent-away contributor is credited as today.
- **Excitement.** The first guess in a window that lands in the top band is
  not a strike ("you nearly had me, again!"); later ones count.

**Only the annoying player is ever sent away.** A send-away follows only the
player's own wrong guesses; grumpiness can shorten patience to two but never
locks out someone who has not failed. A puzzle-wide lockout would let one
player's guessing decide everyone's access and hold a sealed Room shut for
the world, breaking "every player owns their actions" and arming griefers.
Here a griefer sends only themselves away, and the per-player cap stops them
souring the puzzle alone. The seal never imprisons (`puzzles/gates.py:81-82`):
a send-away bars guesses, never movement.

**The clock** is the database's: rows' `recorded_at` (`datetime('now')`,
`persistence/migrations/0001_initial.sql:39`) against `datetime('now')` in one
query, inside `puzzle_attempt`'s writer transaction (`server/rooms.py:286-311`),
so two quick guesses cannot both slip under a limit; a pure fold,
`(rows, now) → mood, strikes, away_until`, decides. **Lock expiry is not
puzzle selection:** which puzzle a node serves, and its content, stays a pure
function of `(node, epoch)` and pinned rows. Time decides only whether a
guess is heard now and which authored line answers, as the rate limiter
(`server/guard.py` `RateLimiter`) and sanction expiry
(`persistence/sanctions.py`) do. Lines are chosen by a hash of node, puzzle,
actor and attempt ordinal, never entropy; moods are responses, not state, so
Wayback shows none ([ADR-011](ADR-011-wayback-surface.md)).

### D3. Warmth: coarse bands in the puzzle's voice, never which part is right

The judge returns only a band and an authored line: *way off*, *cold*,
*warm*, *very close* at difficulty 1-2; difficulty 3 folds way off into cold;
difficulty 4 says only *not close* or *close*. No line gives a direction, a
position or a letter. Bands are never stored: attempt rows are chronicle
rows with a public guess excerpt (`server/handlers.py:2061-2077`), so a stored
band would give everyone free readings of other players' guesses.

| Family | Closeness metric | Fallback |
|---|---|---|
| anagram, cipher | normalized edit distance (a wrong shift reads far: decoding is all or nothing) | — |
| keeper_witness, augury names | share of words right, in place | typo band |
| ancestral_compass, lineage | share of marks right | typo band |
| bond, sealed_lock, riddles | typo band only: another reading is just wrong, and a band would say which neighbour to try | plain "not it" |
| numeric_pattern | no magnitude band; *warm* only when the guess extends the last step's gap or ratio but not the pattern ("a rhythm, not its rhythm") | plain "not it" |
| enfold, augury reach, integer riddles | none: domains of 1..10 | plain "not it" |

The typo band reads *very close* (*close* at difficulty 4) for one edit or
under 15% normalized distance, after the correctness check's normalization
(`server/handlers.py:2030`, `:2047`). Hints keep their content; each player
climbs the ladder with their own wrong guesses, and the last rung repeats.
Today's pooled index (`server/handlers.py:2115-2118`) leaves a newcomer no
hint once the room has spent the ladder.

### D4. No failure state, so no failure renewal

A puzzle is open or solved: `correct_answer` and `FAILED` leave every
response, closing F10. Packet option 3(b) re-armed failed puzzles through
decay, which stops once decay has disturbed and fractured a Room (#156,
finding 2). A puzzle that never fails for everyone needs no failure re-arm,
so that defect has nothing to act on; an unsolved sealed Room stays sealed
to outsiders until a human solves it. Renewal after a solve keeps today's
path and the epoch stays the `PUZZLE_REARM` count, but "solves exceed
re-arms" (`causality/wiring.py:64-66`) becomes "the current epoch's puzzle
has a human solve" (`persistence.get_puzzle_solve`), which old ambient rows
cannot satisfy. A solve sets `stabilized` (`multiverse/effects.py:69-71`) and
the next `DANGER_ALERT` clears it (`:81-83`), so a solved Room can always
renew (*read*; #156 executed this). A renewed puzzle's new name starts its
moods clean.

### D5. Agents help when asked, never attempt, never see the answer

- **No ambient attempts.** The heartbeat's puzzle opportunity and the dice
  go; `Agent._act` treats a puzzle node as any interactive node
  (`agents/agent.py:124-126`).
- **Help only on a human's invitation.** When a human addresses an agent
  (Speak today, chat once parity ships) from a node with an open puzzle and
  asks for help, the agent may discuss it and offer a guess as its own. It
  never submits: no server path gives an agent identity an attempt, and
  server identities are reserved names (`server/handlers.py:174-181`). With
  AI on the model judges whether help was asked for; with AI off the agent
  gives a willing, empty authored line ("Read me what it asks").
- **Agents never see the answer**, only what the player can read (`/puzzle`,
  `/puzzle/evidence`, the place as `/world` serves it) and what the human
  says. Puzzles left node properties because a voice could be asked to reveal
  them (`puzzles/engine.py:45-50`). An agent holding the answer would hand it
  to anyone who asks, invite prompt injection, and differ with AI off; from
  the same clues it is a peer whose guesses can be wrong. With AI on, the
  human's words go to a provider, so this waits on S2 and E2.
- **Credit stays human.** Contributors are the humans who guessed; the solve
  row names who submitted. A helping agent is in neither: its help lives in
  the conversation (subject to S5) and its memory, and nothing labels a solve
  AI-assisted, keeping the no-labels decision and the chronicle blur. The
  covenant then reads: agents never solve, and a human's solve is theirs even
  with an agent's help. The stored `agent` key and its exclusions stay.

### D6. What is stored, and the doors implementation trips

No new state. Moods fold from wrong `PUZZLE_ATTEMPT` rows at the current
puzzle name (it carries the epoch) by the player's identities
(`persistence/participants.py:100-109`, `actor_aliases`; display name when
keyless), their `PUZZLE_FAILED` rows, now marking send-aways, and
`recorded_at`; redaction keeps those fields (AGENTS.md). Changed write
paths, each an existing call, no new row kind: no `PUZZLE_ATTEMPT` for a
guess refused while away (`server/handlers.py:2074-2077`); `PUZZLE_FAILED`
once per send-away, not on every guess after a pool fails (`:2149-2153`); no
ambient `PUZZLE_*` rows (`server/heartbeat.py:486-487`,
`agents/agent.py:122-123`); the CLI judged the same way, no longer printing
the answer (`interface/__init__.py:198-201`,
`puzzles/engine.py:110`); the restated `PUZZLE_REARM` trigger
(`causality/wiring.py:66-69`). `PUZZLE_FAILED`'s readers still make sense:
art (`server/imageprompt.py:96`), narration (`multiverse/history.py:77`), and
`scripts/beta_metrics.py`, whose failure count becomes a send-away count (C2c).

Doors at implementation: those write paths (owner sign-off at merge); the
guide's promises that "Attempts pool across every player present"
(`static/guide.html:62`), of "one pool of attempts" (`:121-122`) and that the
cast attempts "puzzles under the same rules you play by" (`:114`); AGENTS.md's
agent-solve covenant; and a new frozen read-time surface, the temperament
draw, listed beside era names in AGENTS.md and the irreversibility skill. No
migration, golden re-pin, or change to `build_puzzle` or `puzzle_instances`.

### D7. Surfaces: the existing result line speaks

The voice replaces "Wrong.", "N attempts left" and the answer release in the
existing result line, `#puzzle-result` (`static/explorer.js:912`, `:950-971`)
and `/app`'s result block (`frontend/src/components/Interact.jsx:247-266`).
Hints keep their slot; there is no new pane, meter or counter. A send-away is
HTTP 200 with `result: "AWAY"`, the line and `away_for_s`, never a 4xx, as
both clients render `error` verbatim; the input re-opens when time passes,
and `GET /puzzle` learns the reader and reports their away state as it
reports `solved` (`server/handlers.py:1889-1896`). About 100 authored lines
(temperament × band, warning, send-away, still-away, solved; calm and grumpy)
cover every case. The judge calls no model: AI on and off behave the same.
Proposed guide copy: the Solve row (`static/guide.html:62`) becomes "Crack a
node's puzzle. Each one has a temper: it may tell you you're getting warmer,
or send you away for a while if you keep missing. One correct answer counts
for everyone who tried."; `:121-122` becomes "Solving is better together: a
puzzle that is tired of you will still hear a friend."; `:114` drops "attempt
puzzles under the same rules you play by" (the parity record rewrites the
rest of that paragraph).

### D8. Batches, in order

Batches 1 and 2 open write-path doors and should land before the first
production boot (#156, finding 1).

1. **No answer release; per-player send-aways** (one flat temperament): fold,
   handler, `GET /puzzle` away state, both clients, guide. Tests: invert
   `tests/test_server.py:272-281`; fold tests (window, floor, escalation, cap,
   per-player cap, a zero-strike player never sent away after 50 others
   fail); HTTP tests (away is 200, a right answer while away is not judged,
   another player solves, moods survive a restart as in
   `tests/test_server_rooms.py`); Vitest and Playwright.
2. **Agents stop attempting; renewal on a human solve**: heartbeat,
   `Agent._act`, CLI, `_maybe_rearm`, guide `:114`, AGENTS.md. Tests: no
   `PUZZLE_*` from a tick (replacing `tests/test_agent_attention.py:184`,
   `:394`); an old ambient solve neither re-arms nor takes a human's reward;
   epoch equals the `PUZZLE_REARM` count (`tests/test_game_depth.py:136`).
3. **Temperaments, voice bank, warmth, per-player hints.** Tests: secrecy in
   `tests/test_puzzles.py` over every line and band response on the seed-382
   census; no magnitude band for integers; a searcher bound; the draw pin.
4. **Agent collaboration**: the public puzzle view in agent context, the
   AI-off line, no composed agent prompt holding the answer. Needs the parity
   record for chat, and S2 and E2 for AI on.

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

## Trade-offs accepted

- Patience differs by up to two guesses between equally difficult puzzles,
  so a prickly hard puzzle can be less patient than a patient easy one; the
  1-4 rating keeps meaning how hard a puzzle is to think through.
- The same guess can meet a different line an hour later; a puzzle can stay
  unsolved indefinitely; number puzzles get almost no warmth; the one-pool
  promise becomes a shared mood and one shared solve.
- From the first production deploy, changing who is prickly needs an ADR.

## Revisit when

- The pilot (C2c) shows a family's solve rate outside the proposed 40-85%,
  testers call send-aways punitive, or warmth trivializes a family.
- Temperaments must change for existing puzzles or evolve with history
  ([ADR-029](ADR-029-evolution-grammar.md)): materialize them then.
- The world leaves its single SQLite writer, which changes the clock.
- The parity record or [ADR-032](ADR-032-inhabitant-cognition.md) lets agents
  act on stage: decide whether an agent may volunteer help unasked.

## Rejected alternatives

- **Fixed pools** (today; packet options (a), (c)): release the answer (F10)
  or close the puzzle for everyone; static. **Per-player pools only** (d): no
  shared mood, so not answer 1, and a pool still ends in release or close.
- **Option 3(b)**, fail then re-arm through decay: cannot keep renewing a
  failed Room (#156, finding 2); superseded by the owner.
- **Puzzle-wide lockouts**: one player's guesses decide everyone's access.
- **Model-decided lockouts or model-written puzzle voice**: a cost per guess,
  nondeterministic, different with AI off, and a model holding the answer
  can be talked into leaking it.
- **Magnitude warmth on numbers**: measured to make them a search.
- **Agents that see the answer, or submit behind a confirm button**: answer
  delivery, and an agent-originated action.
- **Materializing temperament**: a migration for a value identity derives.
