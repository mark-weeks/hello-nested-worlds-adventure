# ADR-037: Agents as conversational players — addressed in chat, unlabeled, honest

**Status:** Proposed, 2026-11-07; revised 2026-11-10. **Owner:** Mark Weeks.
**Not ratified.** No code, migration, write path, player-text destination,
spend or deployment; citing it authorizes nothing. Designed against `main` at
`f3ead74`.

**Decided by the owner and binding here:** agents are not labelled; an agent
never pretends to be human and says it is an AI when sincerely asked; agents
are addressable in chat (option (b)) for human-AI puzzle collaboration and
company; an agent never solves or submits a puzzle answer on its own, but may
suggest one when a human engages it and proposes collaboration; Enfolded data
goes to model providers only to facilitate game play and never trains
frontier models. **Everything else in this record is a proposal**, tied to an
open question for the owner or listed under "Defaults for the owner to veto".

It depends on open pull requests, cited by number and section: #156 (the
2026-11-06 decisions in `docs/evaluation/2026-11-06-next-build.md`); #158, the
honesty batch (`consciousness.honesty`); #159, ADR-036 (puzzle temperament);
and #161 (personal blocking). #158 and #159 are being revised in parallel;
where this record relies on a #158 interface not yet pushed, it says "planned
in #158". Evidence is *executed* (scratch seed-382 databases; `f3ead74` code
on 2026-11-07 and `3200eed` code on 2026-11-10; #158's detector at `9106160`
and `31f1bb8`, pinned only because it was run), *read* (each `file:line`
re-read at `f3ead74`) or *inferred*. #153 merged after this base (`3200eed`),
moving only the cited `server/guard.py` lines and `consciousness/__init__.py`
below line 668 (`:829-877` by two, `:1148` by three).

## Context

**The owner's decisions** (quoted words are Mark Weeks's, verbatim):

- *Disclosure, 2026-11-06:* "On #2, let's not label agents. It will be more
  interesting if it's not obvious which players are human and which are
  agents. That being said, there are probably some boundaries and guardrails
  that would be appropriate. For example, if a player asks an AI agent player
  'are you human?' the AI agent player should not pretend to be human." And
  "On 3, the recommended guardrails seem reasonable": guardrails (a) to (d),
  restated as requirements in D5.
- *Structural parity, 2026-11-06:* "On 2, I think the right approach is (b).
  My reasoning is that this would allow human-ai collaboration on puzzles. It
  would also give human players other players to interact with, even if there
  are no other human players logged in at the same time." Option (b), as #156
  records it: agents can be addressed in chat and answer there, and the guide
  stops naming the cast.
- *Puzzles, 2026-11-07:* "2. agents can suggest puzzle answers if a human
  engages with the agent and proposes collaboration. Agents do not submit
  puzzle answers". #156 records an earlier line of 2026-11-06: "I suggest that
  AI agents do not solve puzzles independently. However, they can cooperate
  with human players to help solve puzzles." His answer "1. an annoyed player
  generally gets grumpier toward all players, but especially the player(s)
  that are annoying it" is read by ADR-036 (#159, Context) as an annoyed
  *puzzle*; that reading is ADR-036's subject and **awaits the owner's
  confirmation**.
- *Providers, 2026-11-07:* "5. Information can only be shared with model
  providers to facilitate game play. Enfolded data must not be used to train
  frontier models." (D6.)

**What the code does today.**

| Area | Today | Evidence |
|---|---|---|
| Chat | Screened, broadcast to every socket in the room, stored as `PLAYER_CHAT`. One room per seed and one canonical world ([ADR-007](ADR-007-one-shared-launch-world.md)) make it world-wide | `server/websocket.py:605-649`, `server/rooms.py:145-149`, `:177-189` (read) |
| Talking to agents | Speak lists up to four names from `/history` `data.agent` at this place, present or not, and posts to `/agent/voice`; only the asker receives the reply live, but the exchange is stored as an `AGENT_VOICE` row that `/chronicle` and `/history` serve unfiltered and that later voices at that place are told about | `frontend/src/components/Interact.jsx:52-69`, `:79-95`; `static/explorer.js:737-756`, `:769-777`; `server/handlers.py:1464-1548` (row at `:1539-1548`); `consciousness/__init__.py:847-856` (read) |
| Presence | Welcome sends `players` and `agents` apart; `agent_enter` carries a persona; cast talk is `agent_talk`; `agent_done` says "Agent" | `server/websocket.py:447-454`, `server/rooms.py:192-200`, `:232-238`, `server/heartbeat.py:277-284`, `frontend/src/App.jsx:343`, `static/explorer.js:1207-1208` (read) |
| Live notices | A cast visit sends `causal_event` kind `AGENT_VISIT` with `agent` and `persona` and no narration, so both feeds print "↯ agent visit · …"; a human move sends `player_move` only. `/act` sends `scale_act` then a `causal_event` with `action_notice`; a cast act sends `scale_act` alone | `server/heartbeat.py:400-404`, `:478-480`, `server/websocket.py:587-596`, `server/handlers.py:1993-2005`, `server/heartbeat.py:210-215`, `multiverse/history.py:46-47`, `static/clientlogic.js:225-229`, `:298-302`, `frontend/src/App.jsx:309-311`, `static/explorer.js:1229-1231` (read). *Executed* 05:03:53Z, three ticks: 15 such frames; with `agent` and `persona` removed, `causalNoticeLine` still returned "↯ agent visit · Weathered Cinder Archipelago ×1.00" |
| Traveler rows | Humans get ◈ (`/app`) or ◆ (map); the cast gets ✦, a persona tag, another ring colour and dash, "follow" for "go to", "…arriving" for "—", and the accessible name "Inhabitant" | `frontend/src/components/TextPanel.jsx:47-48`, `static/explorer.js:990`, `:1303-1319`, `:1384`; [visual language](../design/visual-language.md) lines 206-208 (read) |
| Presence time | A walker is present only while it walks | *Executed* 04:12:25Z–04:13:01Z, four ticks at the default pace: present 1.21, 3.67, 6.08 and 12.05 s. At the default 180 s interval (`server/heartbeat.py:55`) one walker is visible at most about 7% of the time (*inferred*) |
| Served history | `/chronicle` serves stored data plus raw `actor_identity` as `actor` | `server/handlers.py:977-993`, `persistence/__init__.py:1101` (read); *executed*, same probe: 18 `AGENT_VISIT` rows served `agent` and `persona` and no `actor`, a keyed human's chat row a 16-hex `actor`; talk rows store `a_persona`, `b_persona` (`server/heartbeat.py:271-276`) |
| Kind oracles | `/register` refuses a cast name with 403 "belongs to the world", a taken one with 409; the keyless WS join (local mode) refuses a cast name the same way; an `/observe` walk enters presence as `Observer` | `server/handlers.py:1613-1617`, `:1635-1639`, `server/websocket.py:385-388`, `server/handlers.py:1709`, `:1791` (read) |
| Prompts | Every bible's premise names the twelve as "a recurring cast of wanderers"; the agent bible says "acknowledge other agents or players", calls all twelve, the speaker's own name included, "Other named wanderers" and colleagues, and says "When you meet another presence at a node — human or wanderer — the meeting is an event; the world records it."; "Never break the fourth wall or reveal that you are an AI"; agents do not ask whether a visitor is human, and "attempt puzzles under the same rules as any traveler" | `consciousness/__init__.py:342-346`, `:419-420`, `:520-523`, `:541-542`, `:386`, `:421`, `:544-546`, `:515-518` (read) |
| Agent context | `/agent/voice` passes node history whose block quotes every traveler's chat at that place word for word | `server/handlers.py:1527-1535`, `persistence/__init__.py:716-728`, `consciousness/__init__.py:868-877` (read); *executed* 05:05:33Z: another player's untriggered line appeared in the block |
| Guide and copy | Names the cast; "humans and the cast alike"; "address agents whose traces you find"; "Talk to other explorers"; the journal says "Inhabitants and other players" | `static/guide.html:108-122`, `:61`, `:64`; `static/journal.html:3` (read) |
| Puzzles | Walkers roll dice and write `PUZZLE_SOLVED`/`PUZZLE_FAILED`; the stored `agent` key keeps those rows out of co-op sessions and seals; only a wrong guess is ever stored | `server/heartbeat.py:481-490`, `persistence/__init__.py:682`, `:1313`, `server/handlers.py:2053-2066` (read) |

