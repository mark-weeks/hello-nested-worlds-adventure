# What to build next, and the owner's 2026-11-06 decisions

**Date:** 2026-11-06. **Base:** `main` at `18e5bbd`. **Status:** findings,
with the owner's decisions of 2026-11-06 recorded. This record writes no code,
ratifies no ADR, and authorizes no implementation, deployment, recruitment or
merge. Where a finding below cites `file:line`, the line was re-read at
`18e5bbd` for this record. Re-checked on 2026-11-10 at the branch head,
whose code is `main` at `3200eed` (#152 and #153): every cited range still
reads the same except seven that those merges moved, which this record keeps
at `18e5bbd`: `server/__init__.py:167-172` (now `:207-212`),
`persistence/__init__.py:609` (now `:682`), `:1028` (now `:1101`), `:1240`
(now `:1313`), `server/guard.py:958` (now `:1193`) and `main.py:510-512` and
`:541` (now `:585-587` and `:616`).

## Question

What should agents build next toward the first invited cohort, and which owner
decisions unlock it? The [decision packet](../roadmap/decision-packet-2026-11.md)
had been open for four days with one of twelve decisions settled, while #141 to
#151 merged. The [beta launch checklist](../roadmap/beta-launch-checklist.md)
governs exit criteria.

## Method

- **Four evidence readers**, each on one area: player safety and social play
  (10 items); the core loop and pilot measurability (16); release, operations,
  reliability and accessibility (17); strategy and the contrarian view (8).
  That is **51 evidence items**, plus 27 stale-documentation claims and 28
  cross-cutting notes.
- **Two planning lenses** proposed batches from the evidence: the critical
  path weighted by irreversibility and harm (4 items), and player learning,
  which asked whether building more was the right answer at all (5 items).
  Together they proposed 7 distinct candidates.
- **Two adversarial skeptics** tried to refute each candidate: one against
  the code (feasibility), one against the covenants, one-way doors and owner
  gates.
- **One completeness critic** looked for what all of them missed: 8 gaps,
  7 ordering objections, 8 unverified load-bearing claims and 9 final risks.

**Executed** by the readers and skeptics: scratch-database probes, a
headless-Chrome secure-context probe, `npm audit` on scratch lockfile copies,
`EXPLAIN QUERY PLAN` on a proposed recap query, and `git` statistics.
Everything else was **read**. **Not run** by anyone: anything hosted, any live
model call, and the Node 20 build, Vitest and Playwright (the readers had
Node 22 only); Fly's documentation did not resolve. For this record the
renewal and `/chronicle` findings were re-executed on scratch databases at
`18e5bbd`, and again after review, through the cascade path and the cast's own
payload (findings 2 and 6); other "executed" findings were run by the readers
and re-read here.

## Confirmed findings

1. **The first production boot, not the first invite, is the one-way door.**
   `run()` starts the heartbeat, "ambient agent life that runs whether or not
   anyone is connected" (`server/__init__.py:167-172`). The world is born on
   first use (`multiverse/store.py:82-91`, `multiverse/store.py:119`). A puzzle
   definition is pinned the first time it is built
   (`puzzles/instances.py:46-69`; `ON CONFLICT ... DO NOTHING` at
   `persistence/puzzle_content.py:17`), and the cast's sealed-room check builds
   puzzles through that path as it walks (`server/heartbeat.py:250-251`). The
   cast writes ambient `PUZZLE_SOLVED` and `PUZZLE_FAILED` rows
   (`server/heartbeat.py:486-487`). So the canonical world is born and gathers
   permanent rows before any player arrives. Anything birth or first use pins
   (puzzle renewal under decision 3, world status under decision 4, answer
   uniqueness D2, any C1 bank edit under `GENERATOR_VERSION = 2`,
   `multiverse/store.py:41`) has to be settled before F6. Booting production
   with `NESTED_WORLDS_HEARTBEAT=0` until cohort day (`server/heartbeat.py:22`)
   was named by the critic but not weighed. *Read; the consequence is
   inferred.*
2. **The packet's recommended 3(b) could renew a failed Room only a few
   times in its life.** `_maybe_rearm` runs only when a decay event changes
   the node (`causality/wiring.py:90-95`) and only while solves outnumber
   re-arms (`causality/wiring.py:62-69`). Rooms carry neither `danger_level`
   nor `condition` (`multiverse/generator.py:342-354`), so decay changes a
   Room in three ways only. `DANGER_ALERT` sets `disturbed`, once
   (`multiverse/effects.py:75-80`). A `STRUCTURAL_CHANGE` that a destabilizer
   starts on a child Object (`server/heartbeat.py:170-178`; every Object
   carries `condition`) is staged up to the Room as the same event kind
   (`causality/staging.py:76-80`, fired at `causality/staging.py:160`) and
   sets `fractured`, once (`multiverse/effects.py:85-92`); only Objects can
   be mended (`multiverse/verbs.py:276`). `DANGER_ALERT` also clears
   `stabilized` (`multiverse/effects.py:81-83`), which only a solve sets
   (`multiverse/effects.py:69-71`). A failure sets nothing. So under (b) as
   written, a failed Room renews by decay only while one of its two one-time
   flags is unset, or while it still carries `stabilized` from an earlier
   solve. Once it is disturbed and fractured and not stabilized, a failed
   puzzle there is never renewed, and its seal stays shut to everyone
   outside. The seal would still
   never imprison anyone already inside (`puzzles/gates.py:82`). *Executed
   for this record* on a scratch seed-382 database at `18e5bbd`: 296 Rooms,
   140 locked, none with `danger_level` or `condition`, and 449 of 449
   Objects with `condition`. On one locked puzzle Room, a bare
   `PUZZLE_SOLVED` row stood in for a resolved epoch, because it changes no
   property, as a failure would not. A second `DANGER_ALERT` then re-armed
   nothing. A `STRUCTURAL_CHANGE` on a child Object, with its staged hops
   drained, set `fractured` and wrote the first `PUZZLE_REARM`. After a second
   bare row, neither event changed the Room or re-armed it. Only a solve
   through the substance handler, which set `stabilized`, let the next
   `DANGER_ALERT` re-arm once more. The first version of this finding tested
   `DANGER_ALERT` alone and missed the cascade path; review found it.
3. **F10 still holds.** After a shared pool fails, every further wrong guess
   is accepted, `failed` is recomputed (`server/handlers.py:2114`), and the
   answer is released again (`server/handlers.py:2169`); the released answer
   then solves and opens the seal. *Executed by a reader; re-read.*
4. **An ambient solve takes the material reward from a later human solve.**
   `PUZZLE_SOLVED` stabilizes a node only if it is not already stabilized
   (`multiverse/effects.py:69-73`), and the re-arm count includes ambient
   solves (`causality/wiring.py:64-66`). A human who solves after the cast
   gets credit and no change. *Executed by a reader; re-read.*
5. **The agent prompts tell agents to hide that they are AI.** The agent
   prompt says "Never break the fourth wall or reveal that you are an AI"
   (`consciousness/__init__.py:421`), and the place-voice prompt has the same
   line (`consciousness/__init__.py:386`). Agents are told not to ask whether
   a visitor is human (`consciousness/__init__.py:544-546`). Nothing in the
   agent prompt (`consciousness/__init__.py:501-547`) forbids asking players
   for personal details, money or contact. With AI disabled, an addressed agent
   answers the world's quiet line (`server/handlers.py:1475-1479`). *Read.*
   This contradicts guardrail (a) below. It was found while checking this
   record, not by the evidence pass.
6. **`/chronicle` carries an actor-type signal, contrary to the covenant's
   "carries no actor-type flag".** Cast rows carry `agent` and `persona` in
   their data (`server/heartbeat.py:163`, `agents/agent.py:63-69`;
   conversation rows carry `a_persona` and `b_persona`,
   `server/heartbeat.py:271-276`). `decode` passes the data through
   (`persistence/history.py:10-13`), `get_chronicle` adds the raw
   `actor_identity` as `actor` (`persistence/__init__.py:1028`), and
   `/chronicle` serves the page unfiltered (`server/handlers.py:977-993`).
   A cast member's own acts store its name as `actor_identity`
   (`server/heartbeat.py:198-200`); a keyed human's is a credential hash.
   *Executed for this record:* the payload was built by the cast's own
   `Agent(name="Tessera", world_seed=382)._payload(puzzle=..., difficulty=1)`,
   as `server/heartbeat.py:486-487` builds it, sent as an ambient
   `PUZZLE_SOLVED` through `_ambient_event`, and read back with
   `get_chronicle`: data `{'agent': 'Tessera', 'persona': 'tender', 'puzzle':
   ..., 'difficulty': 1}` (Tessera is a tender, `agents/roster.py:47`). The
   first version of this record quoted a hand-written payload instead; review
   caught it. The stored `agent` key must stay. The agent-solve covenant
   depends on it: rows carrying it are left out of co-op solves
   (`persistence/__init__.py:609`) and seal signals
   (`persistence/__init__.py:1240`). The cast's Speak targets and
   `agent_memory` are keyed by it, and it is not redactable
   (`agents/identities.py:3-6`). The chronicle is append-only. So any
   de-labelling applies to what `/chronicle` serves (the `persona` keys, and
   how `agent` and `actor` are presented), never to the write path. The line
   builder both clients share falls back to `data.agent` for the actor's name
   (`static/clientlogic.js:249`), so that projection also needs a client
   change, not a quick HTTP strip.
7. **A returning tester whose stored key is gone sees a loading screen
   forever.** `/app` removes `key=` and `name=` from the address bar on
   first load (`frontend/src/auth.js:21-28`) and afterwards reads the key
   only from local storage (`frontend/src/auth.js:31-37`). A fresh browser
   (a private window, another browser or device, or cleared storage) holds
   no stored key, name or `nw_seen_intro`, so it first shows the
   introduction and then the name prompt (`frontend/src/App.jsx:576-590`).
   After that the world request fails (`frontend/src/App.jsx:146-148`), the
   error is swallowed (`frontend/src/App.jsx:182-185`), and the page stays
   on "Opening the shared world…" (`frontend/src/App.jsx:592-593`). A
   returning tester who types a fresh name there may think they are
   registering again. `invite mint` prints "Share the URL: …" and says
   "this is the only time the key is shown" (`main.py:510-512`); "Share
   once" is what `invite rotate` prints (`main.py:541`). A bookmark, another
   browser or device, a private window or cleared storage would read as a
   non-return in R1's one-shot 7-day measurement. *Read, not run in a
   browser.* Safari's limit on script-written storage is outside knowledge
   and was not checked. (Corrected on 2026-11-10 after review: the first
   version omitted the introduction and name prompt, and attributed
   "Share once" to `invite mint`.)
8. **With AI disabled, the default Speak tab tells a newcomer to leave.**
   `/app` opens on Speak with a prefilled line
   (`frontend/src/components/Interact.jsx:12`, `:49`), and the quiet line is
   "The worlds are quiet today. Try again tomorrow."
   (`server/handlers.py:1207-1210`, `server/guard.py:958`), right after the
   intro promises that a place "answers in character, and it remembers"
   (`frontend/src/App.jsx:646`). *Executed by a reader; re-read.*
9. **Live labels today.** The Travelers panel marks the cast with `✦` and a
   persona (`frontend/src/components/TextPanel.jsx:48`), while the cast's
   conversation is pushed into the feed as ordinary chat
   (`frontend/src/App.jsx:360-366`, rendered at
   `frontend/src/components/TextPanel.jsx:42`). *Read.*
10. **Mute alone moves no gate box.** C7's criterion also needs a report to
    reach an operator queue, and G1 needs C7 and S3 Done (checklist rows C7
    and G1). *Read.*
11. **`scripts/ws_soak.py` measures nothing at `18e5bbd`.** It asks for seed
    99 (`scripts/ws_soak.py:83`), which the canonical-world guard refuses.
    *Executed by a reader (110 of 110 upgrades refused); line re-read.*
12. **A wider return recap needs an index.** `world_mutations` has no
    `actor_identity` index, and the proposed per-player query planned as a scan
    of the world's chronicle. *Executed by a skeptic (`EXPLAIN QUERY PLAN`);
    not re-run.* That is a migration door.
13. **Open PRs #152 and #153 overlap this evaluation's candidates.** #152
    (`cursor/same-schema-rollback-cb10`, head `6aafe8b`) covers the schema
    guard (P6), same-schema rollback (F4) and the incident playbook (F5), and
    adds a test that recounts the checklist's "At a glance" table. #153
    (`cursor/per-task-text-providers-3e78`, head `4e05684`) covers per-task
    text providers and neutral budget names (E3, M1, M5). Both edit
    `docs/roadmap/beta-launch-checklist.md` and `docs/CHANGELOG.md`, as this
    batch does, so whichever merges later must recount. *Executed: GitHub REST
    read and `git diff --stat` against `18e5bbd`.*

## The owner's decisions on 2026-11-06

Made by the owner, Mark Weeks, in a working session, in answer to questions
the evaluation raised. Quoted words are the owner's.

1. **#152 and #153.** "the tracks referenced are another coding agent's
   work." The owner will have Claude review their code before they merge.
   This batch does not duplicate their scope.
2. **Agents are not labeled, and an agent does not pretend to be human.**
   The owner wrote ("#2" numbers the question in that session):

   > On #2, let's not label agents. It will be more interesting if it's not obvious which players are human and which are agents. That being said, there are probably some boundaries and guardrails that would be appropriate. For example, if a player asks an AI agent player "are you human?" the AI agent player should not pretend to be human.

   Neither live presence nor history labels the actor kind. This answers
   checklist open question 10 and the held row on history labels, and
   replaces A1's labeling criterion. The guardrails in decision 4 follow
   from the second half. (Added on 2026-11-10 after review: the first
   version of this record quoted none of these words.)
3. **Agents become structurally like human players.** The owner chose
   option (b), making agents structurally like human players: they can be
   addressed in chat and answer there, and the guide stops naming the cast.
   The owner's reasons: "this would allow human-ai collaboration on puzzles.
   It would also give human players other players to interact with, even if
   there are no other human players logged in at the same time."
4. **Guardrails accepted** ("the recommended guardrails seem reasonable"):
   - (a) Agents never claim to be human. Asked sincerely whether it is
     human, a bot, an AI or a real person, an agent says plainly, in character
     but unambiguously, that it is an AI. The plan is a deterministic authored
     answer with a model instruction as backup, so it holds with AI off.
   - (b) A world-level notice at entry and in the guide: some travelers are
     AI, you won't always be able to tell, and if you ask they will answer
     truthfully.
   - (c) Agents never ask players for personal details, money or off-platform
     contact, and never frame the relationship romantically.
   - (d) Mute and report treat agents exactly as humans; only operator tools
     record who is who.
5. **Watch venue (packet decision 2): (a).** "yes, we can test locally on a
   temporary world." The Fly twin stays mandatory for P4 and production. The
   watch's voice mode was not decided.
6. **Puzzle failure (packet decision 3): options superseded by direction.**
   Puzzles "can have personalities of sorts": after too many failed attempts
   a puzzle "may get annoyed" and tell the player to go away and leave it
   alone; if an answer is close, the puzzle may "get excited by the progress"
   and encourage the player to try again. Puzzle attempts and lock periods
   "can be dynamic in this way rather than fixed and static." The owner also
   wrote: "I suggest that AI agents do not solve puzzles independently.
   However, they can cooperate with human players to help solve puzzles."
7. **S5 chat permanence stays open.** The owner asked: "chat history impacts
   the evolution of the world - it's current state, historical states, and
   progress. To that end, don't we need to preserve chat history?" No decision
   is recorded. The question bears on packet options (b) and (c), which keep
   chat out of the chronicle and out of prompts, and on the packet's deadline:
   after the first production chat line, the first cohort's chat can never be
   made non-permanent.

## What the decisions change in the evaluated plans

- **Withdrawn:** the agent-label candidate (label word, `agent_talk` event
  types, presence labels). Live labels are not wanted.
- **Superseded in part:** both plans' mute and report designs put the
  control on human rows only and refused agent targets. Under guardrail (d)
  agents are muted and reported like anyone else. Mute and report are still
  unbuilt, still need a migration door, and report's chat evidence still
  waits on S5.
- **Not buildable yet:** the puzzle-failure candidate. Its (b) mechanism
  cannot keep renewing a failed Room (finding 2), and the owner's direction
  needs a Proposed ADR.
- **Decided:** the venue part of the watch-kit candidate. The kit now records
  the ruling, uses consent wording that follows guardrail (b) for today's
  build, and cites `18e5bbd`.
- **Unchanged:** the schema guard, rollback and playbook are in #152; the
  name-spoof half of the first-image guards still needs an ADR-004 section 7
  ruling; the recap waits for the watch and an index; the metrics reader and
  the keyless-return line are decision-free and unbuilt.

## Deferred, and why

- **Structural parity.** Implementation needs a Proposed ADR first. Answering
  players in chat sends their chat text to a model provider, so it depends on
  packet decision 10 (S2, player-text destinations) and decision 11 (E2, the
  dollar ceiling). It intersects ADR-032 (inhabitant cognition, Proposed) and
  S5. This record does not write that ADR.
- **The A1 guardrails.** Recorded as A1's criterion; not built. The implementing
  PR must replace the instructions in finding 5 and add the authored answer.
  Whether the place-voice line at `consciousness/__init__.py:386` changes too
  is not decided: the guardrails name agents, not places.
- **Puzzle personalities.** Open for the ADR: whether annoyance applies to one
  player or everyone; whether an agent may submit an answer or only suggest;
  how much a near-miss may reveal, given answer secrecy and per-node
  difficulty; and how a failed puzzle renews (finding 2). The ADR should also
  settle ambient solves and ambient failures (findings 1 and 4), and keep the
  epoch equal to the count of `PUZZLE_REARM` rows. *Updated by the
  2026-11-07 addendum (item 3):* the owner has since answered annoyance
  scope and agent submission and allowed subtle hints; the hints' bounds and
  renewal stay open.
- **S5.** Open; the owner's question is recorded above.
- **The critic's alternative** was to run the watch on the Fly twin, which
  would exercise invites, devices, the return path and real latency. With the
  owner's ruling for a local watch, those wait for P4 and the cohort. The
  critic's additions for a local watch (a scripted return in a fresh browser,
  a sound-on step) are not in the kit yet.

