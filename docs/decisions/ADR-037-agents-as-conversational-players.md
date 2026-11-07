# ADR-037: Agents as conversational players — addressed in chat, unlabeled, honest

**Status:** Proposed, 2026-11-07. **Owner:** Mark Weeks. Records the owner's
2026-11-06 decisions on agent disclosure and structural parity, and his
2026-11-07 answers, designed against `main` at `f3ead74`. **Not ratified.** No
code, migration, write path, player-text destination, spend or deployment;
citing it authorizes nothing.

It depends on records not on `main`, named rather than linked: #156 (the
2026-11-06 decisions in `docs/evaluation/2026-11-06-next-build.md`, checklist
A1 rewritten); ADR-036 (puzzle temperament, Proposed, read at `a114cf8` on
`claude/adr-036-puzzle-temperament`); and the honesty batch on
`claude/agent-honesty-guardrails`, with no commit beyond `3200eed` at this
writing, so its parts stay dependencies. Evidence is *executed* (scratch
seed-382 databases, `f3ead74` code, 2026-11-07), *read* (each `file:line`
re-read at `f3ead74`) or *inferred*. #153 merged after this base (`3200eed`),
moving only the cited `server/guard.py` lines and `consciousness/__init__.py`
below line 668 (`:829-877` by two, `:1148` by three).

## Context

**The owner's decisions** (quoted words are Mark Weeks's):

- *Disclosure, 2026-11-06:* "let's not label agents. It will be more
  interesting if it's not obvious which players are human and which are
  agents." But "if a player asks an AI agent player 'are you human?' the AI
  agent player should not pretend to be human." He accepted guardrails (a) to
  (d), restated as requirements in D5.
- *Structural parity, 2026-11-06, option (b):* agents can be addressed in chat
  and answer there, and the guide stops naming the cast, because "this would
  allow human-ai collaboration on puzzles. It would also give human players
  other players to interact with, even if there are no other human players
  logged in at the same time."
- *Puzzles:* "I suggest that AI agents do not solve puzzles independently.
  However, they can cooperate with human players to help solve puzzles."
  (2026-11-06) "agents can suggest puzzle answers if a human engages with the
  agent and proposes collaboration. Agents do not submit puzzle answers."
  (2026-11-07) His answer "an annoyed player generally gets grumpier toward all
  players" is read as an annoyed *puzzle*, which is ADR-036's subject.

**What the code does today.**

