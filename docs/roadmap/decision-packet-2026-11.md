# Owner decision packet — November 2026

*Prepared 2026-11-02 against `main` at `23b8830` for the owner, Mark Weeks.
Every recommendation on this page is **proposed by agent; not decided**,
except decision 7, which the owner settled on 2026-11-03 and which ADR-004
records, and decisions 2 and 3, on which the owner ruled in a working session
on 2026-11-06: decision 2 is decided as recommended, and decision 3's options
are superseded by an owner direction whose details wait on a Proposed ADR.
Decision 1 (S5) stays open; the owner asked on 2026-11-06 whether chat must be
kept because it shapes the world's state, history and progress. The
[2026-11-06 evaluation](../evaluation/2026-11-06-next-build.md) records these
rulings and the evidence behind them; the sections below keep the 2026-11-02
analysis as prepared. On 2026-11-07 the owner decided decision 10 as a policy,
which ADR-004 records, and updated decision 2: the Fly staging twin is
preferred, and the local world is the fallback. Beyond those notes the page ratifies no ADR, publishes nothing, and authorizes no
implementation, deployment, recruitment, tag or merge. The evidence behind it
is in the [2026-11-02 week-plan audit](../evaluation/2026-11-02-week-plan.md).
The [beta launch checklist](beta-launch-checklist.md) governs exit criteria;
the [Q4 plan](next-steps-2026-q4.md) governs order until it is re-planned
(decision 6). The [roadmap index](README.md) carries this page.*

## Summary

All recommendations in this table are proposed by agent; not decided, except decision 7 (decided 2026-11-03), decision 2 (decided 2026-11-06, updated 2026-11-07), decision 3 (options superseded by owner direction on 2026-11-06) and decision 10 (decided as a policy on 2026-11-07).