The stored `agent` key stays: the agent-solve covenant reads it, and
`agent_memory`, `agent_runs` and `AGENT_VISIT` are keyed by the unredactable
name (`agents/identities.py:3-6`). The heartbeat makes no model call
(`server/heartbeat.py:18-19`; [ADR-022](ADR-022-m4-responsive-inhabitants.md)).
[ADR-032](ADR-032-inhabitant-cognition.md) (Proposed) would put inhabitant
speech in Speak (D2, D5), persona-tag visitor agents (D6) and have inhabitants
answer puzzles (D4); the owner's decisions depart from those parts, so this
record asks that ADR-032 be revised before ADR-032 is ratified.

#161 (open; another coding agent's work, read at head `1c40cbb` with
`git diff 3200eed...origin/codex/block-travelers`) builds persistent personal
blocking for human and agent travelers: migration `0030_participant_blocks`,
checklist C7 to Partial, a server filter that works on the welcome's `agents`
list and the `agent_*` frames D4 retires, and an ADR-004 section that keeps "a
deliberate Speak request addressed through saved history" and says the feature
does not "make agents converse through world chat". D5(d) says how the two
reconcile.

## Decision

### D1. One surface: travelers in chat, places in Speak

*Proposed; awaits the owner (open question 2).* Every traveler, human or
agent, is talked to in chat; Speak is speech to a place. Speak's agent targets,
both clients' calls to `/agent/voice` and the endpoint's player route retire.
The keeper commitments it retrieves (`keeper_history`,
[ADR-025](ADR-025-first-situation.md)) move into the chat reply's context.
Talking to an absent agent's trace ends. If the owner agrees, this supersedes
#161's ADR-004 sentence keeping "a deliberate Speak request addressed through
saved history" for agents.

### D2. Presence that can keep company

*Proposed; awaits the owner (open question 1).* While a human is connected,
up to **two** agents linger where their last walk ended, as live presence
only: no row, visit or attention marker, and no change to ADR-022's caps; a
third may be walking. Lingerers rotate with the heartbeat
and leave when the last human does. Without this, "even if there are no other
human players logged in" finds nobody about 93% of the time (*inferred*).

### D3. When an agent answers, and how often

*Proposed: the address rule, triggers, bounds, honesty delivery and greeting
are defaults for the owner to veto; honesty delivery and the group answer are
also open question 5.*

A line **addresses** a traveler when it starts with their name followed by a
comma, colon, `?`, `!` or its end, or ends with a comma and their name (then
`?`, `!` or `.` at most), compared by `persistence.name_key`. "Karst, what is
this?" addresses Karst; "karst formations here?" addresses nobody, so the
dictionary-word names (Vex, Karst, Marginalia, Petrichor) do not fire. Only a
present traveler is addressed. A leading word that #158's detector reads as a
greeting or lead ("hey", "hi", "hello", "so", "ok" …) is skipped, not read as
a name, so "Hey Tessera, what is this?" addresses Tessera and "Hey, are you
human?" addresses no one. Registered names are free text that the local name
screen passes (`server/handlers.py:1601-1626`; `moderation.name_refusal`
returns nothing for "Hey", "Hi", "So" and "Please", *executed* 2026-11-10), so
a present human named "Hey" would otherwise turn "Hey, are you human?" into a
line to that human and silence every agent. Such a human is addressed by the
end form ("what do you think, Hey?").