| Area | Today | Evidence |
|---|---|---|
| Chat | Screened, broadcast to every socket in the room, stored as `PLAYER_CHAT`. One room per seed and one canonical world ([ADR-007](ADR-007-one-shared-launch-world.md)) make it world-wide | `server/websocket.py:605-649`, `server/rooms.py:145-149`, `:177-189` (read) |
| Talking to agents | Speak lists up to four names from `/history` `data.agent` at this place, present or not, and posts to `/agent/voice`; only the asker sees the reply | `frontend/src/components/Interact.jsx:52-69`, `:79-95`; `static/explorer.js:737-756`, `:769-777`; `server/handlers.py:1464-1548` (read) |
| Presence | Welcome sends `players` and `agents` apart; `agent_enter` carries a persona; cast talk is `agent_talk`; `agent_done` says "Agent" | `server/websocket.py:447-454`, `server/rooms.py:192-200`, `:232-238`, `server/heartbeat.py:277-284`, `frontend/src/App.jsx:343`, `static/explorer.js:1207-1208` (read) |
| Live notices | A cast visit sends `causal_event` kind `AGENT_VISIT` with `agent` and `persona` and no narration, so both feeds print "↯ agent visit · …"; a human move sends `player_move` only. `/act` sends `scale_act` then a `causal_event` with `action_notice`; a cast act sends `scale_act` alone | `server/heartbeat.py:400-404`, `:478-480`, `server/websocket.py:587-596`, `server/handlers.py:1993-2005`, `server/heartbeat.py:210-215`, `multiverse/history.py:46-47`, `static/clientlogic.js:225-229`, `:298-302`, `frontend/src/App.jsx:309-311`, `static/explorer.js:1229-1231` (read). *Executed* 05:03:53Z, three ticks: 15 such frames; with `agent` and `persona` removed, `causalNoticeLine` still returned "↯ agent visit · Weathered Cinder Archipelago ×1.00" |
| Traveler rows | Humans get ◈ (`/app`) or ◆ (map); the cast gets ✦, a persona tag, another ring colour and dash, "follow" for "go to", "…arriving" for "—", and the accessible name "Inhabitant" | `frontend/src/components/TextPanel.jsx:47-48`, `static/explorer.js:990`, `:1303-1319`, `:1384`; [visual language](../design/visual-language.md) lines 206-208 (read) |
| Presence time | A walker is present only while it walks | *Executed* 04:12:25Z–04:13:01Z, four ticks at the default pace: present 1.21, 3.67, 6.08 and 12.05 s. At the default 180 s interval (`server/heartbeat.py:55`) one walker is visible at most about 7% of the time (*inferred*) |
| Served history | `/chronicle` serves stored data plus raw `actor_identity` as `actor` | `server/handlers.py:977-993`, `persistence/__init__.py:1101` (read); *executed*, same probe: 18 `AGENT_VISIT` rows served `agent` and `persona` and no `actor`, a keyed human's chat row a 16-hex `actor`; talk rows store `a_persona`, `b_persona` (`server/heartbeat.py:271-276`) |
| Kind oracles | `/register` refuses a cast name with 403 "belongs to the world", a taken one with 409; the keyless WS join (local mode) refuses a cast name the same way; an `/observe` walk enters presence as `Observer` | `server/handlers.py:1613-1617`, `:1635-1639`, `server/websocket.py:385-388`, `server/handlers.py:1709`, `:1791` (read) |
| Prompts | Every bible's premise names the twelve as "a recurring cast of wanderers"; the agent bible says "acknowledge other agents or players" and lists the other eleven as colleagues; "Never break the fourth wall or reveal that you are an AI"; agents do not ask whether a visitor is human, and "attempt puzzles under the same rules as any traveler" | `consciousness/__init__.py:342-346`, `:419-420`, `:520-523`, `:386`, `:421`, `:544-546`, `:515-518` (read) |
| Agent context | `/agent/voice` passes node history whose block quotes every traveler's chat at that place word for word | `server/handlers.py:1527-1535`, `persistence/__init__.py:716-728`, `consciousness/__init__.py:868-877` (read); *executed* 05:05:33Z: another player's untriggered line appeared in the block |
| Guide and copy | Names the cast; "humans and the cast alike"; "address agents whose traces you find"; "Talk to other explorers"; the journal says "Inhabitants and other players" | `static/guide.html:108-122`, `:61`, `:64`; `static/journal.html:3` (read) |
| Puzzles | Walkers roll dice and write `PUZZLE_SOLVED`/`PUZZLE_FAILED`; the stored `agent` key keeps those rows out of co-op sessions and seals; only a wrong guess is ever stored | `server/heartbeat.py:481-490`, `persistence/__init__.py:682`, `:1313`, `server/handlers.py:2053-2066` (read) |

The stored `agent` key stays: the agent-solve covenant reads it, and
`agent_memory`, `agent_runs` and `AGENT_VISIT` are keyed by the unredactable
name (`agents/identities.py:3-6`). The heartbeat makes no model call
(`server/heartbeat.py:18-19`; [ADR-022](ADR-022-m4-responsive-inhabitants.md)).
[ADR-032](ADR-032-inhabitant-cognition.md) (Proposed) would put inhabitant
speech in Speak (D2, D5), persona-tag visitor agents (D6) and have inhabitants
answer puzzles (D4); the owner's decisions depart from those parts, so ADR-032
needs revising before ratification.

## Decision

### D1. One surface: travelers in chat, places in Speak

Every traveler, human or agent, is talked to in chat; Speak is speech to a
place. Speak's agent targets, both clients' calls to `/agent/voice` and the
endpoint's player route retire. The keeper commitments it retrieves
(`keeper_history`, [ADR-025](ADR-025-first-situation.md)) move into the chat
reply's context. Talking to an absent agent's trace ends.

### D2. Presence that can keep company