| # | Decision | Needed by | Blocks | Recommendation |
|---|---|---|---|---|
| 1 | [S5: is chat kept in the never-wipe chronicle?](#1-s5-chat-permanence) | Hard: the first production chat line. Practical: before the report queue is built (next week) | The S5 go/no-go line; report evidence (S3, G2); the privacy notice's chat sentence (L3); consent wording | (c) an operator-only chat log with a short retention window, kept out of the chronicle and out of prompts |
| 2 | [Newcomer-watch venue](#2-newcomer-watch-venue) | Decided 2026-11-06; updated 2026-11-07 | O1 to O4 observations; C2c ratings; Q4 steps P6 and P7 | **Updated 2026-11-07:** "Let's expedite the test build, preferably in a staging environment rather than local." The owner prefers the Fly staging twin and an expedited test build; the local, declared-disposable world remains only as a fallback. The twin waits on the Fly account (F1). **Decided 2026-11-06: (a), as recommended.** A local, declared-disposable world for the onboarding watch only; the Fly twin stays mandatory for P4 and production. The watch's voice mode was not decided on 2026-11-06; decision 10's 2026-11-07 policy permits live voice (*inferred*), and the voice mode remains a per-watch choice once the operator's checks are done |
| 3 | [Puzzle failure semantics](#3-puzzle-failure-semantics) | Direction set 2026-11-06; the details need a Proposed ADR before the release-candidate scope freeze | The fix; honest C2a and C2c counts | **Superseded 2026-11-06 by owner direction:** puzzles can have personalities, attempts and lock periods can be dynamic, and the owner suggested that agents help humans solve rather than solve on their own. Details wait on a Proposed ADR. *As prepared:* refuse attempts after a failure, and re-arm failed puzzles through decay with the condition "current epoch resolved (solved or failed)"; the 2026-11-06 evaluation found that this re-arm stops renewing a failed Room once decay has disturbed and fractured it, unless an earlier solve left it stabilized |
| 4 | [World status (Q4 B)](#4-world-status-q4-decision-b) | Before any copy goes to recruits, and before the first invited outside player | R3, K2, "World status declared"; the permanence copy on `/register` and in the guide; L3 | Production for the cohort world if P4's restore and freshness checks pass; any staging or local watch declared disposable |
| 5 | [Minimum tester age (S4)](#5-minimum-tester-age-s4) | Before recruitment (Q4 P5) and before any terms or invite text | S4; the terms text (L2); the invite template | 18 or older |
| 6 | [Re-plan date (Q4 A, lapsed Oct 10)](#6-re-plan-date-q4-decision-a) | Now | Every dated step | Do not adopt the mechanical November 29 date. Plan an early-to-mid January cohort and set the exact date after the watch, once Fly timing is known |
| 7 | [Reserve Observer and Scout](#7-reserve-observer-and-scout) | Decided 2026-11-03 | Nothing now | Reserved, as recommended; recorded in ADR-004's 2026-11-03 reserved-names amendment |
| 8 | [D6 timing (Q4 C, lapsed Oct 10)](#8-d6-timing-q4-decision-c) | Before the first production deploy; a migration-first answer needs about two more weeks before it | ADR-029 batch 1 ordering; how urgent the consumer inventory is | The Q4 recommendation stands: before the first structural operation, not before the pilot |
| 9 | [#89 criteria (Q4 H, lapsed Oct 15)](#9-89-criteria-q4-decision-h) | Before anyone implements #89 | #89 only | The agent drafts revised criteria; the owner posts them or edits the issue |
| 10 | [Player-text destinations (S2, with L4)](#10-player-text-destinations-s2) | Decided 2026-11-07 as a policy. Still needed before any outside participant's text or other Enfolded data reaches a model: the operator's check of each destination | S2, L4; the destinations named in the privacy notice; live voice in the watch; scene images; any second provider; since 2026-11-06, the owner's direction that agents answer players in chat, which sends chat text to a model provider | **Decided 2026-11-07 (policy):** "Information can only be shared with model providers to facilitate game play. Enfolded data must not be used to train frontier models." Recorded in ADR-004. Both sentences apply to all information and Enfolded data sent to any model provider, image prompts included. Implementer's wording: each destination, the image provider included, is checked against the policy and gets its L4 data use note before it receives any Enfolded data, and the operator opts no provider account into a training or data-sharing programme and submits no feedback containing Enfolded data. Still open: naming the destinations in the privacy notice (L3); the operator's checks and notes (L4: none written yet); and the owner's question whether a destination that may train a model that is not plainly frontier (an image model, a safety classifier) meets the policy. *As prepared:* one text provider for voice, intention and moderation, chosen by decision D's probes, and record that image prompts carry no player text |
| 11 | [Dollar spend ceiling (E2)](#11-dollar-spend-ceiling-e2) | Before cohort budget sizing (E1) at P9 | E2, E1, M4; since 2026-11-06, agents answering players in chat (each answer is a model call) | Keep E2 blocking and move only D8's dollar posture ahead of the cohort, resolving the conflict with Q4 decision G. The owner sets the amount and period |
| 12 | [Off-host backup destination and retention (Q4 I)](#12-off-host-backup-destination-and-retention-q4-decision-i) | Before `ENFOLDED_BACKUP_REQUIRED=true` (Q4 P1) | P3 to P5; the backup-retention sentence in L3; the retention tail in decision 1 | Choose a destination and a retention period deliberately; the 30 days in the runbook is an example, not a decision |

## 1. S5 chat permanence

*Proposed by agent; not decided.*

**Today.** Every chat line is broadcast to the whole world and written in full
as a `PLAYER_CHAT` row (`server/websocket.py:236-252`). `/chronicle` and
`/history` return the text to any invited player
(`server/handlers.py:914-946`), node voices quote it into model prompts
(`consciousness/__init__.py:868-873`), and art wear counts the row
(`persistence/__init__.py:1028-1041`). From the first invited outside player
those rows are never-wipe (`docs/decisions/ADR-004-day-one-data-policy.md:240-244`).
Redaction keeps the row, the name slot and `actor_identity`
(`persistence/__init__.py:868-910`), and copies made before a redaction keep
the words until they are deleted (`docs/infrastructure/fly-deployment.md:548-565`).
Operator-minted keys skip the only consent line, on `/register`
(`main.py:318-328`, `static/register.html:49-52`).

**Deadline.** The first production chat line. After it, the first cohort's chat
can never be made non-permanent. The reverse stays possible: chat can be made
permanent going forward at any time.

| | (a) Consent, and keep chat in the chronicle | (b) Ephemeral: out of the chronicle | (c) Operator-only log with a retention window |
|---|---|---|---|
| What changes | Nothing in storage. Consent wording at `/register` and at first entry for minted keys; the privacy notice says chat is permanent and readable in full by invited players. | Chat is broadcast live only; `PLAYER_CHAT` is no longer written. | Chat goes to a new private table that only operators read, with a fixed time-to-live; never to `world_mutations`, `/chronicle`, `/history` or prompts. |
| Migration door | None. | None. | Yes: one additive table. The irreversibility-check human gate applies at merge, and the table holds player text in every backup. |
| ADR-004 amendment | None required: section 6 already names `PLAYER_CHAT` as stored in full (`docs/decisions/ADR-004-day-one-data-policy.md:270-281`) and section 4 is unchanged. A note recording the consent requirement is optional. | Section 6 drops `PLAYER_CHAT` from the full-storage sites; section 4 (`docs/decisions/ADR-004-day-one-data-policy.md:253-258`) states that chat is live presence, not recorded participation. | As (b), plus a retention statement for the log. |
| Backup-retention tail | Permanent. Removing words means redaction, then the backup-deletion procedure. | None for chat sent after the change. | Backups copy the whole database and the time-to-live does not reach them, so real retention runs from the last backup that still contains the line. A backup taken just before the line expires keeps it for the full backup retention (decision 12): a 30-day window with 30-day backups can reach about 60 days, not 30. The prune runs only after a backup stores an object, and it never deletes the newest nonempty validated snapshot (`.github/workflows/backup.yml:140-141`, `scripts/backup_store.py:211-224`). If backups stop, nothing is pruned until they resume; if they keep failing validation, the newest validated copy stays until a newer one exists. Meanwhile, only a bucket lifecycle rule, if one is set (retention plus 7 days or more, `docs/infrastructure/fly-deployment.md:446-449`), or deletion by hand removes the line. The machine-local `/data/backups/*.db` copies sit outside the bucket and its retention. Each backup run writes an `offhost-*.db` copy there and then keeps the newest six (`.github/workflows/backup.yml:100-101`, `.github/workflows/backup.yml:153-158`). Each deploy writes a `worlds-*.db` copy, and `scripts/deploy.sh` prunes the directory to its newest five files only when it deploys (`scripts/deploy.sh:16`, `scripts/deploy.sh:29-33`), so a deploy copy stays until a later deploy prunes it. They and any downloaded copy need their own deletion (`docs/infrastructure/fly-deployment.md:548-565`). |
| Node voices | Unchanged: chat stays in place memory and reaches the voice provider (ties to decision 10). | Lose chat memory; `/speak` and inhabitant exchanges remain. | As (b). |
| Art wear | Unchanged. | Chat rows stop counting toward wear, and the scene-art cooperation modifier counts only `/speak` speakers (`server/imageprompt.py:83-89`). | As (b). |
| Report evidence | Chat rows exist to cite. A chat line still has no client-side ID (`persistence/__init__.py:729-764` returns nothing), so the server must attach evidence by actor identity. | Nothing is stored to cite. G2's "chat lines as evidence" needs text the reporter supplies, or a new store. | Rows can be cited until they expire. A report must either copy the line (a second store of player text that redaction and the privacy notice must cover) or tolerate expiry. |
| Other fallout | S2 must allow chat text to reach the voice provider. A minor's words would be permanent (decision 5). | `beta_metrics.py` reports zero chat lines. Nine test files reference `PLAYER_CHAT` (grep of `tests/`); those that assert a written row change. | As (b), and `beta_metrics.py` would read the log for chat counts. Deleting from an operational table does not engage the chronicle covenant. |
| Effort (sweep estimate) | Consent wording only. | About 1 agent-day. | About 1.5 agent-days. |

**Recommendation (proposed by agent; not decided):** (c), with a short window
(30 days is an example, not a decision), and the backup tail stated in the
privacy notice. If no new table is wanted, (b) with reporter-supplied evidence.
Choose (a) only with consent at both entry points and an explicit S2 allowance
for chat text reaching the voice provider. Whether chat becomes place-local
(open question 2) does not change this door; it changes the shape of block and
report.

## 2. Newcomer-watch venue

**Updated 2026-11-07: the Fly staging twin is preferred.** Asked whether 2 to
3 first-time testers should try the current build now or wait for agents in
chat, the owner, Mark Weeks, answered: "Let's expedite the test build,
preferably in a staging environment rather than local." The owner prefers
the Fly staging twin and an expedited test build. The answer does not forbid
the local, declared-disposable world decided on 2026-11-06; that setup
remains only as a fallback, and the owner did not say when to use it. Staging
is the venue that ADR-005 section 2
(`docs/decisions/ADR-005-launch-operations.md:96-102`), runbook section 3a
and protocol 2 already name, so no ADR is amended. The
[facilitator kit](../evaluation/2026-11-02-newcomer-watch-kit.md) now puts
the twin first: testers on their own devices with invite links minted on
staging, live voice as a per-watch choice that decision 10's 2026-11-07
policy permits (*inferred*) once the operator's checks are done, a sound-on
step, and a scripted return from a bookmark in a fresh browser. Protocol 2
gains one more dated line. The twin's critical path is the held Fly account
(checklist F1: account, billing, flyctl and token). This record deploys
nothing: bringing the twin up is the operator's step under the runbook, and
the research basics are still required.

**Decided 2026-11-06: option (a).** In a working session the owner, Mark
Weeks, answered "yes, we can test locally on a temporary world." The 2 to 3
person onboarding watch may run on a local, declared-disposable world on the
facilitator's machine, with the
[facilitator kit](../evaluation/2026-11-02-newcomer-watch-kit.md). The Fly
staging twin stays mandatory for P4 and before production. As the
recommendation proposed, the ruling is recorded as one line in
[protocol 2](../evaluation/2026-09-12-pilot-protocol.md) ("Scope and
venue"); ADR-004 and ADR-005 are not amended. The watch's voice mode (pre-written lines or
a live model, decision 10's scoped slice) was **not** decided, so the kit
keeps both, with pre-written lines as the default that needs no further
ruling. The research basics are still required. The analysis below is as
prepared on 2026-11-02.

*As prepared: proposed by agent; not decided.*

**Question.** May the 2 to 3 newcomer onboarding watch (protocol 2, script
steps 1 to 3) run on a local, declared-disposable world on the facilitator's
machine, instead of waiting for the Fly staging twin?

**Text it must be reconciled with.**

- ADR-004: "a world meant to be disposable must be declared so and run on
  staging" (`docs/decisions/ADR-004-day-one-data-policy.md:243-244`).
- ADR-005 decides that a disposable staging twin (`enfolded-staging`, its own
  volume) hosts the onboarding watch, the soak, the live-voice probe and the
  restore rehearsal, because "the throwaway phase simply never touches the
  production volume" (`docs/decisions/ADR-005-launch-operations.md:60-66`).
- Protocol 2: "First watch 2–3 newcomers on disposable staging. Tell them that
  its history is temporary" (`docs/evaluation/2026-09-12-pilot-protocol.md:10-11`).
- Q4 step P6 depends on P4 (the staging rehearsal) and P5.

| Option | Gain | Cost |
|---|---|---|
| (a) Local world for the onboarding watch only, run with the [facilitator kit](../evaluation/2026-11-02-newcomer-watch-kit.md) | Player contact without waiting on the Fly account. ADR-005's own reason holds: nothing touches the production volume. ADR-007's boundary stays on, because an unset seed fails closed to 382 (`server/guard.py:133-135`). | Needs a ruling that "staging" in ADR-004, ADR-005 and protocol 2 covers a local, declared-disposable instance for this purpose: a one-line protocol note, or an ADR-005 amendment if you prefer. Sessions run on the facilitator's machine only, because Act and the journal need a secure context, so the watch gives no device evidence (Y5). No hosted soak or restore. |
| (b) Wait for the Fly staging twin | The text is followed as written. | The watch waits on the held Fly account (F1). With the plan already four weeks behind, it likely lands after Thanksgiving. |
| (c) Bring up the Fly twin early, for the watch only | Hosted conditions for the watch. | Still waits on the Fly account; the rest of P4 still has to follow. |

**Recommendation (proposed by agent; not decided):** (a), for the onboarding
watch only. The Fly twin stays mandatory for P4 (soak, downloaded restore,
live-voice probe) and before production. Record the ruling as one line in
protocol 2, and delete the session databases on the deletion date recorded
under K1. The watch also needs the research basics protocol 2 lists
(`docs/evaluation/2026-09-12-pilot-protocol.md:27-31`) and, if live voice is
wanted, decision 10's scoped slice.

## 3. Puzzle failure semantics

**Superseded 2026-11-06 by owner direction.** In a working session the owner
set aside options (a) to (d) below. Puzzles "can have personalities of
sorts": after too many failed attempts a puzzle may get annoyed and tell the
player to go away and leave it alone, and a close answer may excite it into
encouraging the player to try again. Puzzle attempts and lock periods "can
be dynamic in this way rather than fixed and static." The owner also wrote:
"I suggest that AI agents do not solve puzzles independently. However, they
can cooperate with human players to help solve puzzles." Not decided, and
left for a Proposed ADR before anything is built:

- whether annoyance applies to one player or to everyone at the puzzle;
- whether an agent may submit an answer or only suggest one;
- how much a near-miss may reveal, given answer secrecy
  (`tests/test_puzzles.py`) and per-node difficulty (AGENTS.md);
- how a puzzle renews once it has been failed or has sent a player away.

The 2026-11-06 evaluation also found that the recommended (b) could renew a
failed Room only a few times in its life. `_maybe_rearm` runs only when a
decay event changes the node (`causality/wiring.py:90-95`) and only while
solves outnumber re-arms (`causality/wiring.py:62-69`). Rooms carry neither
`danger_level` nor `condition` (`multiverse/generator.py:342-354`), so decay
changes a Room in three ways only: `DANGER_ALERT` sets `disturbed` once
(`multiverse/effects.py:75-80`); a `STRUCTURAL_CHANGE` cascading up from a
child Object sets `fractured` once (`server/heartbeat.py:170-178`,
`causality/staging.py:76-80`, `multiverse/effects.py:85-92`), and nothing
mends a Room; and `DANGER_ALERT` clears `stabilized`, which only a solve sets
(`multiverse/effects.py:69-71`, `multiverse/effects.py:81-83`). A failure
sets nothing, so once a Room is disturbed and fractured and not stabilized,
decay never renews a failed puzzle there. Executed on 2026-11-06 at `18e5bbd` on a scratch
database for seed 382: 296 Rooms, 140 of them locked, none with
`danger_level` or `condition`; on a locked puzzle Room, `DANGER_ALERT` set
`disturbed`, a cascaded `STRUCTURAL_CHANGE` from a child Object set
`fractured` and re-armed once, and after that neither event changed or
re-armed the Room until a solve set `stabilized` again. Whatever the ADR
chooses, renewal needs a clock that does not depend on a material change.
Audit F10 still holds at `18e5bbd` (re-executed by the 2026-11-06 evidence
pass, lines re-read for this record): `failed` is
recomputed on every wrong guess (`server/handlers.py:2114`) and the answer is
released with every failure (`server/handlers.py:2169`).

The analysis below is as prepared on 2026-11-02; its line numbers cite
`23b8830`.

*As prepared: proposed by agent; not decided.*

**Today.** After a shared attempt pool fails and the answer is released, the
server still accepts attempts. Each extra wrong guess writes another
`PUZZLE_FAILED`, and the released answer solves with a material reward
(`server/handlers.py:1921-1929`, `server/handlers.py:1995-2005`,
`server/handlers.py:2021`; re-executed on a scratch database, audit F10).
Nothing re-arms a puzzle because players failed it: `_maybe_rearm` writes
`PUZZLE_REARM` only while the node's `PUZZLE_SOLVED` rows outnumber its
`PUZZLE_REARM` rows (`causality/wiring.py:51-66`). That count includes ambient
agents' rolled solves (`persistence/__init__.py:914-922`,
`agents/agent.py:105-115`), which the seal and the co-op session ignore
(`persistence/__init__.py:584-599`). So a failed puzzle renews only by
accident, when a cast member's roll "solves" it there before decay lands
(executed in review on a scratch database), and a seal opens only on a
player's solve (`puzzles/gates.py:84-87`). The explorer closes the input at
zero remaining (`static/explorer.js:877-878`); `/app` re-enables it after a
reopen (`frontend/src/components/Interact.jsx:164-171`).

| Option | Cost |
|---|---|
| (a) Refuse attempts after a failure, and nothing else | A failed sealed room stays sealed for everyone until a cast member's roll happens to re-arm it, and one player can cause that (*inferred*). It is not imprisonment: anyone already inside can still leave (`puzzles/gates.py:81-82`). |
| (b) Refuse attempts after a failure, and re-arm failed puzzles through the existing decay | `_maybe_rearm`'s condition must be restated from "solves exceed rearms" to "the current epoch's puzzle is resolved (solved or failed)", counting player outcomes only. Today's counter also counts ambient agents' solves, so an ambient roll can renew a puzzle that players are still working on and reset its pool (*inferred* from `causality/wiring.py:61-66` and `persistence/__init__.py:914-922`); the restated condition should not carry that over. Under the current counter, a failure-triggered rearm makes rearms exceed solves, and the next solve at that node would silently stop re-arming (*inferred* from `causality/wiring.py:61-66`). The epoch is the count of `PUZZLE_REARM` rows and feeds seals, mechanics, pressure and Wayback, so the epoch invariant needs tests. This changes an existing `world_mutations` write path (fewer `PUZZLE_ATTEMPT` and `PUZZLE_FAILED` rows, a new trigger for `PUZZLE_REARM`): an irreversibility-check write-path door with the owner's sign-off at merge. Answers do not change, so there is no golden re-pin and `tests/test_continuity_freeze.py` is untouched. About 1.5 agent-days. |
| (c) Stop releasing the answer on failure, and keep accepting attempts | Less answer reuse across sibling puzzles, but failure no longer ends anything, and the failure counts stay inflated. |
| (d) Give each player their own attempt pool | Changes the pooled co-op the guide promises (`static/guide.html:60`); a larger redesign. |

**Recommendation (proposed by agent; not decided):** (b). The server refuses
attempts once the current epoch has failed, reports `failed` on the puzzle
read, `/app` matches the explorer, and decay re-arms the failed puzzle so no
room stays shut forever. "Failed" and "solved" come from players' pooled
attempts, never from an ambient agent's `PUZZLE_FAILED` or `PUZZLE_SOLVED`
row (`agents/agent.py:105-115`): an ambient roll neither closes a puzzle to
players nor counts as resolving it. Answer secrecy (`tests/test_puzzles.py`) stays green.

## 4. World status (Q4 decision B)

*Proposed by agent; not decided.*

**Options.** (a) Production: the cohort world is never reset. (b) Retained
research: it may be kept, but persistence is never promised and then wiped
(`docs/evaluation/2026-09-12-pilot-protocol.md:14-16`).

**Costs.** The copy today assumes (a): `/register` says every trace is recorded
"permanently" (`static/register.html:49-52`), the guide opens by saying every
word joins "the world's permanent chronicle" (`static/guide.html:37-40`), and
its "Nothing is lost" section promises continuity (`static/guide.html:159-167`). Protocol 2 requires
staging newcomers to be told their history is temporary, so the copy must
depend on the deployment either way: a small code change after this decision.
Choosing (a) starts never-wipe at the first invited outside player.

**Recommendation (proposed by agent; not decided):** production for the cohort
world, conditional on P4's restore and freshness checks passing (the Q4
recommendation). Declare staging and any local watch disposable, with
different copy.

## 5. Minimum tester age (S4)

*Proposed by agent; not decided.*

**Options.** 18 or older; 16 or older; 13 or older with guardian consent.

**Costs.** No age statement exists anywhere a player can reach (checklist S4).
A lower age puts minors' words into an append-only record if chat stays in the
chronicle (decision 1, option a), and raises consent and legal work for the
terms and privacy notice (L2, L3). That work depends on jurisdiction, and
legal review is the owner's.

**Recommendation (proposed by agent; not decided):** 18 or older for the first
cohort, stated in the invite and the terms. A facilitator-run watch of adults
does not settle this policy.

## 6. Re-plan date (Q4 decision A)

*Proposed by agent; not decided. Lapsed October 10.*

**The mechanical slip rule.** The Q4 plan runs 23 days from P1/P2 (October 8)
to the beta date (October 31). If P1 and P2 complete on Friday November 6, P9
lands November 14, the cohort runs November 15 to 22, interviews finish
November 25, the read-out runs November 26 to 29, and the beta date is
**November 29**. Thanksgiving (Thursday November 26) falls inside the read-out.

**Why not adopt it.** The slip is 29 days, and the plan's proposed slip rule
says a slip longer than two weeks is re-planned, not absorbed. The mechanical
date also ignores the checklist's blocking build work that must be in the
release candidate before P4 and P6 (block, report and suspension; terms,
privacy and age; E2; P1 targets; F4), the held Fly account, and the unnamed
research lead (P5).

| Option | Cohort window | Assumes | Risk |
|---|---|---|---|
| Mechanical | November 15 to 22; beta November 29 | P1/P2 by November 6; no new build work | Contradicts the plan's proposed slip rule (two weeks); read-out over Thanksgiving |
| December | About December 8 to 15; read-out about December 19 to 22 | Decisions this week; P1/P2 by about November 13; release candidate about November 20 to 23; newcomers after Thanksgiving | Tight. Any slip pushes the overlapping seven-day windows into the year-end holidays |
| Early-to-mid January | For example the weeks of January 4 or January 11 | The watch in November (if decision 2 allows it); the safety and policy build in November and December; Fly and the release candidate in December | A later beta, in exchange for room to decide and build; avoids December 20 to January 3 |

The December and January dates are *inferred* estimates from the evidence
sweep, not verified schedules.

**Recommendation (proposed by agent; not decided):** plan for an early-to-mid
January cohort and set the exact date after the watch, once the Fly account's
timing is known. A migration-first ruling on decision 8 adds about two weeks
(the Q4 plan's "What this plan displaces") and lands in January regardless.

## 7. Reserve Observer and Scout

*Decided 2026-11-03.* The owner, Mark Weeks, directed the merge of #139 on
2026-11-03 and delegated its open choices. The reservation was kept and is
recorded in [ADR-004](../decisions/ADR-004-day-one-data-policy.md)'s
2026-11-03 reserved-names amendment. The analysis below is as prepared on
2026-11-02.

**Then (`23b8830`).** Only the twelve cast names are reserved
(`server/handlers.py:176-181`; ADR-004 section 7,
`docs/decisions/ADR-004-day-one-data-policy.md:291-294`). `/observe` defaults
its agent to "Observer" (`server/handlers.py:1591`); `/agent` and
`/agent/voice` default to "Scout" (`server/handlers.py:1042`,
`server/handlers.py:1409`). The server-owned agent identities PR makes these
fixed identities, so a player registered under either name would collide with
them.

**Options.** Reserve both, which extends ADR-004 section 7's list; reuse an
already-reserved cast name as the fixed observer, which confuses the cast;
or leave them unreserved, which allows the collision.

**Recommendation (proposed by agent; not decided):** reserve both now, while no
player is registered. Only that hunk of the PR waits on this.

## 8. D6 timing (Q4 decision C)

*Proposed by agent; not decided. Lapsed October 10.*

Must the identity/alias and provenance migration (ADR-029 batch 1) land before
the first production history, or only before the first structural operation?
The roadmap index records the open conflict between ADR-029's text, the Q4
recommendation and the readiness record
([Known open conflicts](README.md#known-open-conflicts-unresolved-pending-owner-decision)).
A migration-first answer must ratify ADR-029 batch 1's scope at the same time
and adds about two weeks before P9.

**Recommendation (proposed by agent; not decided):** the Q4 plan's
recommendation stands: before the first structural operation, not before the
pilot. The name-keyed consumer inventory becomes urgent only on a
migration-first answer.

## 9. #89 criteria (Q4 decision H)

*Proposed by agent; not decided. Lapsed October 15.*

Issue #89 is open with 0 comments, last updated 2026-08-31 (GitHub REST, read
2026-11-02). Its per-response property-delta requirement conflicts with
ADR-028's accepted, pending, partial and moot outcomes (Q4 plan, decision H).
Options: revise the criteria, close the issue, or leave it. Posting to the
issue is external publication and needs its own authorization.

**Recommendation (proposed by agent; not decided):** the agent drafts the
revised criteria; the owner posts them or edits the issue. Not cohort-blocking.

## 10. Player-text destinations (S2)

**Decided 2026-11-07, as a policy.** The owner, Mark Weeks, wrote:
"Information can only be shared with model providers to facilitate game
play. Enfolded data must not be used to train frontier models."
[ADR-004](../decisions/ADR-004-day-one-data-policy.md)'s 2026-11-07
model-provider data amendment records it. The owner set a policy rather
than choosing among the options below, so the recommendation of exactly one
provider is neither adopted nor rejected. Both sentences apply to all
information and Enfolded data sent to any model provider: player text and
world content, the text provider and the image provider alike. Its
consequences:

- **Purpose.** Enfolded shares information with a model provider only for a
  task that serves play: today a place's or an inhabitant's voice, reading
  an intention, scene images, and the moderation of shared text (counting
  moderation as a play task is the implementer's reading, *inferred*). The
  owner set no other limit on what a provider does with what it receives.
- **No training.** Enfolded data must not be used to train frontier models.
- **The operator's accounts** (implementer's wording, following from the
  no-training rule). The operator opts no provider account into a training
  or data-sharing programme, and submits no feedback that contains Enfolded
  data.
- **Check before use** (implementer's wording). Each destination is checked
  against both sentences before it receives any Enfolded data, and the check
  is recorded as its L4 data use note: the configured text provider, a
  provider chosen for one task, any `openai_compatible` base URL under
  ADR-035 (Proposed), and the image provider, whose key (`FAL_KEY`) stays
  unset until its note is written.
- **Images.** Image prompts carry no player text: they count distinct
  speakers (`server/imageprompt.py:83-89`), and the prompt is built from the
  node's level, name and properties (`server/imageprompt.py:120-143`). Those
  names and properties are Enfolded data, so the image provider is a
  destination under the policy.
- **The watch.** The policy permits live voice (*inferred*), on the staging
  twin or on the local fallback; the watch's voice mode remains a per-watch
  choice once the operator's checks are done. The
  [facilitator kit](../evaluation/2026-11-02-newcomer-watch-kit.md) states
  the checks.

The configured default text provider is `anthropic`
(`consciousness/runtime.py:38-39`). A web search on 2026-11-07 returned its
help-centre statement that customer content sent through the API under its
commercial terms is not used to train its models by default, with exceptions
when the customer opts in (for example, a development partner programme) or
submits feedback. The page could not be opened from the session that wrote
this record, so the statement is unverified here. No data use note has been
written for any destination.

Still open:

1. Naming the destinations in the privacy notice (checklist L3).
2. The operator's check of each destination against the policy, recorded as
   its L4 data use note: the default text provider's current terms
   confirmed, and the image provider's note written before `FAL_KEY` is set.
3. A question for the owner: whether a destination whose terms let Enfolded
   data train a model that is not plainly a frontier model, such as an image
   model or a provider's safety classifier, meets the policy. Until the owner
   answers, the implementer proposes that the operator asks the owner before
   such a destination receives Enfolded data.

The policy bears on decision 1's option (a), where chat is quoted into
node voices, and on agents answering players in chat; both send chat text to
a provider in the course of play (*inferred*). It decides neither: S5 and the
structural-parity ADR stay open. The analysis below is as prepared on
2026-11-02; its line numbers cite `23b8830`.

*As prepared: proposed by agent; not decided. Held in the checklist, with L4.*

**What reaches which provider today.** The configured text provider receives a
player's speech to places and inhabitants, plus earlier players' names,
messages and chat lines from that node's history
(`consciousness/__init__.py:843-877`). An intention a player describes in Act
goes to the provider to be read (`consciousness/interventions.py:57-81`). Shared
text that the local screen cannot clear goes to the moderation classifier
(`server/moderation.py:184-224`). Image
prompts carry counts of history kinds and of distinct speakers, not player text
(`server/imageprompt.py:83-89`, `server/imageprompt.py:121-141`).

**Options.** One provider for all text tasks; separate providers per task; or
none, with places and inhabitants answering the authored quiet line
(`server/handlers.py:1158-1160`).

**Recommendation (proposed by agent; not decided):** allow exactly one text
provider for voice, intention and moderation: whichever passes decision D's
staging probes. Keep the evaluation adapter (`openai_compatible`, ADR-035
Proposed) away from hosted player text, and record that image prompts carry no
player text. For the local watch only, if live voice is wanted: allow the
current default provider for that disposable watch, disclosed in consent, with
low daily caps. Otherwise run the watch with AI disabled.

## 11. Dollar spend ceiling (E2)

*Proposed by agent; not decided. Held in the checklist.*

**The conflict.** The checklist makes E2 blocking and lets it gate E1 and M4.
The Q4 plan, which governs order, schedules D8 dollar budgets after the
read-out (decision G, "After P11") and lists D8 under "After the cohort
window".

| Option | Cost |
|---|---|
| (a) Keep E2 blocking and move only D8's dollar posture ahead of the cohort | About 2.5 agent-days (sweep estimate); the evaluation harness already meters dollars with verified pricing, reserve and settle (`evals/harness.py:177-183`, `evals/harness.py:216-246`). Needs an amount, a period and a pricing source from the owner. |
| (b) Defer E2 to after the cohort and rely on the daily call caps | Spend is bounded by call counts only; the checklist gate would need amending. |

**Recommendation (proposed by agent; not decided):** (a). The owner sets a
global dollars-per-day and a per-player dollars-per-day they would accept
losing on every day of the window.

## 12. Off-host backup destination and retention (Q4 decision I)

*Proposed by agent; not decided.*

The Q4 plan lists this as pending and needed before
`ENFOLDED_BACKUP_REQUIRED=true`. Cloudflare R2 and 30 days appear only as
examples in the workflow and the runbook; neither is a decision
(`docs/infrastructure/fly-deployment.md:405-409`,
`docs/infrastructure/fly-deployment.md:560-561`). The checklist's held table
did not list it; this batch adds the row from the Q4 plan's decision I,
which is pending and not decided. The retention period also sets the tail in
decision 1 and the backup sentence in the privacy notice, and that tail is
longer than the retention period. A line that leaves the live database stays
in every backup taken before it left, and each of those backups is kept for
the full backup retention. Under decision 1(c), the tail is the time-to-live
plus the full backup retention: a 30-day window with 30-day backups can reach
about 60 days. The prune runs only after a backup stores an object, and it
never deletes the newest nonempty validated snapshot
(`.github/workflows/backup.yml:140-141`, `scripts/backup_store.py:211-224`).
If backups stop, nothing is pruned until they resume; if they keep failing
validation, the newest validated copy stays until a newer one exists.
Meanwhile only a bucket lifecycle rule, if one is set (retention plus 7 days
or more, `docs/infrastructure/fly-deployment.md:446-449`), or deletion by hand
removes the line. The machine-local `/data/backups/*.db` copies sit outside
the bucket and its retention. Each backup run writes an `offhost-*.db` copy
there and then keeps the newest six (`.github/workflows/backup.yml:100-101`,
`.github/workflows/backup.yml:153-158`). Each deploy writes a `worlds-*.db`
copy, and `scripts/deploy.sh` prunes the directory to its newest five files
only when it deploys (`scripts/deploy.sh:16`, `scripts/deploy.sh:29-33`), so
a deploy copy stays until a later deploy prunes it. They and any downloaded
copy need their own deletion
(`docs/infrastructure/fly-deployment.md:548-565`). The privacy notice's backup
sentence should state all of this.

**Recommendation (proposed by agent; not decided):** a private S3-compatible
bucket on an account you already hold, with a retention period chosen
deliberately and stated in the privacy notice.

## What is unchanged

The checklist's other held decisions (the budget-bucket rename, ADR statuses,
new adapters and live evaluations, the Fly account, community governance, and
whether permanent history labels an actor) are not reopened here.

*Update 2026-11-06.* The last of those is no longer held. The owner decided
that agents are not labeled as agents, in permanent history or in live
presence, and accepted guardrails: agents never claim to be human and answer
truthfully when sincerely asked, a world-level notice says some travelers are
AI, agents never solicit, and mute and report treat agents exactly as humans.
The owner also chose to make agents structurally like human players. That
direction needs a Proposed ADR first, and it depends on decision 10 and
decision 11 above. The [beta launch checklist](beta-launch-checklist.md) (A1,
held decisions, open question 10) and the
[2026-11-06 evaluation](../evaluation/2026-11-06-next-build.md) record it.
