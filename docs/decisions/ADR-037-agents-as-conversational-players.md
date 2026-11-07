# ADR-037: Agents as conversational players — addressed in chat, unlabeled, honest

**Status:** Proposed, 2026-11-07. **Owner:** Mark Weeks. Records the owner's
2026-11-06 decisions on agent disclosure and structural parity, and his
2026-11-07 answers, designed against `main` at `f3ead74`. **Not ratified.** No
code, migration, write path, player-text destination, spend or deployment;
citing it authorizes nothing.

It depends on three records not on `main`, named rather than linked: #156
(the 2026-11-06 decisions in `docs/evaluation/2026-11-06-next-build.md`, and
checklist A1 rewritten); the honesty batch on `claude/agent-honesty-guardrails`;
and ADR-036 (puzzle temperament, Proposed, `claude/adr-036-puzzle-temperament`).
Neither branch was readable here, so their parts are stated as dependencies.
Evidence is *executed*, *read* (each `file:line` re-read at `f3ead74`) or
*inferred*. #153 merged after this base (`3200eed`), moving only the cited
`server/guard.py` lines and `consciousness/__init__.py:829-877` (two lower).

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
| Chat | Screened, then broadcast to every socket in the room and stored as `PLAYER_CHAT`; nothing else reads it. One room per seed and one canonical world ([ADR-007](ADR-007-one-shared-launch-world.md)) make chat world-wide | `server/websocket.py:605-649`, `server/rooms.py:145-149`, `:177-189` (read) |
| Talking to agents | Speak lists up to four names found in `/history` `data.agent` at this place, present or not, and posts to `/agent/voice`; only the asker sees the reply | `frontend/src/components/Interact.jsx:52-69`, `:79-95`; `static/explorer.js:737-756`, `:769-777`; `server/handlers.py:1464-1548` (read) |
| Presence | The welcome frame sends `players` and `agents` as two lists; `agent_enter` carries a persona; heartbeat `causal_event` frames carry `agent` and `persona`, a human's neither; cast talk is its own `agent_talk` frame; `agent_done` says "Agent" | `server/websocket.py:447-454`, `server/rooms.py:192-200`, `:232-238`, `server/heartbeat.py:277-284`, `:400-404`, `frontend/src/App.jsx:343`, `static/explorer.js:1207-1208` (read); frame keys *executed* (probe below) |
| Traveler rows | Humans get ◈ (`/app`) or ◆ (map); the cast gets ✦, a persona tag, another ring colour and dash, and the accessible name "Inhabitant", as the visual-language doc specifies | `frontend/src/components/TextPanel.jsx:47-48`, `static/explorer.js:990`, `:1303-1320`, `:1384`; [visual language](../design/visual-language.md) lines 206-208 (read) |
| Presence time | A walker is present only while it walks | *Executed* 2026-11-07T04:12:25Z–04:13:01Z: four heartbeat ticks on a scratch seed-382 database at the default 1.2 s pace were present 1.21, 3.67, 6.08 and 12.05 s. At the default 180 s interval (`server/heartbeat.py:55`) one walker is visible at most about 7% of the time (*inferred*) |
| Served history | `/chronicle` serves stored data plus raw `actor_identity` as `actor` | `server/handlers.py:977-993`, `persistence/__init__.py:1101` (read). *Executed*, same probe: 18 `AGENT_VISIT` rows served data keys `agent` and `persona` and no `actor`; a keyed human's chat row served a 16-hex `actor`. Cast acts store the name as `actor_identity` (`server/heartbeat.py:198-200`); talk rows store `a_persona`, `b_persona` (`:271-276`) (read) |
| Kind oracles | `/register` refuses a cast name with 403 "belongs to the world", a taken name with 409; `/agent/voice` voices only server-owned names; an `/observe` walk enters room presence as `Observer` | `server/handlers.py:1613-1617`, `:1635-1639`, `:1483-1514`, `:1709`, `:1791` (read) |
| Prompts | "Never break the fourth wall or reveal that you are an AI" in the place and agent bibles; agents told not to ask whether a visitor is human; agents "attempt puzzles under the same rules as any traveler"; the world premise names all twelve | `consciousness/__init__.py:386`, `:421`, `:544-546`, `:515-518`, `:342-345` (read) |
| Guide | Names the cast; the panel shows "humans and the cast alike" | `static/guide.html:108-122` (read) |
| Output | `/agent/voice` screens the player's message, not the reply, and stores both | `server/handlers.py:1515-1520`, `:1540-1548` (read) |
| Puzzles | Walkers roll dice against difficulty and write `PUZZLE_SOLVED`/`PUZZLE_FAILED`; the stored `agent` key keeps those rows out of co-op sessions and seals | `server/heartbeat.py:481-490`, `persistence/__init__.py:682`, `:1313` (read) |