## What this record does not do

- It changes no code, static asset or `AGENTS.md`. The covenant wording that
  the decisions touch, "The chronicle blurs; live presence may distinguish"
  and "Agent solves don't count as human progress", changes with the
  implementing PRs.
- It writes no ADR and ratifies none. It decides nothing about S5, world
  status, tester age, the spend ceiling or player-text destinations.
- It adds no migration, no golden re-pin and no `world_mutations` write path.
- It does not settle the watch's voice mode, or the puzzle questions above
  that the owner's 2026-11-07 answers (addendum, item 3) leave open.

## Addendum, 2026-11-07: the owner's decisions of that day

Recorded without changing the findings above. Quoted words are the owner's,
Mark Weeks.

1. **Watch venue (packet decision 2), updated.** Asked whether 2 to 3
   first-time testers should try the current build now or wait for agents in
   chat: "Let's expedite the test build, preferably in a staging environment
   rather than local." The owner prefers the Fly staging twin and an
   expedited test build. The local, declared-disposable world of decision 5
   above remains only as a fallback. This takes up the critic's alternative
   under "Deferred, and why": the
   [facilitator kit](2026-11-02-newcomer-watch-kit.md) now runs the watch on
   the twin, on testers' own devices, with a sound-on step and a scripted
   return in a fresh browser from a bookmark. The twin still waits on the Fly
   account (checklist F1).