While a human is connected, up to **two** agents linger where their last walk
ended, as live presence only: no row, visit or attention marker, and no change
to ADR-022's caps; a third may be walking. Lingerers rotate with the heartbeat
and leave when the last human does. Without this, "even if there are no other
human players logged in" finds nobody about 93% of the time (*inferred*).

### D3. When an agent answers, and how often

A line **addresses** a traveler when it starts with their name followed by a
comma, colon, `?`, `!` or its end, or ends with a comma and their name (then
`?`, `!` or `.` at most), compared by `persistence.name_key`. "Karst, what is
this?" addresses Karst; "karst formations here?" addresses nobody, so the
dictionary-word names (Vex, Karst, Marginalia, Petrichor) do not fire. Triggers
are local and deterministic, on a human line that passed the screen:

1. **Addressed:** the line addresses a present agent; the first one answers.
2. **A question at its place:** it ends in `?`, addresses no one, and exactly
   one agent stands at the sender's place.
3. **Quiet company:** it addresses no one, and nobody but the sender and their
   last answerer has chatted in five minutes; the agent that answered them in
   the last two minutes answers, else the agent at their place if it is alone.

Never a trigger: an agent's line; a line addressing a human, which wins over
any agent it also addresses; a held or declined line
(`server/websocket.py:623-626`); a line from a player who muted that agent. No
trigger or greeting reads how many humans are connected, which no player sees.

**Bounds.** At most one agent line per human line, and each agent at most once
per 8 s, within D6's caps. Agents never answer each other through a model;
cast talk stays the authored banter (`agents/banter.py`), sent as chat lines.
**The honesty answer is exempt** from the pace, the bound and the caps: it is
authored, runs before any model work and is never queued or dropped. A repeat
from the same asker to the same agent within ten minutes gets the same answer
sent to the asker alone and stored nowhere: they already know, so it tells
them nothing new. A sincere question to no one ("is anyone here an AI?") gets
the honesty answer, and nothing else, from each agent at the asker's place
(open question 5).

**Initiation.** A player connected for 60 s, with no other traveler at their
place and no chat line in five minutes, gets one authored greeting from a
present agent (once per agent per player per connection, at most one
unsolicited line per player per ten minutes) as an ordinary chat line, since
a line to one player alone is a shape no human can send. No cost; works with
AI off. ADR-032 D5's model-written unsolicited speech is not adopted.