The stored `agent` key must stay: the agent-solve covenant reads it, and
`agent_memory`, `agent_runs` and `AGENT_VISIT` are keyed by the unredactable
name (`agents/identities.py:3-6`, read). The heartbeat makes no model call
(`server/heartbeat.py:18-19`; [ADR-022](ADR-022-m4-responsive-inhabitants.md):
"No language-model loop"). [ADR-032](ADR-032-inhabitant-cognition.md)
(Proposed) would put inhabitant speech in Speak (D2, D5), persona-tag visitor
agents (D6) and have inhabitants answer puzzles (D4); the owner's decisions
depart from those parts, so ADR-032 needs revising before ratification.

## Decision

### D1. One surface: travelers in chat, places in Speak

Every traveler, human or agent, is talked to in chat; Speak is speech to a
place. Speak's agent targets, both clients' calls to `/agent/voice` and the
endpoint's player route retire (it answers only cast names). The keeper
commitments it retrieves (`keeper_history`, [ADR-025](ADR-025-first-situation.md))
move into the chat reply's context. Talking to an absent agent's trace ends.

### D2. Presence that can keep company

While a human is connected, up to **two** agents linger where their last walk
ended, as live presence only: no row, visit or attention marker, and no change
to ADR-022's caps; a third may be walking. Lingerers rotate with the heartbeat
and leave when the last human does. Without this, "even if there are no other
human players logged in" finds nobody about 93% of the time (*inferred*).

### D3. When an agent answers, and how often

Triggers are local and deterministic, on a human line that passed the screen:

1. **Named:** the line names a present agent, compared by
   `persistence.name_key` at word boundaries. The first agent named answers.
2. **A question at its place:** the line ends in `?`, names no one, and the
   sender stands where exactly one present agent stands.
3. **Company:** exactly one human is connected and the line names no one. The
   agent that answered them in the last two minutes answers, else one at their
   place.

Never a trigger: an agent's line, a line naming a human, a held or declined
line (it reaches nobody, `server/websocket.py:623-626`), or a line from a player
who muted that agent (D5d).

**Bounds.** At most one agent line per human line. The exception is a sincere
question to nobody in particular ("is anyone here an AI?"): each present agent
gives the honesty answer and nothing else. Each agent speaks at most once per
8 s, within D6's caps. Agents never answer each other through a model; cast
talk stays the authored banter (`agents/banter.py`), sent as chat lines (D4).

**Initiation.** A human alone for 60 s gets one authored greeting from a
present agent (once per agent per player per connection, at most one
unsolicited line per player per ten minutes): no cost, works with AI off.
ADR-032 D5's model-written unsolicited speech is not adopted.

