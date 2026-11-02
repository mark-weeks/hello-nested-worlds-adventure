# Owner decision packet — November 2026

*Prepared 2026-11-02 against `main` at `23b8830` for the owner, Mark Weeks.
Every recommendation on this page is **proposed by agent; not decided**. The
page records no decision, ratifies no ADR, publishes nothing, and authorizes no
implementation, deployment, recruitment, tag or merge. The evidence behind it
is in the [2026-11-02 week-plan audit](../evaluation/2026-11-02-week-plan.md).
The [beta launch checklist](beta-launch-checklist.md) governs exit criteria;
the [Q4 plan](next-steps-2026-q4.md) governs order until it is re-planned
(decision 6). The [roadmap index](README.md) carries this page.*

## Summary

All recommendations in this table are proposed by agent; not decided.

| # | Decision | Needed by | Blocks | Recommendation |
|---|---|---|---|---|
| 1 | [S5: is chat kept in the never-wipe chronicle?](#1-s5-chat-permanence) | Hard: the first production chat line. Practical: before the report queue is built (next week) | The S5 go/no-go line; report evidence (S3, G2); the privacy notice's chat sentence (L3); consent wording | (c) an operator-only chat log with a short retention window, kept out of the chronicle and out of prompts |
| 2 | [Newcomer-watch venue](#2-newcomer-watch-venue) | Before the first newcomer session is scheduled; this week for a watch before Thanksgiving | O1 to O4 observations; C2c ratings; Q4 steps P6 and P7 | A local, declared-disposable world for the onboarding watch only; the Fly twin stays mandatory for P4 and production |
| 3 | [Puzzle failure semantics](#3-puzzle-failure-semantics) | Before release-candidate scope freeze | The fix; honest C2a and C2c counts | Refuse attempts after a failure, and re-arm failed puzzles through decay with the condition "current epoch resolved (solved or failed)". A write-path door; no re-pin |
| 4 | [World status (Q4 B)](#4-world-status-q4-decision-b) | Before any copy goes to recruits, and before the first invited outside player | R3, K2, "World status declared"; the permanence copy on `/register` and in the guide; L3 | Production for the cohort world if P4's restore and freshness checks pass; any staging or local watch declared disposable |
| 5 | [Minimum tester age (S4)](#5-minimum-tester-age-s4) | Before recruitment (Q4 P5) and before any terms or invite text | S4; the terms text (L2); the invite template | 18 or older |
| 6 | [Re-plan date (Q4 A, lapsed Oct 10)](#6-re-plan-date-q4-decision-a) | Now | Every dated step | Do not adopt the mechanical November 29 date. Plan an early-to-mid January cohort and set the exact date after the watch, once Fly timing is known |
| 7 | [Reserve Observer and Scout](#7-reserve-observer-and-scout) | Before the server-owned agent identities PR merges | That one hunk | Reserve both now, while no player is registered |
| 8 | [D6 timing (Q4 C, lapsed Oct 10)](#8-d6-timing-q4-decision-c) | Before the first production deploy; a migration-first answer needs about two more weeks before it | ADR-029 batch 1 ordering; how urgent the consumer inventory is | The Q4 recommendation stands: before the first structural operation, not before the pilot |
| 9 | [#89 criteria (Q4 H, lapsed Oct 15)](#9-89-criteria-q4-decision-h) | Before anyone implements #89 | #89 only | The agent drafts revised criteria; the owner posts them or edits the issue |
| 10 | [Player-text destinations (S2, with L4)](#10-player-text-destinations-s2) | Before any outside participant's text reaches a model: the first watch session with live voice, and P9 | S2, L4; the destinations named in the privacy notice; live voice in the watch; any second provider | One text provider for voice, intention and moderation, chosen by decision D's probes. Record that image prompts carry no player text |
| 11 | [Dollar spend ceiling (E2)](#11-dollar-spend-ceiling-e2) | Before cohort budget sizing (E1) at P9 | E2, E1, M4 | Keep E2 blocking and move only D8's dollar posture ahead of the cohort, resolving the conflict with Q4 decision G. The owner sets the amount and period |
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
| Backup-retention tail | Permanent. Removing words means redaction, then the backup-deletion procedure. | None for chat sent after the change. | Real retention is the longer of the time-to-live and the backup retention (decision 12), because backups copy the whole database and the time-to-live does not reach them. |
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

*Proposed by agent; not decided.*

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

*Proposed by agent; not decided.*

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

**Why not adopt it.** The slip is 29 days, and the plan's own rule says a slip
longer than two weeks is re-planned, not absorbed. The mechanical date also
ignores the checklist's blocking build work that must be in the release
candidate before P4 and P6 (block, report and suspension; terms, privacy and
age; E2; P1 targets; F4), the held Fly account, and the unnamed research lead
(P5).

| Option | Cohort window | Assumes | Risk |
|---|---|---|---|
| Mechanical | November 15 to 22; beta November 29 | P1/P2 by November 6; no new build work | Contradicts the plan's two-week rule; read-out over Thanksgiving |
| December | About December 8 to 15; read-out about December 19 to 22 | Decisions this week; P1/P2 by about November 13; release candidate about November 20 to 23; newcomers after Thanksgiving | Tight. Any slip pushes the overlapping seven-day windows into the year-end holidays |
| Early-to-mid January | For example the weeks of January 4 or January 11 | The watch in November (if decision 2 allows it); the safety and policy build in November and December; Fly and the release candidate in December | A later beta, in exchange for room to decide and build; avoids December 20 to January 3 |

The December and January dates are *inferred* estimates from the evidence
sweep, not verified schedules.

**Recommendation (proposed by agent; not decided):** plan for an early-to-mid
January cohort and set the exact date after the watch, once the Fly account's
timing is known. A migration-first ruling on decision 8 adds about two weeks
(the Q4 plan's "What this plan displaces") and lands in January regardless.

## 7. Reserve Observer and Scout

*Proposed by agent; not decided.*

**Today.** Only the twelve cast names are reserved
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

*Proposed by agent; not decided. Held in the checklist, with L4.*

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
did not list it; this batch adds the row, marked proposed by agent. The
retention period also sets the tail in decision 1 and the backup sentence in
the privacy notice.

**Recommendation (proposed by agent; not decided):** a private S3-compatible
bucket on an account you already hold, with a retention period chosen
deliberately and stated in the privacy notice.

## What is unchanged

The checklist's other held decisions (the budget-bucket rename, ADR statuses,
new adapters and live evaluations, the Fly account, community governance, and
whether permanent history labels an actor) are not reopened here.