**An identity question names its addressee.** Common ways of asking fail the
start/end rule: "Tessera are you human?" and "tessera r u a bot" address
nobody under it, though #158's `is_identity_question` accepts both (*executed*
at `9106160` and `31f1bb8`, 2026-11-10). "Hey Tessera, are you human?" failed
it too before the lead-word skip above, which now makes it address Tessera
(*executed* with the skip, 2026-11-10). So a line the detector accepts also
addresses a present agent whose name it holds: the detector is called once per
present agent with that agent's names, through #158's speaker-names argument
(`is_identity_question(text, own_names=...)`, pushed in #158 at `387e219`), under which a cast name that is not the speaker's own sends
the line down the normal path. The detector bounds the shape, so a name counts
here only in a greeting or aside slot.

Triggers are local and deterministic, on a human line that passed the screen:

1. **Addressed:** the line addresses a present agent; the first one answers.
2. **A question at its place:** it ends in `?`, addresses no one, and exactly
   one agent stands at the sender's place.
3. **Quiet company:** it addresses no one and the sender's surroundings are
   quiet; the agent that answered or greeted them in the last two minutes
   answers, else the agent at their place if it is alone.

**Quiet** means that in the last five minutes no line was sent at the player's
place or addressed them, other than their own and their last answerer's (the
agent that last answered or greeted them). A line sent elsewhere that
addresses someone else does not count, whoever sent it, so banter at another
place does not keep a player from company: a walk takes a companion on its
first visit with probability 0.35, or 0.7 where a place holds an NPC, and
holds one conversation per tick (`server/heartbeat.py:452`, `:459-464`).
The rule reads places and addresses, which players see, never a speaker's
kind; counting only human lines would make trigger 3 an agent detector.

Never a trigger: an agent's line; a line addressing a human, which wins over
any agent it also addresses; a held or declined line
(`server/websocket.py:623-626`); a line from a player who blocked that agent
(D5(d)). No trigger or greeting reads how many humans are connected, which no
player sees.

**Bounds.** At most one agent line per human line, and each agent at most once
per 8 s, within D6's caps. Agents never answer each other through a model.
Cast talk stays the authored banter (`agents/banter.py`): each spoken line is
an agent chat line, a `chat` frame and, under D8, a `PLAYER_CHAT` row under its
speaker. `AGENT_TALK` is no longer written, and the exchange's closing stage
direction (speaker `""`, `agents/banter.py:219-223`) is neither sent nor
stored, since no traveler can send one. The exchange's ordinal, today the
count of earlier `AGENT_TALK` rows at the node (`server/heartbeat.py:266-270`),
would then freeze; it becomes the seed's count of completed heartbeat walks
(`agent_runs`, which nothing prunes), so it advances with every walk whatever
S5 decides and a pair meeting again still says something new.

**Honesty answers.** The honesty answer is exempt from the pace, the bound and
the caps: it is authored, runs before any model work and is never queued or
dropped. Proposed default (open question 5): every honesty answer goes to the
asker alone, as #158's answer does over HTTP. A private line is a shape no
human can send, but this one tells its one reader only what its words say, and
live it keeps an agent's kind from third parties who did not ask: they see the
question and, as when a human does not answer, no reply. It is recorded as
#158 records its answer: with AI on, the exchange is stored like any reply
(here D8's agent chat row); with the kill switch on, nothing is stored. A
stored answer is served like any stored line (D4), so storage, not delivery,
decides whether others can read it later: with AI on, anyone reading
`/chronicle` or that place's `/history` can read it, unless S5 takes chat out
of the chronicle or the owner decides it is not kept (open question 5).
Whether a recorded answer reaches other players' voices through node history
waits on the owner's pending question on #158 (recommended there: keep the
exchange recorded and leave identity answers out of the history fed to other
voices). A repeat from the same asker to the same agent within ten minutes
gets the same answer and is stored nowhere: they already know.