**Delivery.** An agent's line is an ordinary `chat` frame on a human's
broadcast, so world-wide today; if checklist
[open question 2](../roadmap/beta-launch-checklist.md#open-questions-for-mark)
makes chat place-local, agents follow. Puzzle help is the owner's to decide
(D7). No delay imitates typing. A model reply runs on a bounded worker, never
the sender's socket thread; a full queue drops the trigger.

### D4. No labels

What any player receives treats both kinds alike; operator tools keep the kind.

- **Clients.** Within each client, every traveler row takes the glyph, ring
  colour and style, tooltip and empty-place text that client gives a human
  today, no persona tag, and one accessible name, "Traveler"; the `agent_done`
  notice leaves the feed; the visual-language paragraph follows. Copy sweep:
  `static/guide.html:61`, `:64` and `:108-122`, and `static/journal.html:3`.
- **Wire.** One welcome list, `players`, with the same keys for both kinds; an
  agent presence gets an opaque id shaped like a `session_id`
  (`server/websocket.py:420`) and rides `player_join`, `player_move` and
  `player_leave`; `agent_talk` lines go out as `chat`; `agent_encounter` retires.
- **Live notices match a human doing the same thing.** A cast visit's
  `AGENT_VISIT` is recorded and its pressure applies, but its `causal_event` is
  not sent, as a human move sends `player_move` alone. A cast act sends
  `scale_act` then the `causal_event` with `action_notice: true`, as `/act`
  does. Destabilizer decay, which no human verb causes, keeps its frame without
  `agent` and `persona`, like the pump's anonymous staged frames
  (`server/heartbeat.py:598-607`). Ambient puzzle notices end with ADR-036 D5.
- **Served history** (`/chronicle`, `/history`, any view serving rows to
  players). A read projection drops `agent`, `persona`, `a_persona`,
  `b_persona` and the raw `actor` (no client reads it), serves the cast name in
  `player`, serves `AGENT_VISIT` as `PLAYER_MOVE` and aliases `AGENT_TALK` and
  `AGENT_VOICE` to types both kinds share; `static/clientlogic.js:249` and
  `:273` follow. Stored rows never change (`multiverse/history.py:23-27`).
- **Oracles.** `/register` and the keyless join answer a reserved name with
  the taken-name line (operator CLI messages may stay explicit). The `Observer`
  utility walk stops entering room presence.
- **Prompts.** The premise in every bible, place voices included, stops naming
  the cast as a class (`consciousness/__init__.py:342-346`); the agent bible
  drops "other agents or players" and the colleagues list (`:419-420`,
  `:520-523`). The history block renders rows through the served projection
  above, so "agent visit, by Tessera" (`:845`, `:868`) reads as a move. Any
  traveler is spoken of by name and temperament, never kind; the general
  "humans and AI agents alike" (`:322`) labels no one and may stay.
- **Names: keep the twelve.** Registered names are unique free text up to 32
  characters (`server/handlers.py:1603`), so "The Locksmith" passes as a handle
  once the guide stops listing the cast. After the first production boot a
  rename needs an alias table and a migration (#156, finding 1); any rename
  lands in batch 2, in `consciousness.WANDERER_CAST` and `agents/roster.py`.
- **Not hidden: behaviour.** Agents write no arrival rows, walk in paced bursts,
  cause decay no human can and answer at model latency; nothing disguises that.

### D5. The guardrails as requirements

**(a) Agents never claim to be human.** Asked sincerely (are you human, a bot,
an AI, a real person), an agent says plainly, in character but unambiguously,
that it is an AI: the honesty batch's deterministic authored answer with its
model instruction as backup, reused unchanged, on the chat path before any
model call, charge or output screen, AI on or off, exempt as D3 says. This
record does not design them; the place-voice line
(`consciousness/__init__.py:386`) stays as that batch leaves it. A
model-written line that claims to be human is dropped and counted: "I am" or
"I'm" followed within three words by human, a person, a real person, not an
AI or not a bot, or "my" before a fixed off-world term (job, boss, office,
school, wife, husband, kids, apartment, phone, timezone). "Body" and "home" are
not on it: "a celestial body" and an agent's home scales are this world's words.

**(b) A world-level notice at entry and in the guide.** The honesty batch's
copy wins if it has one; otherwise, for the `/app` intro, the map's entry and
the guide: "Some travelers are AI, and you won't always be able to tell. Ask
one if they're human: an AI will tell you the truth." The guide's "You are not
alone" section becomes one paragraph agreed with ADR-036 D7, keeping its
"Solving is better together: a puzzle that is tired of you will still hear a
friend.", naming no cast member, and saying how to talk to a traveler: start a
chat line with their name.

**(c) No solicitation.** An agent never asks for a real name, age, location,
contact details, an account, money or a meeting outside the world, and never
frames the relationship romantically; the agent bible says so. A deterministic
output check first rewrites each whole stored node name in the line to its
display name (`multiverse/utils.py:17`), because agents are told the stored
name (`consciousness/__init__.py:1148`): 3929 of seed 382's 4208 stored names
hold a 7-digit run under the screen's rule (`content_screen.py:203`, `:238`);
after the rewrite a line naming each one holds none and passes the screen's
local tier (*executed* 05:06:04Z, 05:13:36Z). The rewritten line is what is checked,
screened, sent and stored. The check drops a line holding a URL or bare
domain, an email address, a phone-shaped run (7 to 15 digits once spaces,
dashes, dots, parentheses and a leading `+` are removed) or a phrase from a
fixed solicitation list. It prefers silence to doubt.

**(d) Mute and report treat agents exactly as humans; only operator tools
record who is who** (not built: checklist C7, S3). One control on every
traveler row and chat line. Mute hides a traveler's lines and presence from the
muter, whatever their kind (if checklist question 3 is answered otherwise, both
kinds follow), and a muted agent never answers or greets the muter. A report
goes to the same operator queue; only the operator view shows the kind. A
per-agent chat switch lets the operator silence one.

**Covenant text** (proposed; `AGENTS.md` changes with batch 2):

- Replace "The chronicle blurs; live presence may distinguish" with
  "**No player-facing surface carries a human-or-agent label, and no agent
  pretends.** One ledger voices traces the same way, and `/chronicle`,
  `/history` and live frames carry no actor-kind flag. Only operator tools
  record who is who; the stored `agent` key stays for them and the agent-solve
  covenant. Truth is the one exception: an agent never claims to be human, and
  asked sincerely says plainly that it is an AI, AI on or off (ADR-037)."
- In "Extend or replace an experience": "New action capabilities belong in
  Act, speech to a place in Speak, conversation with travelers, human or agent,
  in chat, and history in its existing views."
- In "Agent solves don't count as human progress", add "An agent never submits
  a puzzle answer; it may suggest one to a human who asked for its help, and
  the attempt is the human's." Final wording follows ADR-036.

### D6. Cognition and cost

- **What leaves the server**, only on a trigger: the line; up to six recent
  exchanges between that player and that agent (30 minutes); the place and
  memory blocks `voice_agent` builds today; and up to ten node-history rows
  minus every row quoting a player's words (`PLAYER_CHAT`, `PLAYER_SPEAK`,
  `AGENT_VOICE`), so another player's untriggered line never leaves on someone
  else's trigger. Under trigger 3, each line of a player chatting beside an
  agent in a quiet world leaves, within the caps. `/speak`'s quoting is not
  changed here. Chat text to the inhabitant-voice provider is a new
  destination ([ADR-034](ADR-034-provider-and-model-optionality.md) Decision 5).
  #156 records [packet decision 10](../roadmap/decision-packet-2026-11.md#10-player-text-destinations-s2)
  as a policy the owner set on 2026-11-07; this record has not confirmed it and
  does not rely on it, and naming the destination (L3) and the terms check
  (L4) are open there.
- **Spend.** Each reply is one inhabitant-voice call charged, as `/agent/voice`
  is today, to the triggering player (the voice allowance's global and
  per-user caps and the model-action cap, `server/guard.py:71`, `:75`, `:114`),
  plus at most one classify for its screen. An agent-chat sub-cap counts both;
  starting values to measure: **200** replies a day world-wide and **40** per
  player, in #153's neutral scheme. Agent-line classifies spend the global
  moderation budget, not the player's own 60 classifies and 600 screened lines
  a day (`server/guard.py:94`, `:105`), so agent replies never get the
  player's own lines held. The E2 dollar ceiling
  ([packet decision 11](../roadmap/decision-packet-2026-11.md#11-dollar-spend-ceiling-e2)),
  still open, sits above all of these.
- **Allowance spent, provider busy, or a failure:** one authored deferral in
  the agent's own voice, once per agent per player per UTC day, then silence.
  Never `guard.QUIET_RESPONSE` (`server/guard.py:958`), which tells a newcomer
  to come back tomorrow (#156, finding 8).
- **AI off** (the kill switch, or no provider): agents still walk, banter and
  greet, and give the honesty answer, the deferral and ADR-036's authored
  puzzle line, at no charge. Every model call is caused by one human line.
- **Moderation.** A model-written agent line is shared text: its display-name
  form passes the human line's screen (a new `agent_chat` surface), failing
  closed (`server/moderation.py:183-241`), so a hold or block means no line
  and no row. Authored lines are vetted and not screened.

### D7. Puzzle collaboration

This record owns what opens a collaboration and where its replies go; ADR-036
D5 owns the puzzle view in agent context, the AI-off puzzle line and the end of
ambient attempts. The two records' batch 4 is one batch.

- **The human proposes, explicitly.** A line addressing an agent (D3) at a
  place with an open puzzle, with a help or solve verb aimed at the puzzle by a
  fixed pattern ("help me with this puzzle", "can you solve the riddle?"), is
  offered puzzle context; with AI on the model then judges whether help was
  asked for (ADR-036 D5), and with AI off the pattern alone opens ADR-036's
  authored line. A sincere honesty question never opens one. It covers that
  player, agent and puzzle epoch for 15 minutes. An agent never offers first.
- **Same clues.** The prompt carries the puzzle as served to that player: the
  question, the hints that player has unlocked and the evidence snapshot;
  never the answer or anything derived from it (normalized form, length,
  near-miss scores, ADR-036's warmth). Suggestions are the agent's own guesses
  and can be wrong. The context is never shown to another player, written to
  `agent_memory` or carried past a renewal; the help lives in the conversation
  (its lines and D8's buffer), as this record reads ADR-036 D5's "its memory".
- **Where replies go is the owner's (open question 4).** From the clues an
  agent will sometimes reach the right answer (*inferred*). As ordinary chat
  that line goes world-wide into a `PLAYER_CHAT` row `/chronicle` serves, so
  anyone could open the seal, undoing what the code protects: only a wrong
  guess is stored, and ADR-036 D3 stores no warmth band for the same reason.
  *Recommended:* replies reach only the collaborator and are not stored, which
  needs direct messages humans can send too (checklist open question 2), or
  the private line is itself a label.
- **Never submits.** No agent path reaches `/puzzle/attempt`, the shared pool
  or the contributor set. The human types and submits, so the attempt, and a
  solve, are the human's (every player owns their actions); a puzzle's
  temperament under ADR-036 answers the human. ADR-036 D5 retires the
  heartbeat's dice; chat never adds an attempt. The agent bible's puzzle
  paragraph (`consciousness/__init__.py:515-518`) is rewritten in batch 4.

### D8. Storage and memory

- **Agent lines follow human chat.** Under ADR-004 §6 as it stands, a full
  `PLAYER_CHAT` row: `player_name` and `actor_identity` set to the agent's
  name, data `{"text", "agent"}`, and a provenance row on a model-written line
  (operator read only, `persistence/__init__.py:852-856`). If S5
  ([packet decision 1](../roadmap/decision-packet-2026-11.md#1-s5-chat-permanence),
  open) takes chat out of the chronicle, agent lines leave with it. Served
  under D4; redactable like a human's (`persistence/__init__.py:917`).
- **Conversation memory** is a bounded in-memory buffer of screened lines per
  room, not a chronicle read, so it works under every S5 option and is lost on
  restart. No new table; `agent_memory` stays the discovery record, and
  ADR-032's `inhabitant_memory` stays ADR-032's.
- **Operator counts** keep agent lines apart from human chat, after #155.
- **Doors at implementation.** Batch 3a adds a `persistence.record_mutation`
  call site, a new write path needing the owner's sign-off at merge, unless S5
  removes chat storage first. Batches 1 to 4 need no migration; mute and
  report (C7) need their own. A cast rename is a first-production-boot door.

## Implementing batches

| Batch | Scope | Behaviour tests it needs | Doors |
|---|---|---|---|
| **1. Honesty** | Built on `claude/agent-honesty-guardrails` | A sincere question gets the authored answer with AI on, the kill switch on and no provider, with no model call (spy), from an agent and a place voice; a mention such as "the human scale" gets none | As that branch states |
| **2. De-label** | D1; D4 clients, wire, live notices, served projection, oracles, place-voice premise, names; D5(b); the copy sweep and visual-language paragraph; the covenant text | A cast walk and a human session that move, act and chat alike give equal frame types, key sets and shared feed text; `/chronicle` and `/history` rows for a cast act and a human act have equal key sets and served types, while the stored row keeps `agent` and the co-op and seal exclusions hold; within each client a cast row and a human row differ only in name and place (Vitest); `inhabitants.spec.js` updated (Playwright); `/register` and the keyless join answer a reserved name as a taken one; no composed place prompt names more than one cast member over an empty history, or says "agent visit" over a cast visit's row; Speak offers only the place | None, unless names change (first-boot door) |
| **3a. Agents in chat, authored** | D2; D3; honesty answer, greeting, deferral and banter as chat lines; no model | Each trigger fires and each non-trigger does not, including "karst formations here?" and a line addressing a human and an agent; two agents addressed give one reply; the honesty answer goes out while the agent is paced and past the bound, and a repeat reaches only the asker with no row; no trigger or greeting reads the human count; a held line and an agent line trigger nothing; one greeting; the same with AI off; lingerers leave with the last human; ADR-022 counters unchanged | New write path (agent chat rows), unless S5 removes chat storage |
| **3b. Model replies, flag off by default** | D6; D5(a) and (c) checks; agent-bible de-label; keeper commitments | Flag off: zero provider calls (spy); untriggered lines: zero, and another player's line absent from every request; caps spent: one deferral, then silence; agent-line classifies leave the player's moderation allowance untouched; screen hold: no frame, no row; URL, email, phone-run, solicitation and human-claim lines dropped, while every stored node name of seed 382, "a celestial body" and "my home scale" pass; no composed agent prompt lists the cast or says "agents or players" | L3, L4 and E2 closed before the flag is on for outside players; no migration |
| **4. Collaboration** (with ADR-036 batch 4) | D7 | No puzzle context without an explicit request, and none from a sincere question at a puzzle place; under the recommended delivery the answer string is absent from every provider request, broadcast frame and stored row across the puzzle families; no `PUZZLE_ATTEMPT` row or pool change from any chat path; the human's attempt lists only the human; a second player gets none of the first's context | Depends on ADR-036 and open question 4 |

Batches 2 and 3a reach any deployed build together, so the cast stays addressable.

## Trade-offs accepted

- Kind stays inferable from behaviour and patterns, and the honesty answer
  reveals it on request; the guarantee is the truth when asked, not disguise.
- Talking to an absent agent's trace ends; ordinary agent replies are as public,
  and under S5 as permanent, as any chat line.
- Lingerers fill presence (two at most). Agent chat spends voice and moderation
  budget within its sub-cap; trigger 3 sends each line of a player in a quiet
  world; the output checks prefer silence to a doubtful line.

## Revisit when…

- A tester felt deceived, or testers who asked still could not tell → revisit
  the notice's prominence (labels only if the owner reopens them).
- S5, L3, L4, E2 or checklist open question 2 is decided → D8, D6 or D3 follows.
- Agent lines exceed an agreed share of chat, or agent spend hits its sub-cap
  on most days → tighten the triggers.
- ADR-032 is revised or external visitor agents arrive → they follow D4 and D5.
- ADR-036 is ratified → D7's wording and the agent-solve covenant text follow.

## Rejected alternatives

- **Labels.** Rejected by the owner on 2026-11-06.
- **Speak-only agents.** A separate surface for agent conversation is itself a
  label, and it gives no company where people talk.
- **Humans addressable in Speak.** Two composers for one purpose.
- **Model-free canned chat agents.** No destination or spend, but they cannot
  work a puzzle from its clues or hold a conversation, so both of the owner's
  reasons fail. Kept as the AI-off floor.
- **Agents read every chat line:** all player text to a provider, cost growing
  with chat; trigger 3's quiet-world case is the bounded exception. **A new
  `AGENT_CHAT` row type:** a stored kind flag every reader must alias.
  **Typing delays:** disguise beyond "won't always be able to tell".

## Open questions for the owner

1. **Should one or two AI travelers stay around whenever a person is online,
   so there is always someone to talk to?** Today each is visible a few seconds
   every three minutes. *Recommended: yes, at most two.*
2. **Should all talking to AI travelers happen in chat, with Speak only for
   places?** This ends talking to a traveler who is not there. *Recommended:
   yes.*
3. **Keep the twelve names (Tessera, Aunt Entropy, The Locksmith,
   Cartographer-9 …), or rename them to look like ordinary player names?**
   Renaming is free only until the real world first starts. *Recommended: keep.*
4. **When an AI traveler helps you with a puzzle, should only you see its
   suggestions?** If everyone sees them, a right answer it suggests becomes
   public and stays in the world's history, so anyone could open that puzzle.
   *Recommended: only you, and not kept; that needs private messages between
   people too, so that a private line does not give the AI away.*
5. **If someone asks "is anyone here an AI?", should every AI traveler at that
   place say so?** That reveals all of them there at once. *Recommended: yes,
   only those at the asker's place.*

## What this ADR does not decide

S5, S2 (#156 records a 2026-11-07 policy for it, with L3 and L4 open), E2 and
the watch timing. ADR-036 owns puzzle temperament, near-miss hints, renewal,
ambient attempts and the AI-off puzzle line; the honesty batch owns the
sincere-question detector, its answer and the fourth-wall rewrite. ADR-032
stays Proposed. Juries and governance stay the owner's.