**Delivery.** An agent's line is an ordinary `chat` frame on a human's
broadcast, so world-wide today; if checklist
[open question 2](../roadmap/beta-launch-checklist.md#open-questions-for-mark)
makes chat place-local, agents follow. No delay imitates typing. A model reply
runs on a bounded worker, never the sender's socket thread; a full queue drops
the trigger.

### D4. No labels

What any player receives treats both kinds alike; operator tools keep the kind.

- **Clients.** Every traveler row takes the glyph, ring colour and ring style
  each client gives a human today, no persona tag, and one accessible name,
  "Traveler"; the `agent_done` notice leaves the feed; the visual-language
  paragraph follows.
- **Wire.** One welcome list, `players`, with the same keys for both kinds; an
  agent presence gets an opaque id shaped like a `session_id`
  (`server/websocket.py:420`). Agent presence rides `player_join`,
  `player_move` and `player_leave`; `agent_talk` lines go out as `chat` frames;
  `agent_encounter` retires (the talk that follows is the encounter); heartbeat
  `causal_event` frames drop `agent` and `persona`.
- **Served history** (`/chronicle`, `/history`, any view serving rows to
  players). A read projection drops `persona`, `a_persona`, `b_persona` and the
  raw `actor` (no client reads it; grep of `frontend/src` and `static`), serves
  the cast name in `player`, and aliases `AGENT_VISIT`, `AGENT_TALK` and
  `AGENT_VOICE` to served types both kinds share; `static/clientlogic.js:249`
  and `:273` follow. Stored rows never change; `multiverse/history.py:23-27`
  already refuses to infer a taxonomy from them.
- **Oracles.** `/register` answers a reserved name with the taken-name 409
  line (operator CLI messages may stay explicit). The `Observer` utility walk
  stops entering room presence.
- **Names: keep the twelve.** Registered names are unique free text up to 32
  characters (`server/handlers.py:1603`), so "The Locksmith" passes as a handle
  once the guide stops listing the cast. A rename is free only before the
  first production boot, after which the heartbeat has written rows and memory
  keyed by these names (#156, finding 1) and a rename needs an alias table, a
  migration. Any rename lands in batch 2, in `consciousness.WANDERER_CAST` and
  `agents/roster.py` together (`tests/test_roster.py` pins them).
- **Not hidden: behaviour.** Agents write no arrival rows, walk in paced bursts
  and answer at model latency; nothing synthetic disguises that.

### D5. The guardrails as requirements

**(a) Agents never claim to be human.** Asked sincerely (are you human, a
bot, an AI, a real person), an agent says plainly, in character, that it is an
AI. That is the honesty batch's deterministic authored answer with its model
instruction as backup, reused unchanged: its detector and answer run on the
chat path before any model call, charge or output screen, AI on or off. This
record does not design them. Also, a model-written line that claims to be
human, or a human life outside the world (a job, a home, a body), is dropped
and counted. The place-voice line (`consciousness/__init__.py:386`) stays as
the honesty batch leaves it.

**(b) A world-level notice at entry and in the guide.** The honesty batch's
copy wins if it has one; otherwise, for the `/app` intro, the map's entry and
the guide: "Some of the travelers you meet are AI, and you won't always be
able to tell. Ask one whether it is human: an AI traveler always answers
truthfully." The guide's "You are not alone" section
(`static/guide.html:108-122`) is rewritten to match, names no cast member, and
says how to talk to a traveler: say their name in chat.

**(c) No solicitation.** An agent never asks for a real name, age, location,
contact details, an account, money or a meeting outside the world, and never
frames the relationship romantically. A rule in the agent bible states it; a
deterministic output check drops any line holding a URL, an email address, a
phone-shaped digit run or such a request. The check prefers silence to doubt.

**(d) Mute and report treat agents exactly as humans; only operator tools
record who is who** (not built: checklist C7, S3). One control on every
traveler row and chat line, the same for both kinds. Muting an agent hides its
lines and presence from the muter, and it never answers or greets the muter. A
report on an agent line goes to the same operator queue; only the operator
view shows the kind. A per-agent chat switch lets the operator silence one.

**Covenant text** (proposed; `AGENTS.md` is not edited here and changes with
batch 2):

- Replace "The chronicle blurs; live presence may distinguish" with
  "**Nothing a player receives tells human from agent, and no agent pretends.**
  Whether a trace, a presence or a chat line came from a human or an agent is
  left open on every player-facing surface: one ledger voices them the same
  way, and `/chronicle`, `/history` and live frames carry no actor-kind flag.
  Only operator tools record who is who; the stored `agent` key stays for them
  and for the agent-solve covenant. Truth is the one exception: an agent never
  claims to be human, and asked sincerely it says plainly that it is an AI,
  with AI on or off (ADR-037)."
- In "Extend or replace an experience": "New action capabilities belong in
  Act, speech to a place in Speak, conversation with travelers, human or agent,
  in chat, and history in its existing views."
- In "Agent solves don't count as human progress", add "An agent never submits
  a puzzle answer; it may suggest one to a human who asked for its help, and
  the attempt is the human's." Final wording follows ADR-036.

### D6. Cognition and cost

- **What leaves the server**, only on a trigger: the line, up to six recent
  exchanges between that player and that agent (30 minutes), and the place and
  memory blocks `voice_agent` builds today, whose node history already quotes
  chat (`consciousness/__init__.py:829-877`). Untriggered lines never leave.
  Chat text to the inhabitant-voice provider is a new destination
  ([ADR-034](ADR-034-provider-and-model-optionality.md) Decision 5): it waits
  on S2 ([packet decision 10](../roadmap/decision-packet-2026-11.md#10-player-text-destinations-s2)), still open.
- **Spend.** Each reply is one inhabitant-voice call, charged as `/agent/voice`
  is today to the triggering player: the voice allowance's global and per-user
  caps and the per-user model-action cap (`server/guard.py:71`, `:75`, `:114`,
  read). An agent-chat sub-cap keeps agent chat from draining Speak; starting
  values to measure, not decided: **200** replies a day world-wide, **40** per
  player, named in #153's neutral scheme (`NESTED_WORLDS_VOICE_DAILY_CALLS`
  and its `_PER_USER` twin for the voice allowance). The E2
  dollar ceiling ([packet decision 11](../roadmap/decision-packet-2026-11.md#11-dollar-spend-ceiling-e2)),
  still open, sits above all of these.
- **Allowance spent, provider busy, or a failure:** one authored deferral in
  the agent's own voice, once per agent per player per UTC day, then silence.
  Never `guard.QUIET_RESPONSE` (`server/guard.py:958`), which tells a newcomer
  to come back tomorrow (#156, finding 8). The honesty answer still holds.
- **AI off** (the kill switch, or no provider): agents still walk, banter,
  greet, and give the honesty answer and the deferral, at no charge. Every
  model call is caused by one human line; the heartbeat stays model-free.
- **Moderation.** A model-written agent line is shared text: it passes the
  human line's screen (a new `agent_chat` surface) and fails closed, so a hold
  or block means no line and no row. Its classify calls charge the triggering
  player's moderation allowance. Authored lines are vetted and not screened.

### D7. Puzzle collaboration

Follows the owner's 2026-11-07 answer; where ADR-036 decides, it wins.

- **The human proposes.** A collaboration opens when a player at a place with
  an open puzzle names an agent in a line that asks for help or mentions the
  puzzle (a local word check: help, puzzle, riddle, question, answer, solve).
  It covers that player, agent and puzzle epoch for 15 minutes. An agent never
  offers first.
- **Same clues.** The prompt carries the puzzle as served to that player: the
  question, the hints that player has unlocked and the evidence snapshot.
  Never the answer or anything derived from it (normalized form, length,
  near-miss scores, ADR-036's warmth). Suggestions are the agent's own guesses
  and can be wrong. The context is never shown to another player, kept in agent
  memory or carried past a renewal.
- **Never submits.** No agent path reaches `/puzzle/attempt`, the shared pool
  or the contributor set. The human types and submits, so the attempt, and a
  solve, are the human's (every player owns their actions), as after another
  human's tip; a puzzle's temperament under ADR-036 answers the human.
- **Autonomous attempts.** "do not solve puzzles independently" bears on the
  heartbeat's dice attempts (`server/heartbeat.py:481-490`). Whether they
  retire is ADR-036's decision; this record requires only that chat never adds
  an attempt. The agent bible's puzzle paragraph
  (`consciousness/__init__.py:515-518`) is rewritten in batch 4.

### D8. Storage and memory

- **Agent lines follow human chat.** Under ADR-004 §6 as it stands, that is a
  full `PLAYER_CHAT` row: `player_name` and `actor_identity` set to the agent's
  name, data `{"text", "agent"}`, and provenance columns on a model-written
  line. If S5 ([packet decision 1](../roadmap/decision-packet-2026-11.md#1-s5-chat-permanence),
  open) takes chat out of the chronicle, agent lines leave with it. Served under
  D4; the text is redactable like a human's (`persistence/__init__.py:917`).
- **Conversation memory** is an in-memory, bounded buffer of screened lines per
  room, not a chronicle read, so it works under every S5 option and is lost on
  restart. No new table; `agent_memory` stays the discovery record, and
  ADR-032's `inhabitant_memory` stays ADR-032's.
- **Operator counts** keep agent lines apart from human chat, after #155
  (which owns `scripts/beta_metrics.py` today).
- **Doors at implementation.** Batch 3a adds a `persistence.record_mutation`
  call site, a new write path needing the owner's sign-off at merge, unless S5
  removes chat storage first. Batches 1 to 4 need no migration; mute and
  report (C7) need their own. A cast rename is a first-production-boot door.

## Implementing batches

| Batch | Scope | Behaviour tests it needs | Doors |
|---|---|---|---|
| **1. Honesty** | As built on `claude/agent-honesty-guardrails` | As that branch defines | As that branch states |
| **2. De-label** | D1 (Speak place-only; the `/agent/voice` player route retired); D4 clients, wire, served projection, oracles, names; D5(b); the visual-language paragraph; the covenant text | Welcome and presence frames for a walker and a human have equal key sets; `/chronicle` and `/history` rows for a cast act and a human act have equal key sets and served types, while the stored row keeps `agent` and the co-op and seal exclusions hold; both clients render identical row markup (Vitest); `inhabitants.spec.js` updated (Playwright); `/register` answers a reserved name as a taken one; Speak offers only the place | None, unless names change (first-boot door) |
| **3a. Agents in chat, authored** | D2; D3; honesty answer, greeting, deferral and banter as chat lines; no model | Each trigger fires and each non-trigger does not; two agents named in one line give one reply; a held line triggers nothing; an agent line never triggers; one greeting; the same with AI off; lingerers leave with the last human; ADR-022 counters unchanged | New write path (agent chat rows), unless S5 removes chat storage |
| **3b. Model replies, flag off by default** | D6: worker, context, caps, output screen, solicitation and human-claim checks, keeper commitments | Flag off: zero provider calls (spy); untriggered lines: zero; caps spent: one deferral, then silence; screen hold: no frame, no row; URL, email, digit-run and human-claim lines dropped; a sincere question answered with no call | S2 and E2 decided before the flag is on for outside players; no migration |
| **4. Collaboration** | D7 | The answer string is absent from every provider request across the puzzle families; no `PUZZLE_ATTEMPT` row or pool change from any chat path; the human's attempt lists only the human; no puzzle context without the proposal; a second player gets none of the first's | Depends on ADR-036; none of its own |

Batches 2 and 3a reach any deployed build together, so the cast stays addressable.

## Trade-offs accepted

- Kind stays inferable from behaviour and row patterns; the guarantee is the
  truth when asked, not perfect disguise.
- Talking to an absent agent's trace ends, and agent replies are as public as
  any chat line. If S5 keeps chat permanent, they are as permanent too.
- Lingerers fill presence (two at most). Agent chat spends the voice allowance,
  bounded by the sub-cap; the output checks prefer silence to a doubtful line.

## Revisit when…

- A watch or cohort tester felt deceived, or testers who asked still could not
  tell → revisit the notice's prominence (labels only if the owner reopens them).
- S5, S2 or E2 is decided → D8, D6's destination, or D6's caps follow.
- Checklist open question 2 is decided → D3's delivery follows.
- Agent lines exceed an agreed share of chat, or agent spend hits its sub-cap
  on most days → tighten the triggers.
- ADR-032 is revised or external visitor agents arrive → they follow D4 and D5.
- ADR-036 is ratified → D7's wording and the agent-solve covenant text follow.

## Rejected alternatives

- **Labels.** Rejected by the owner on 2026-11-06.
- **Speak-only agents.** A separate surface for agent conversation is itself a
  label, and it gives no company where people talk.
- **Humans addressable in Speak.** Two composers for one purpose, since chat
  exists; Speak's reply is a private request and response.
- **Model-free canned chat agents.** No S2 or E2 dependency, but they cannot
  work a puzzle from its clues or hold a conversation, so both of the owner's
  reasons fail. Kept as the AI-off floor.
- **Agents read every chat line:** all player text to a provider, cost growing
  with chat. **A new `AGENT_CHAT` row type:** a stored kind flag every reader
  must alias. **Typing delays:** disguise beyond "won't always be able to tell".

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
4. **Should everyone online see an AI traveler's replies, as everyone sees all
   chat today?** *Recommended: yes; if chat becomes local, both change.*

## What this ADR does not decide

S5, S2, E2 and the watch timing stay open. ADR-036 owns puzzle temperament,
near-miss hints, renewal and ambient attempts; the honesty batch owns the
sincere-question detector, its answer and the prompt rewrite. ADR-032 stays
Proposed. Juries and governance stay the owner's.