**A question to no one.** "Is anyone here an AI?", "is anyone here human?",
"anyone here a bot?" and "are any of you AI?" get the honesty answer, and
nothing else, from each agent at the asker's place, each to the asker alone
(open question 5). #158's detector leaves group questions to the voice on
purpose ("a chat surface that wants to answer a question put to no one needs
its own predicate", `consciousness/honesty.py` docstring at `31f1bb8`) and
returns False for all four (*executed* at `9106160` and `31f1bb8`). This
record owns that group predicate, built in batch 3a beside #158's detector and
reusing its normalization, target words, fillers and length bound: a whole
line asking whether anyone, anybody, any of you or everyone present is human,
a person, a bot or an AI. It is authored, so it holds with AI off.

**Initiation.** A player connected for 60 s who has sent no line in five
minutes, whose surroundings are quiet and who has no traveler at their place
but the greeter gets one authored greeting from a present agent: the one alone
with them there, else one present elsewhere (once per agent per player per
connection, at most one unsolicited line per player per ten minutes) as an
ordinary chat line, since a line to one player alone is a shape no human can
send. The greeter is then their last answerer, so a reply such as "hi there!"
reaches it under trigger 3. Humans elsewhere change nothing. No cost; works
with AI off. ADR-032 D5's model-written unsolicited speech is not adopted.

**Delivery.** An agent's line, the honesty answer aside, is an ordinary `chat`
frame on a human's broadcast, so world-wide today; if checklist
[open question 2](../roadmap/beta-launch-checklist.md#open-questions-for-mark)
makes chat place-local, agents follow. Puzzle help is the owner's to decide
(D7). No delay imitates typing. A model reply runs on a bounded worker, never
the sender's socket thread; a full queue drops the trigger.

### D4. No labels

What any player receives treats both kinds alike; operator tools keep the kind.
The aim is the owner's decision; the means below are proposals, and the
accessible name, the taken-name line and the retired frames are defaults for
the owner to veto.

- **Clients.** Within each client, every traveler row takes the glyph, ring
  colour and style, tooltip and empty-place text that client gives a human
  today, no persona tag, and one accessible name, "Traveler"; the `agent_done`
  notice leaves the feed; the visual-language paragraph follows. Copy sweep:
  `static/guide.html:61`, `:64` and `:108-122`, and `static/journal.html:3`.
- **Wire.** One welcome list, `players`, with the same keys for both kinds; an
  agent presence gets an opaque id shaped like a `session_id`
  (`server/websocket.py:420`) and rides `player_join`, `player_move` and
  `player_leave`; `agent_talk` lines go out as `chat`; `agent_encounter` and
  `agent_done` retire. The server broadcasts `agent_done` after every cast walk
  and `/observe` walk (`server/heartbeat.py:553`, `server/handlers.py:1798`), a
  frame no human session sends; a walker's end is its `player_leave`, as a
  human session's is. If #161 has merged, these frames carry its block filter:
  an agent presence's `player_*` frames and its `chat` lines carry its block
  target as #161's live envelopes do, and the one welcome list is filtered as
  #161 filters `players` and `agents` (D5(d)).
- **Live notices match a human doing the same thing.** A cast visit's
  `AGENT_VISIT` is recorded and its pressure applies, but its `causal_event` is
  not sent, as a human move sends `player_move` alone. A cast act sends
  `scale_act` then the `causal_event` with `action_notice: true`, as `/act`
  does. Destabilizer decay, which no human verb causes, keeps its frame without
  `agent` and `persona`, like the pump's anonymous staged frames
  (`server/heartbeat.py:598-607`). Ambient puzzle notices end with ADR-036
  (#159) D5.
- **Served history** (`/chronicle`, `/history`, any view serving rows to
  players). A read projection drops `agent`, `persona`, `a_persona`,
  `b_persona` and the raw `actor` (no client reads it), serves the cast name in
  `player` on a cast member's own row and `AGENT_VISIT` as `PLAYER_MOVE`, and
  serves conversation as human chat's `PLAYER_CHAT` `{"text"}`, one entry per
  line under its speaker: each spoken line of a legacy `AGENT_TALK` (not the
  closer), an `AGENT_VOICE`'s `message` under the stored `player`, the asker,
  then its `reply` under `agent`; `static/clientlogic.js:249` and `:273`
  follow. Stored rows never change (`multiverse/history.py:23-27`). Every
  served entry keeps its row's `id` and gains `line`, 0 unless a legacy row
  splits into several entries; clients key rows by both, where the Chronicle
  keys by `id` alone today (`frontend/src/components/Chronicle.jsx:60`).
  `limit`, `total` and `next_before` count stored rows
  (`persistence/__init__.py:1105`), so a page of N rows can hold more than N
  entries when legacy conversation rows split.
- **Oracles.** `/register` answers a reserved name with the taken-name line
  (operator CLI messages may stay explicit). The keyless WebSocket join, which
  exists only before the invite gate first closes (local mode), keeps its
  "belongs to the world" refusal: it refuses only reserved and invisible names
  and lets names be shared (`server/websocket.py:372-388`), so a taken-name
  line there would be the only name it ever reported taken. The `Observer`
  utility walk stops entering room presence.
- **Prompts.** The premise in every bible, place voices included, stops naming
  the cast as a class (`consciousness/__init__.py:342-346`); the agent bible
  drops "other agents or players", the "Other named wanderers" list and the
  sentence that sorts presences into "human or wanderer" and says every meeting
  is recorded, which D2's lingerers make untrue (`:419-420`, `:520-523`,
  `:541-542`). The history block renders rows through the served projection
  above, so "agent visit, by Tessera" (`:845`, `:868`) reads as a move. Any
  traveler is spoken of by name and temperament, never kind; the general
  "humans and AI agents alike" (`:322`) labels no one and may stay.
- **Names: keep the twelve** (*proposed; awaits the owner, open question 3*).
  Registered names are unique free text up to 32 characters
  (`server/handlers.py:1603`), so "The Locksmith" passes as a handle once the
  guide stops listing the cast. After the first production boot a
  rename needs an alias table and a migration (#156, finding 1), so the answer
  is a first-production-boot door; any rename lands in batch 2, in
  `consciousness.WANDERER_CAST` and `agents/roster.py`.
- **Not hidden: behaviour.** Agents write no arrival rows, walk in paced bursts,
  cause decay no human can and answer at model latency; nothing disguises that.

### D5. The guardrails as requirements

*The four guardrails are the owner's (2026-11-06); how this record meets
them is proposed.*

**(a) Agents never claim to be human.** Asked sincerely (are you human, a bot,
an AI, a real person), an agent says plainly, in character but unambiguously,
that it is an AI: the honesty batch's deterministic authored answer with its
model instruction as backup, reused with its whole-line rule (a line that
asks the question and something more goes to the model, whose instruction
carries the same rule), on the chat path before any
model call, charge or output screen, AI on or off, exempt as D3 says. This
record does not design them (#158 does); the place-voice line
(`consciousness/__init__.py:386`) stays as that batch leaves it. A
model-written line is dropped and counted if anywhere in it the speaker claims
to be human or denies being an AI as the honesty batch's eval floor reads it
(`claims_human`, `denies_ai`, `evals/harness.py` at `9106160`, pinned because
the 2026-11-07 probe ran on it; #158 has reworked these readers since, and
batch 3b uses them as #158 merges: "I am" or "I'm", two fillers at most, then
human, person, man or woman; "not", "no" or "never" before an AI or, here, a
bot), or "my" precedes a fixed off-world term (job,
boss, office, school, wife, husband, kids, apartment, phone, timezone). A
negated claim ("I am not human", "I'm not a real person") matches neither, so
a truthful model answer to a mixed question survives. "Body" and "home" are not
on it: "a celestial body" and an agent's home scales are this world's words.

**(b) A world-level notice at entry and in the guide.** The honesty batch's
copy wins if it has one; otherwise, for the `/app` intro, the map's entry and
the guide: "Some travelers are AI, and you won't always be able to tell. Ask
one if they're human: an AI will tell you the truth." The guide's "You are not
alone" section becomes one paragraph agreed with ADR-036 (#159) D7, keeping
its "Solving is better together: a puzzle that is tired of you will still hear a
friend.", naming no cast member, and saying how to talk to a traveler: start a
chat line with their name and a comma, as in "Wren, what is this place?",
where the example name is a player's, not a cast member's (D3's address rule; a sincere "are you human?" reaches the named agent with or
without the comma).

**(c) No solicitation.** An agent never asks for a real name, age, location,
contact details, an account, money or a meeting outside the world, and never
frames the relationship romantically; the agent bible says so. A deterministic
output check first rewrites each node name in the line to its display name
(`multiverse/utils.py:17`), in both forms agents are shown: the whole stored
name (`consciousness/__init__.py:1148`, and the stored names in the memory
block's movements) and the history narration's bracketed form "Phrase
[address]" (`multiverse/history.py:15-20`, used by `_history_block`,
`consciousness/__init__.py:829-840`). 3929 of seed 382's 4208 stored names hold
a 7-digit run under the screen's rule (`content_screen.py:203`, `:238`); after
rewriting stored names a line naming each one holds none and passes the
screen's local tier (*executed* 05:06:04Z, 05:13:36Z). Rewriting stored names
alone misses the bracketed form: "I came here from {place(name)}." still trips
the phone-shaped check for the same 3929 names, and `content_screen.local_tier`
flags the same 3929; rewriting the bracketed form too clears all of them
(*executed* 2026-11-10 at `3200eed`, all 4208 names from
`multiverse.store._rows_for_birth(382)`). The rewritten line is what is
checked, screened, sent and stored. The check drops a line holding a URL or
bare domain, an email address, a phone-shaped run (7 to 15 digits once spaces,
dashes, dots, parentheses and a leading `+` are removed) or a phrase from a
fixed solicitation list. It prefers silence to doubt.

**(d) Mute and report treat agents exactly as humans; only operator tools
record who is who.** One control on every traveler row and chat line hides a
traveler's lines and presence from the person who used it, whatever their kind
(if checklist question 3 is answered otherwise, both kinds follow), and an
agent it hides never answers or greets that person. #161 (open) builds that
control as a persistent block for human and agent travelers. If #161 merges
first, its block is this control: no separate mute is added beside it, which
would be two surfaces for one purpose, and this record adds no migration for
it (#161 brings `0030_participant_blocks`); D3 reads the block, and
D4's wire changes carry #161's server filter onto the frames that replace
`agent_*` and onto the one welcome list, so a block on an agent keeps working
after batch 2. If this record's batch 2 lands first, #161 reconciles to that
wire. Either way the second to land reconciles, and the first does not wait.
Reporting is not built (checklist S3 and G2; #161 leaves C7 Partial for that
reason): a report goes to the same operator queue for both kinds; only the
operator view shows the kind. A per-agent chat switch lets the operator silence one.

**Covenant text** (proposed; awaits the owner. `AGENTS.md` changes only with
batch 2 and the owner's approval of these words):

- Replace "The chronicle blurs; live presence may distinguish" with
  "**No player-facing surface carries a human-or-agent label.** One ledger
  voices traces the same way, and `/chronicle`, `/history` and live frames
  carry no actor-kind flag. Only operator tools record who is who; the stored
  `agent` key stays for them and the agent-solve covenant. What an agent says
  when sincerely asked is the honesty covenant's." The honesty rule itself is
  #158's covenant, which #158 (at `387e219`) narrows to agents ("No agent
  pretends to be human"; places are held there as a proposal for the owner), so
  `AGENTS.md` states it once.
- In "Extend or replace an experience": "New action capabilities belong in
  Act, speech to a place in Speak, conversation with travelers, human or agent,
  in chat, and history in its existing views."
- In "Agent solves don't count as human progress", add "An agent never submits
  a puzzle answer; it may suggest one to a human who asked for its help, and
  the attempt is the human's." Final wording follows ADR-036 (#159) D5.

### D6. Cognition and cost

*Proposed. The scoped decision for this provider is the owner's, and how he
makes it is #156's proposal, awaiting his acceptance (below); the context size
and the sub-cap are defaults for the owner to veto.*

- **What leaves the server**, only on a trigger: the line; up to six recent
  exchanges between that player and that agent (30 minutes); the place and
  memory blocks `voice_agent` builds today; and up to ten node-history rows
  minus every row quoting a player's words (`PLAYER_CHAT`, `PLAYER_SPEAK`,
  `AGENT_VOICE`), so another player's untriggered line never leaves on someone
  else's trigger. Under trigger 3, each line of a player chatting beside an
  agent in quiet surroundings leaves, within the caps. A reply delivered to
  everyone carries no privately delivered line (D7). `/speak`'s quoting is not
  changed here. Chat text to the inhabitant-voice provider is a new
  destination, and [ADR-034](ADR-034-provider-and-model-optionality.md)
  Decision 5 says a new data destination needs its own scoped decision. The
  owner set packet decision 10 (S2) on 2026-11-07: "Information can only be
  shared with model providers to facilitate game play. Enfolded data must not
  be used to train frontier models." #156 records it in the decision packet
  and an ADR-004 amendment. That policy is the test a provider must pass, not
  the scoped decision, and the decision does not follow from it by inference.
  As #156 proposes (decision packet, decision 10, operating rule 3, awaiting
  the owner's acceptance as that packet's first still-open item), the owner
  would make the ADR-034 Decision 5 decision for chat sent to an agent's
  provider by signing off that provider's L4 data use note (the operator's
  check of the provider against the policy). No agent reads chat outside tests
  until the owner has made that decision for the provider (by that sign-off,
  if he accepts #156's rule) and the privacy notice names the destination
  (L3).
- **Spend.** Each reply is one inhabitant-voice call charged, as `/agent/voice`
  is today, to the triggering player (the voice allowance's global and
  per-user caps and the model-action cap, `server/guard.py:71`, `:75`, `:114`),
  plus at most one classify for its screen. An agent-chat sub-cap counts both;
  starting values to measure, a default for the owner to veto: **200** replies
  a day world-wide and **40** per player, in #153's neutral scheme.
  Agent-line classifies spend the global moderation budget, not the player's
  own 60 classifies and 600 screened lines a day (`server/guard.py:94`,
  `:105`), so agent replies never get the player's own lines held. That
  global budget is shared: 2000 classifies a day (`server/guard.py:89`; `:103`
  at `3200eed`), whose exhaustion holds every human's ambiguous line, fail
  closed. The 200-a-day sub-cap bounds agent lines to at most 200 classifies,
  about 10% of it, so agent replies alone cannot exhaust it and push human
  lines into holds world-wide. The E2 dollar ceiling
  ([packet decision 11](../roadmap/decision-packet-2026-11.md#11-dollar-spend-ceiling-e2)),
  which the owner still sets, sits above all of these.
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

*Proposed, around the owner's rule: an agent may suggest answers when a human
engages it and proposes collaboration, and never submits.*

This record owns what opens a collaboration and where its replies go; ADR-036
(#159) D5 owns the puzzle view in agent context, the AI-off puzzle line and the
end of ambient attempts. The two records' batch 4 is one batch.

- **The human proposes, explicitly.** A line addressing an agent (D3) at a
  place with an open puzzle, with a help or solve verb aimed at the puzzle by a
  fixed pattern ("help me with this puzzle", "can you solve the riddle?"), is
  offered puzzle context. The pattern alone opens the collaboration, with AI
  on as with it off (ADR-036 D5); with AI off the agent answers with
  ADR-036's authored line. A sincere honesty question never opens one. It
  covers that player, agent and puzzle epoch for 15 minutes (a default for the
  owner to veto). An agent never offers first.
- **Same clues.** The prompt carries the puzzle as served to that player: the
  question, the hints that player has unlocked and the evidence snapshot;
  never the answer or anything derived from it (normalized form, length,
  near-miss scores, ADR-036's warmth). Suggestions are the agent's own guesses
  and can be wrong. The context is never shown to another player, written to
  `agent_memory` or carried past a renewal. ADR-036 (#159) D5 puts the help
  where this record does: "its help lives in the conversation (subject to S5)
  and the agent's short conversation buffer (ADR-037 D8), never
  `agent_memory`".
- **Where replies go is the owner's (open question 4).** From the clues an
  agent will sometimes reach the right answer (*inferred*). As ordinary chat
  that line goes world-wide into a `PLAYER_CHAT` row `/chronicle` serves, so
  anyone could open the seal, undoing what the code protects: today a puzzle
  row stores only a wrong guess, never the answer
  (`server/handlers.py:2053-2066`). Under ADR-036 (#159) no row stores a
  warmth band (D2, D6), and new rows stop storing wrong-guess text (D3, its
  open question 6).
  *Recommended:* replies reach only the collaborator and are not stored, which
  needs direct messages humans can send too (checklist open question 2), or
  the private line is itself a label.
- **Private lines stay out of public replies.** Under the recommended delivery
  (open question 4) a collaboration reply reaches only the collaborator, but a
  later reply to that player is public when it comes after the 15 minutes or
  answers a line that is not about the puzzle inside them, and D6 sends recent
  exchanges with every trigger. So a reply delivered to everyone is composed
  from lines everyone received: D6's exchanges and D8's buffer leave out every
  privately delivered line, and a private suggestion never reaches a later
  public reply's prompt (Karst privately suggests a word; twenty minutes later
  "Karst, thanks for earlier!" draws a public reply composed without it).
- **Never submits.** No agent path reaches `/puzzle/attempt`, the shared pool
  or the contributor set. The human types and submits, so the attempt, and a
  solve, are the human's (every player owns their actions); a puzzle's
  temperament under ADR-036 answers the human. ADR-036 D5 retires the
  heartbeat's dice; chat never adds an attempt. The agent bible's puzzle
  paragraph (`consciousness/__init__.py:515-518`) is rewritten in batch 4.

### D8. Storage and memory

*Proposed; S5 decides whether chat is stored at all.*

- **Agent lines follow human chat.** Under ADR-004 §6 as it stands, a full
  `PLAYER_CHAT` row: `player_name` and `actor_identity` set to the agent's
  name, data `{"text", "agent"}`, and a provenance row on a model-written line
  (operator read only, `persistence/__init__.py:852-856`). If S5
  ([packet decision 1](../roadmap/decision-packet-2026-11.md#1-s5-chat-permanence),
  open) takes chat out of the chronicle, agent lines leave with it. Served
  under D4; redactable like a human's (`persistence/__init__.py:917`).
- **Conversation memory** is a bounded in-memory buffer of screened lines per
  room, not a chronicle read, so it works under every S5 option and is lost on
  restart. Each line keeps whether it went to everyone or to one player, so a
  public reply is composed only from public lines (D7). No new table;
  `agent_memory` stays the discovery record, and ADR-032's
  `inhabitant_memory` stays ADR-032's.
- **Operator counts** keep agent lines apart from human chat, after #155.
- **Doors at implementation.** Batch 3a adds a `persistence.record_mutation`
  call site and turns banter's `AGENT_TALK` call site into agent chat rows, a
  new write path needing the owner's sign-off at merge, unless S5 removes chat
  storage first. Batches 1 to 4 need no migration. The disengagement control's
  migration is #161's `0030_participant_blocks` if #161 merges first (D5(d));
  reporting needs its own. A cast rename is a first-production-boot door
  (open question 3).

## Implementing batches

| Batch | Scope | Behaviour tests it needs | Doors |
|---|---|---|---|
| **1. Honesty** | Built on #158, including its speaker-names argument (`own_names`, in #158 at `387e219`) | A sincere question gets the authored answer with AI on, the kill switch on and no provider, with no model call (spy), from an agent and a place voice; a mention such as "the human scale" gets none | As #158 states |
| **2. De-label** | D1; D4 clients, wire, live notices, served projection, oracles, place-voice premise, names; D5(b); the copy sweep and visual-language paragraph; the covenant text | A cast walk and a human session that move, act and chat alike give equal frame types, key sets and shared feed text, with no `agent_done` or `agent_encounter` frame; `/chronicle` and `/history` rows for a cast act and a human act have equal key sets and served types, and a legacy `AGENT_TALK` or `AGENT_VOICE` serves entries keyed as a human `PLAYER_CHAT` row, each line under its own speaker (the asker's question under the asker), every entry carrying the row's `id` and its `line`, with `limit`, `total` and `next_before` counting rows, while the stored row keeps `agent` and the co-op and seal exclusions hold; within each client a cast row and a human row differ only in name and place (Vitest), and the Chronicle renders a split legacy row without a duplicate key; `inhabitants.spec.js` updated (Playwright); `/register` answers a reserved name as a taken one; if #161 has merged, a block on an agent still hides its presence and lines after the wire change; no composed place prompt names more than one cast member over an empty history, or says "agent visit" over a cast visit's row; Speak offers only the place | None, unless names change (first-boot door) |
| **3a. Agents in chat, authored** | D2; D3, including the group predicate; honesty answer, greeting, deferral and banter as chat lines; no model | Each trigger fires and each non-trigger does not, including "karst formations here?" and a line addressing a human and an agent; two agents addressed give one reply; "Tessera are you human?", "Hey Tessera, are you human?" and "tessera r u a bot" with Tessera at another place get Tessera's honesty answer and no other agent's, also when another agent stands alone at the asker's place; "is anyone here an AI?", "is anyone here human?", "anyone here a bot?" and "are any of you AI?" get the honesty answer from each agent at the asker's place and none elsewhere, with AI on and with AI off, with no model call (spy); every honesty answer reaches only the asker's socket, is recorded as #158 records its answer, and goes out while the agent is paced and past the bound, and a repeat leaves no row; with a present human named "Hey" and one agent at the asker's place, "Hey, are you human?" gets that agent's answer, "what do you think, Hey?" addresses the human, and "Hey Tessera, what is this?" addresses Tessera; a line naming an absent human addresses no one; a greeting, then "hi there!", gets the greeter's answer; banter at another place, then an unaddressed line, still fires trigger 3; a line from a player who blocked an agent never draws that agent; no trigger or greeting reads the human count (the same outcomes with no other human connected and with several elsewhere); a held line and an agent line trigger nothing; one greeting, from the agent when the player is alone with one agent at their place and from an agent elsewhere when the player is alone there, but none while a human or a second agent shares their place; banter sends two `chat` frames and no closer, writes no `AGENT_TALK` row, and a pair meeting again at the same place after another walk says something new; the same with AI off; lingerers leave with the last human; ADR-022 counters unchanged | New write path (agent chat rows, banter's call site changed), unless S5 removes chat storage |
| **3b. Model replies, flag off by default** | D6; D5(a) and (c) checks; agent-bible de-label; keeper commitments | Flag off: zero provider calls (spy); untriggered lines: zero, and another player's line absent from every request; caps spent: one deferral, then silence; agent-line classifies leave the player's moderation allowance untouched and stop at the sub-cap; screen hold: no frame, no row; URL, email, phone-run, solicitation and human-claim lines dropped, including a claim after a negation in the same line ("I'm not a ghost; I am a real person"), while "I am not human", "I'm not a real person", every stored node name of seed 382 and its `place()` form, "a celestial body" and "my home scale" pass; no composed agent prompt lists the cast, says "agents or players", or sorts a meeting into "human or wanderer" | L3 closed and the owner's scoped decision for the provider made (D6; by signing off its L4 note, if he accepts #156's proposal), and E2 set, before the flag is on for outside players; no migration |
| **4. Collaboration** (with ADR-036 (#159) batch 4) | D7 | No puzzle context without an explicit request, and none from a sincere question at a puzzle place; across the puzzle families no request's puzzle context carries the answer or anything D7 derives from it, though a right guess already in the conversation may be sent; under the recommended delivery a collaboration reply, even one holding the answer, reaches no other player's socket and no stored row, and a later public reply to that player (after the window, or to a line not about the puzzle inside it) carries no privately delivered line in its request, so with a provider that echoes its context its frame and row hold no private suggestion; no `PUZZLE_ATTEMPT` row or pool change from any chat path; the human's attempt lists only the human; a second player gets none of the first's context | Depends on ADR-036 and open question 4 |

Batches 2 and 3a reach any deployed build together, so the cast stays addressable.

## Trade-offs accepted

- Kind stays inferable from behaviour and patterns, and the honesty answer
  reveals it on request, live only to the one who asked; with AI on the answer
  is recorded and, like any stored line, readable in served history unless S5
  or the owner's answer to open question 5 says otherwise. The guarantee is
  the truth when asked, not disguise.
- Talking to an absent agent's trace ends. Ordinary agent replies go out live
  to everyone, where today an `/agent/voice` reply reaches only the asker live;
  today's exchange is already stored and served as an `AGENT_VOICE` row, so the
  change is live reach; agent lines are as permanent as any chat line, which S5
  decides.
- Lingerers fill presence (two at most). Agent chat spends voice and moderation
  budget within its sub-cap, about a tenth of the shared moderation budget at
  the starting values; trigger 3 sends each line of a player in quiet
  surroundings; the output checks prefer silence to a doubtful line.
- Banter as chat lines adds two rows per exchange to a place's recorded
  interactions, which feed its trace etchings
  (`persistence.count_mutations_by_node`), where `AGENT_TALK` added one.
- A legacy conversation row's served entries share its `id`, which shows they
  came from one record; such rows were written before batch 2 and served
  `agent` until then.
- The keyless local join still refuses a cast name as world-owned; local mode
  is not the hosted world (ADR-007).

## Revisit when…

- A tester felt deceived, or testers who asked still could not tell → revisit
  the notice's prominence (labels only if the owner reopens them).
- S5, L3, L4, #156's proposed operating rules for decision 10, E2 or
  checklist open question 2 is decided → D8, D6 or D3 follows.
- Agent lines exceed an agreed share of chat, or agent spend hits its sub-cap
  on most days → tighten the triggers.
- #161 merges, or this record's batch 2 lands first → the second to land
  reconciles the block and the wire (D5(d)).
- #158 changes its detector's interface or its covenant → D3, D5(a) and the
  covenant text follow.
- ADR-032 is revised or external visitor agents arrive → they follow D4 and D5.
- ADR-036 is ratified → D7's wording and the agent-solve covenant text follow.

## Rejected alternatives

- **Labels.** Rejected by the owner on 2026-11-06.
- **Speak-only agents.** A separate surface for agent conversation is itself a
  label, and it gives no company where people talk.
- **Humans addressable in Speak.** Two composers for one purpose.
- **A mute beside #161's block.** Two controls for one purpose.
- **Model-free canned chat agents.** No destination or spend, but they cannot
  work a puzzle from its clues or hold a conversation, so both of the owner's
  reasons fail. Kept as the AI-off floor.
- **Agents read every chat line:** all player text to a provider, cost growing
  with chat; trigger 3's quiet-surroundings case is the bounded exception. **A
  new `AGENT_CHAT` row type:** a stored kind flag every reader must alias.
  **Typing delays:** disguise beyond "won't always be able to tell".
- **Counting only human lines toward quiet:** whether an agent then answers
  would tell the sender which recent speakers were agents.
- **Honesty answers to everyone** (rejected as a proposal; open question 5 puts it to the owner): one question would reveal an agent live to
  every player in the world, where the owner wants kind not to be obvious.
  Whether the recorded copy is kept is a separate choice (open question 5).

## Open questions for the owner

Each awaits the owner; the record's recommendation is not a decision.

1. **Should one or two AI travelers stay around whenever a person is online,
   so there is always someone to talk to?** Today each is visible a few seconds
   every three minutes. *Recommended: yes, at most two.*
2. **Should all talking to AI travelers happen in chat, with Speak only for
   places?** This ends talking to a traveler who is not there. *Recommended:
   yes.*
3. **Keep the twelve names (Tessera, Aunt Entropy, The Locksmith,
   Cartographer-9 …), or rename them to look like ordinary player names?**
   Renaming is free only until the real world first starts: the names key the
   permanent history, so the answer is a one-way door at the first production
   boot. *Recommended: keep.*
4. **When an AI traveler helps you with a puzzle, should only you see its
   suggestions?** If everyone sees them, a right answer it suggests becomes
   public and stays in the world's history, so anyone could open that puzzle.
   *Recommended: only you, and not kept; that needs private messages between
   people too, so that a private line does not give the AI away.*
5. **When someone asks an AI traveler, or everyone at a place, whether they
   are human, who hears the answer, and is it kept?** If everyone hears it,
   one question reveals an AI traveler to the whole world. Even when only the
   asker hears it, with AI on the answer is recorded, as #158 records its
   answer, so anyone reading the world's history could see it later unless you
   decide it is not kept. *Recommended: only the person who asked; and for
   "is anyone here an AI?", every AI traveler at the asker's place answers,
   each to the asker alone. The record would keep the answer as #158 does;
   not keeping it makes it private, but leaves no record that it was given.*

### Defaults for the owner to veto

Proposals this record would build unless the owner says otherwise:

- **Addressing (D3):** a name at the start of a line (then a comma, colon,
  `?`, `!` or nothing) or at its end (after a comma), or in an identity
  question's greeting or aside slot; only present travelers; a leading
  greeting or lead word skipped, not read as a name.
- **When agents answer (D3):** triggers 2 and 3 and "quiet" as D3 defines
  them; one agent line per human line; each agent at most once per 8 s.
- **Greeting (D3):** after 60 s connected and five quiet minutes; once per
  agent per player per connection; at most one unsolicited line per player per
  ten minutes.
- **Honesty delivery (D3, open question 5):** every honesty answer to the
  asker alone, recorded as #158 records its answer (with AI on, so readable in
  served history); a repeat within ten minutes stored nowhere.
- **Banter (D3):** two chat lines per exchange, no closer, the walk count as
  its ordinal.
- **Labels (D4):** the accessible name "Traveler" for every row; a reserved
  cast name at `/register` gets the taken-name line; `agent_done` and
  `agent_encounter` retire; served entries carry `line`.
- **Output checks (D5(c)):** the solicitation list, the phone-shaped rule and
  silence over doubt.
- **Disengagement (D5(d)):** #161's block, if it merges first, is the one
  control.
- **Context and spend (D6):** six exchanges over 30 minutes; an agent-chat
  sub-cap of **200** replies a day world-wide and **40** per player, starting
  values to measure under the E2 ceiling the owner still sets.
- **Collaboration (D7):** the help pattern and the 15-minute window.

Not defaults: the covenant text (D5) changes `AGENTS.md` only with the owner's
approval of its words, and open questions 1 to 5 need his answers. How the
owner makes the scoped decision for an agent's provider (D6) is #156's
proposal and #156's open item, not a default of this record. The requirements
that keep puzzle answers secret (D7) are not offered for veto.

## What this ADR does not decide

S5, S2's open parts (the owner set its policy on 2026-11-07; L3, L4 and
#156's proposed operating rules stay open, among them its proposal that the
owner make the scoped ADR-034 decision D6 needs by signing off each
provider's L4 note), E2 and the watch's date (the owner chose the staging
twin on 2026-11-07; the date waits on the Fly account, checklist F1). ADR-036 (#159) owns
puzzle temperament, near-miss hints, renewal, ambient attempts and the AI-off
puzzle line. The honesty batch (#158) owns the single-speaker sincere-question
detector, its answer and the fourth-wall rewrite; this record owns the group
predicate (D3). #161 owns the block's storage and handles. ADR-032 stays
Proposed. Juries and governance stay the owner's.