2. **Player-text destinations (packet decision 10, checklist S2 with L4),
   decided as a policy.** "Information can only be shared with model
   providers to facilitate game play. Enfolded data must not be used to
   train frontier models."
   [ADR-004](../decisions/ADR-004-day-one-data-policy.md)'s 2026-11-07
   amendment records it. Both sentences apply to all information and
   Enfolded data sent to any model provider, the image provider's prompts
   included. How each destination is checked, and the owner's sign-off on
   its L4 data use note before testers' text reaches it, are proposals
   awaiting the owner's acceptance in packet decision 10, not part of the
   ADR. Still open: those proposals; naming the destinations in the privacy
   notice (L3); each destination's L4 data use note (none is written, and
   the session that recorded this could not open the default provider's
   terms); and a question for the owner, whether a provider whose terms let
   Enfolded data train a model that is not plainly a frontier model, such as
   an image model, meets the policy. The policy bears on the
   structural-parity dependency on S2 under "Deferred, and why": agents
   answering in chat would send chat text to a provider in the course of
   play (*inferred*). The Proposed ADR, E2 and S5 are still needed.
3. **Puzzle failure (packet decision 3), three questions answered.** Asked
   follow-up questions on decision 6 above, the owner answered:

   > 1. an annoyed player generally gets grumpier toward all players, but especially the player(s) that are annoying it 2. agents can suggest puzzle answers if a human engages with the agent and proposes collaboration. Agents do not submit puzzle answers 3. puzzles can give subtle hints like "you're getting warmer" or "you're way off" in their voice and personality 4. I don't understand the question 5. I don't understand the question

   Answer 1 says "player"; this record, like Proposed ADR-036 (#159, not on
   `main`), reads it as an annoyed **puzzle**, the subject of the question.
   Read that way, annoyance scope is answered (grumpier toward all players,
   especially toward whoever annoys the puzzle), agent submission is
   answered (an agent may suggest an answer when a human engages it and
   proposes collaboration, and does not submit one), and near-miss hints
   such as "you're getting warmer" or "you're way off" are allowed in the
   puzzle's own voice. Answers 4 and 5 are not read as decisions, and this
   record does not say which questions they answered. Still open, for the
   Proposed ADR: how much a hint may reveal under answer secrecy and
   per-node difficulty; how a failed puzzle renews (finding 2); ambient
   solves and failures (findings 1 and 4); and the further questions
   ADR-036 puts to the owner (packet decision 3 lists them). (Added on
   2026-11-10 after review: the first version of this addendum listed only
   the venue and provider rulings.)
