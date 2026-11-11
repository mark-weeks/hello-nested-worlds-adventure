# Roadmap index — what governs now

*Verified on 2026-11-11 against `main` at #163 (`7a7b632`, 2026-11-10).
Repository facts were re-read at that commit. Hosted state was checked only
through GitHub (releases and workflow runs); the Fly account and
enfolded.world were not reachable from the verifying session, so "not
deployed" below rests on the record on `main` and is otherwise unverified.*
This is the one place that says which roadmap documents are live, which
decisions are open, and which plans are archived. Update it whenever a plan
ships, a decision is ratified, or a document moves to
[`docs/archive/`](../archive/README.md).

## Where the project stands

- **Not deployed.** The hosted world at enfolded.world has never run, the
  chronicle is empty, and there are no external players. Three QA prereleases
  were cut for local QA (`v0.1.0-qa.1` and `v0.1.1-qa.1` on 2026-08-30,
  `v0.1.1-qa.2` on 2026-08-31); no production release has been cut. The
  [beta readiness record](../evaluation/2026-10-03-beta-readiness.md) (#109)
  named October 31 as a conditional target for an 8–12 person invited study.
  **That date has lapsed and no new date is set.** The re-plan is an open
  owner decision: decision 6 in the
  [November decision packet](decision-packet-2026-11.md#6-re-plan-date-q4-decision-a),
  which is decision A in the
  [Q4 plan](next-steps-2026-q4.md#part-2-decisions-the-owner-must-make-and-by-when).
  The packet sets out the options; its recommendation is proposed by agent
  and not decided. The hosted and human gates the readiness record lists are
  still open on the record: backup activation, hosted restore, freshness
  alerting, live models, hosted runtime and devices, first-session
  observations, the seven-day return.
- **Shipped on `main` since `0.1.0-beta`** (the `[Unreleased]` section of
  [`docs/CHANGELOG.md`](../CHANGELOG.md) holds the measured record). Since
  the readiness record, #110–#163, by subject and newest first within each:
  - *Play and players:* personal blocking of live speech and presence for
    human and agent travelers in both clients, migration
    `0030_participant_blocks` (#161); agents and places never claim to be
    human and answer a sincere identity question plainly, and players are
    told at entry (#158); a returning player with no invite key is told how
    to return (#154); a held or declined chat line comes back to the
    player's input (#151); invitations and return links stay in the `/app`
    scene client, the bounded D7 pilot default (#150); a puzzle or scale act
    reaches the same first ring at every view depth (#129); idle sessions
    stay connected (#121); player and operator wording no longer names the
    text vendor (#116).
  - *Safety, moderation and integrity:* name uniqueness and reserved names
    hold for non-ASCII text (#143); a revoked, rotated or sanctioned session
    is closed on the server's schedule, and the invite gate stays closed once
    any credential is issued (#137, #142); player-reachable agent walks store
    nothing and voice outages reach the operator (#141); agent identities are
    server-owned (#139); the owner can suspend or ban a player, migration
    `0029_sanctions` (#138); empty speech is refused, and unknown places and
    non-string speech fail before any charge (#126, #128); shared text is
    held when moderation cannot judge it, under the ADR-004 amendment (#119,
    #124); HTTP reads, writes and handler threads are bounded (#122);
    moderation routing for person-directed harm and sexual content (#114).
  - *Providers and models:* each text task can name its own provider, and
    the voice and image allowances have neutral names (#153); model calls
    are bounded (the wait for a provider slot, one attempt for a timed
    moderation classify, a per-attempt voice timeout on the anthropic
    adapter), and a screen that could not judge fails `voice-health` (#144,
    #147–#149); the eval harness runs any registered adapter (#146); the
    `openai_compatible` adapter is registered for evaluation, with ADR-035
    still Proposed (#133, #134); the text provider is selected from
    configuration, startup refuses a model id its adapter rejects as
    unusable, without calling the provider, and each task can name its own
    model id (#120, #127, #130–#132);
    model-written chronicle rows record provider and resolved model,
    migration `0028_model_provenance` (#123); provider and model optionality
    under ADR-034, with task-specific evaluations (#112, #113).
  - *Operations and measurement:* beta metrics read the pilot as it happens
    and keep ambient agent traces out of human counts (#155, #162); a manual
    workflow redeploys only the staging twin (#157); same-schema release
    rollback, a binary that refuses a newer chronicle, and the incident
    playbook (#152); off-host backups go to a private bucket, not public
    GitHub artifacts (#136).
  - *Records, plans and working rules (no runtime change):* the prospective
    M8 cross-scale cooperative mystery (#163); Proposed ADR-036 and ADR-037
    (#159, #160); the owner's 2026-11-06 and 2026-11-07 decisions (#156);
    documentation corrections (#117, #145); the November decision packet,
    the newcomer-watch kit and the week-plan audit (#140); the beta launch
    checklist (#135); the standing rule that review findings are posted to
    the reviewed pull request (#125); the merge-time migration numbering rule
    and the open conflicts below (#118); shared agent instructions (#115);
    the Q4 plan (#111); this index and the archive (#110).

  Through #109, newest first:
  beta readiness — pilot protocol 2, validated half-hourly backups with an
  independent freshness check, the scripted situation choice retired from
  onboarding (#109); the ambition assessment and five Proposed ADR drafts (#108); unified
  exploration UX and node-condition styling (#107); commit-then-discover
  actions (#106); 44 scale-native actions, local plates and eleven sampled
  musical forms (#105); the Ideas board, GitHub promotion and their review
  follow-ups (#102–#104); hardened reads and the work report (#101); the first
  shared situation, participants, journal and profile (#100); community policy
  and Apache-2.0 (#99); M1–M4 delivery, delayed choices, history narration and
  responsive inhabitants (#94–#97); the four pre-launch batches (#77–#81).
- **Open:** M7 (pilot cohort) and M8; deployment and its launch gates; the
  beta re-plan date and the other undecided items in the
  [November decision packet](decision-packet-2026-11.md);
  ratification of the implemented-but-Proposed contracts — ADR-019 through
  ADR-022 (M1–M4) and the bounded parts of ADR-013 and ADR-014 realised under
  ADR-024/025 — whose code is merged while their status is still Proposed;
  ADR-012's direction, realised so far only as that bounded first situation;
  ADR-015 through ADR-018 (referential puzzles, spoken interaction,
  multidimensional leaderboards, collectibles), which remain unimplemented
  directions pending both implementation and ratification; ratification of
  [ADR-037](../decisions/ADR-037-agents-as-conversational-players.md), the
  Proposed design for agents in chat, and its five open questions; ratification of
  the ADR-029 through ADR-033 drafts; ratification of
  [ADR-035](../decisions/ADR-035-openai-compatible-chat-completions.md), a
  Proposed design for a second text adapter (the record registers nothing
  and changes no runtime behavior; the adapter merged for evaluation in
  #134; status still Proposed); ratification of
  [ADR-036](../decisions/ADR-036-puzzle-temperament.md), the Proposed puzzle
  temperament design, and its eight open questions; the decision agenda below.

## Live documents

| Document | What it governs | Status |
|---|---|---|
| [Discovery, identity and return](discovery-and-return.md) | Product sequence M0–M8, pilot gates, identity stages, the puzzle and speech tracks; [prospective M8 cross-scale cooperative mystery](discovery-and-return.md#prospective-m8-item-one-cross-scale-cooperative-mystery) | M1–M4 merged; bounded M0/M5/M6 merged (#100, #101); M7 and M8 open. Mystery recorded 2026-11-06 as a candidate for U5's next situation; unassigned and contingent on player evidence |
| [Phase 2 scale plan](phase-2-scale.md) | The standing continuity policy; capacity triggers at 100 users and beyond | Standing; edit in place as triggers fire |
| [Community Ideas board](community-ideas.md) | Player-submitted ideas, support votes, moderation, explicit GitHub promotion | Merged (#102–#104); not deployed |
| [Expressive world: next steps](expressive-world-next-steps.md) | The boundary of the #105–#107 batches and their remaining gaps | Checkpoint; the gaps feed the decision agenda |
| [Beta readiness record](../evaluation/2026-10-03-beta-readiness.md) | Beta scope and promise, the #109 evidence for the remaining launch gates and their owners, the October 31 conditional target (lapsed; the re-plan is packet decision 6, undecided) | Current (#109); not launch approval. The checklist governs exit criteria; the Q4 plan governs order |
| [Beta launch checklist](beta-launch-checklist.md) | Exit criteria before 8 to 12 invited people play: 95 items, evidence, and the decisions held for the owner. The Q4 plan governs order | Living. Statuses are as of `main` at `23b8830` (2026-11-02), with later updates listed in the checklist header (among them M3 to Partial on 2026-11-05; E3, F5 and P6 to Done on 2026-11-06; A1's criterion for the owner's 2026-11-06 decisions; S2 to Partial and L4 to Not started for the owner's 2026-11-07 decisions; C7 and G1 to Partial on 2026-11-10 for personal blocking, #161). Thresholds marked as proposals are not decided |
| [Owner decision packet, November 2026](decision-packet-2026-11.md) | Twelve decisions with needed-by dates, what each blocks, and options with costs: S5 chat permanence, the newcomer-watch venue, puzzle failure semantics, world status, minimum tester age, the re-plan date, reserving Observer and Scout, the lapsed Q4 decisions A, C and H, S2, E2 and Q4 decision I | Prepared 2026-11-02 at `23b8830`. Decision 7 decided 2026-11-03; decision 2 decided (a) and decision 3's options superseded by owner direction on 2026-11-06; decision 10 decided as a policy, decision 2 updated (the Fly staging twin preferred) and three of decision 3's questions answered on 2026-11-07; decision 10's operating rules and the rest are proposed by agent, not decided |
| [Newcomer watch facilitator kit](../evaluation/2026-11-02-newcomer-watch-kit.md) | Setup, script, capture and teardown for 2 to 3 protocol-2 newcomer sessions on the Fly staging twin, with a local, declared-disposable world as the fallback | Draft. Venue: the Fly staging twin, preferred by the owner on 2026-11-07, with the local world allowed on 2026-11-06 kept as the fallback; the 2026-11-07 provider policy may permit live voice (*inferred*), but the watch runs in per-scale silence, with no provider key, until the owner signs off the named provider's L4 data use note (proposed, packet decision 10); code citations re-verified at the branch head (`3200eed` code) on 2026-11-10, runbook citations by section. Recruits nobody and deploys nothing |
| [2026-11-06 next-build evaluation](../evaluation/2026-11-06-next-build.md) | The evidence, plans and critique behind the owner's 2026-11-06 decisions on agent disclosure and structural parity, the watch venue and puzzle failure; the first production boot as the one-way door | Findings with the owner's 2026-11-06 decisions recorded, and an addendum listing the 2026-11-07 decisions on the venue, provider data and puzzles. Ratifies no ADR and authorizes no build |
| [Pilot protocol 2](../evaluation/2026-09-12-pilot-protocol.md) | The M7 study: curiosity, attempted-action and observed-consequence understanding, unprompted and useful return | Ready to run; no cohort observed |
| [2026-10-03 assessment](../evaluation/2026-10-03-ambition-and-boundaries.md) | The decision agenda and a proposed 90-day sequence | Findings for the owner; ratifies nothing |
| [Next steps, Q4 2026](next-steps-2026-q4.md) | The dated critical path to the M7 pilot, the owner's decisions and their needed-by dates, the parallel maintenance track, and the November–January batch order for ADR-029 to ADR-033 as ratified | Plan (2026-10-04); ratifies nothing |
| [ADR-037: agents as conversational players](../decisions/ADR-037-agents-as-conversational-players.md) | The owner's 2026-11-06 decisions on agent disclosure and structural parity and the owner's 2026-11-07 puzzle answers, designed against `f3ead74`: travelers (human or agent) are talked to in chat and places in Speak; no human-or-agent label on any player-facing surface, live notices and prompts included; the honesty, notice, no-solicitation and mute/report guardrails; triggers, caps and the AI-off floor; puzzle help only on a human's explicit request, never submitted, with its batch shared with ADR-036; five ordered batches | Proposed 2026-11-07, revised 2026-11-10; not ratified. Changes no code; approves no player-text destination or spend. S2: a policy is recorded in #156, and the destinations (L3) and the terms check (L4) are still open; S5 and E2 open. Five open questions for the owner |
| [Incident response](../infrastructure/incident-response.md) | One-page operator playbook: kill switches, redaction, rollback versus restore, who decides | Operational. Records no policy decision |
| [ADR-036: Puzzle temperament](../decisions/ADR-036-puzzle-temperament.md) | The owner's 2026-11-06 and 2026-11-07 puzzle decisions designed against the code: per-node temperaments, puzzle-wide grumpiness and per-player send-aways (always after a warning, within a proposed 24-hour cap of 12 misses) in place of the fixed pool and its answer release (F10), whole-answer warmer/colder bands measured per family over a day (the [band-searcher record](../evaluation/2026-11-07-puzzle-band-searchers.md)), no ambient agent attempts (superseding ADR-022's puzzle-eligibility paragraph in part), agents who help only on a human's proposal and never see the answer; four ordered batches, the first shipping its answer withdrawal alone as a rollback floor, and eight open questions | Proposed 2026-11-07, revised 2026-11-10, not ratified. Writes no code; authorizes no build |

The owner's 2026-10-04 provider/model optionality direction is recorded in
[ADR-034](../decisions/ADR-034-provider-and-model-optionality.md). It supersedes
ADR-005's vendor-family preference, not the release gates or the open decisions below.

[ADR-035](../decisions/ADR-035-openai-compatible-chat-completions.md)
(Proposed, 2026-11-01) records the design of one further text adapter,
`openai_compatible`: stdlib HTTP, OpenAI-compatible Chat Completions, an
operator-set base URL, no default model ids, and the existing voice-budget
bucket left in place. Mark Weeks approved the source plan the same day. The
record is not accepted. It registers no adapter, approves no destination for
player text, and sets no spend ceiling. Citing it authorizes nothing.
Separately from the record, the adapter is on `main`: #134 registered
`openai_compatible` for evaluation (selected only by
`NESTED_WORLDS_PROVIDER=openai_compatible`; unset still means `anthropic`),
#146 lets the eval harness run it, and #153 lets one text task name its own
provider. No live evaluation has been run (checklist M3), and ADR-035's
status is unchanged.

## Decision agenda (the owner’s; only bounded D7 pilot default is decided)

The 2026-10-03 assessment put nine decisions to the owner. Five are drafted as
ADRs. All five are **Proposed** and introduce no runtime behavior, migration or
write path; citing them authorizes nothing.
The owner approved the bounded D7 pilot-client change on 2026-11-04, recorded
in [ADR-005](../decisions/ADR-005-launch-operations.md). That decision does
not ratify the five drafts or approve map retirement.

| Decision | Draft | Recommendation in the assessment |
|---|---|---|
| D1 Evolution grammar: births, renames, re-aspect, traversal reparenting, merge/retire, era turns and law shifts as chronicled events | [ADR-029](../decisions/ADR-029-evolution-grammar.md) | Yes |
| D2 Model authorship of persistent canon under ratification, with provenance | [ADR-031](../decisions/ADR-031-model-authorship.md) | Yes, with a deterministic validator, proposal ledger, audit sample and disclosure |
| D3 A recorded, state-addressed render contract in place of renderer determinism | [ADR-030](../decisions/ADR-030-render-contract.md) | Yes |
| D4 Budgeted inhabitant cognition and an open agent roster | [ADR-032](../decisions/ADR-032-inhabitant-cognition.md) | Yes, after pilot evidence |
| D5 A scale registry and lateral kinds; no twelfth depth | [ADR-033](../decisions/ADR-033-scale-registry.md) | Yes to the registry; keep ADR-008 |
| D6 What must precede first production history | none | Only the identity/alias and provenance schema |
| D7 One client | [ADR-005](../decisions/ADR-005-launch-operations.md) | Pilot `/app` default approved 2026-11-04 for consistent first arrival and return. Device and human gates remain; map retirement is undecided |
| D8 Budget posture | none | Dollars per day, not calls per day |
| D9 Process re-tune | none | Keep five covenants; demote the rest to guidance |

### Migration numbering rule

Migration numbers are assigned at merge time. The first batch to merge takes
the next free number. Drafts must not reserve numbers. The current top
migration on `main` is `0030_participant_blocks` (personal blocking, #161).
ADR-029 through ADR-033 each describe a migration they would add; whichever
of those batches merges first takes the next free number.

### Known open conflicts (unresolved; pending owner decision)

Line numbers in this section were re-read at the commit in the verification
stamp at the top of this page. Each link also carries its section anchor,
which survives edits that move lines.

- ADR-029 batch 1 says it must precede first production history
  ([ADR-029](../decisions/ADR-029-evolution-grammar.md#implementing-batches-and-the-doors-they-trip)
  line 192). Decision C states "Before the first structural operation, not
  before the pilot."
  ([next-steps-2026-q4.md](next-steps-2026-q4.md#part-2-decisions-the-owner-must-make-and-by-when)
  line 127). The beta-readiness record states: do not add ADR-029
  implementation as a prerequisite for ordinary beta history on the evidence
  currently available; require it before enabling the structural operations
  that depend on it
  ([2026-10-03-beta-readiness.md](../evaluation/2026-10-03-beta-readiness.md#identity-timing-recommendation-not-ratification)
  lines 146–148).
- ADR-032 says batch 1 ships dark and can be turned on for the pilot cohort
  ([ADR-032](../decisions/ADR-032-inhabitant-cognition.md#d8-economics-and-gating)
  lines 201–202). The Q4 plan schedules D4 after the pilot: decision F says
  "D4 only after pilot evidence"
  ([next-steps-2026-q4.md](next-steps-2026-q4.md#part-2-decisions-the-owner-must-make-and-by-when)
  line 130), and the November–January order places ADR-032 batch 1 after
  pilot evidence, January at the earliest
  ([next-steps-2026-q4.md](next-steps-2026-q4.md#part-4-after-the-read-out-november-to-january-as-ratified)
  line 193). Row D4 of the
  [decision agenda](#decision-agenda-the-owners-only-bounded-d7-pilot-default-is-decided)
  above records the same timing.
- ADR-037 (Proposed) talks to agents in chat and leaves Speak to places,
  keeps every traveler unlabeled, and lets an agent only suggest a puzzle
  answer to a human who asked
  ([ADR-037](../decisions/ADR-037-agents-as-conversational-players.md) D1,
  D4, D7). [ADR-032](../decisions/ADR-032-inhabitant-cognition.md)
  (Proposed) puts inhabitant speech in Speak (D2, D5), persona-tags visitor
  agents (D6) and has inhabitants answer puzzles (D4). ADR-037 asks that
  ADR-032 be revised before ADR-032 is ratified.
- Resolved 2026-10-25 by the owner in chat. ADR-004 section 2 said
  "Fail-open everywhere" for moderation, and no open agenda item covered that
  posture before outside players arrived. The amendment in
  [ADR-004](../decisions/ADR-004-day-one-data-policy.md) (2026-10-25 moderation
  amendment) closes it: shared text fails closed when moderation cannot
  complete, and private or solo-only text and mechanical gameplay stay
  fail-open. The D1–D9
  [decision agenda](#decision-agenda-the-owners-only-bounded-d7-pilot-default-is-decided)
  above and the Q4 decisions A–H
  ([next-steps-2026-q4.md](next-steps-2026-q4.md#part-2-decisions-the-owner-must-make-and-by-when)
  lines 125–132) are unchanged.

## Standing commitments carried from archived plans

Still open when the ensemble action plan was archived; its item numbers are
kept so the archived text can be cross-read.

- **1.2** Activate hosted backups: set `FLY_API_TOKEN`, the private-bucket
  secrets and variables in [backup-bucket.md](../infrastructure/backup-bucket.md),
  `ENFOLDED_BACKUP_APP`, and, before permanent history, `ENFOLDED_BACKUP_REQUIRED=true`;
  dispatch `.github/workflows/backup.yml` (every 30 minutes, SQLite validation,
  private bucket, no GitHub artifact), and prove freshness with
  `scripts/backup_health.py` (runbook §7–§8; readiness record "Remaining gates").
  Observed on GitHub on 2026-11-11: the schedule asks for a run every 30
  minutes, and GitHub started 40 scheduled runs between 2026-10-31 and
  2026-11-10, a mean of one every 6.2 hours and none within an hour of the
  one before; each finished in under 20 seconds (*inferred*: the inactive
  no-op). At that cadence the 60-minute default of `backup_health.py` and
  ADR-005's one-hour bound would not hold; runbook §7 already says a schedule
  alone does not establish the bound.
- **1.3** Run the ADR-005 staging rehearsal on the disposable twin (runbook §3a):
  2–3 observed newcomer sessions, WebSocket soak, live-voice and intention
  probes, and a restore of a downloaded hosted backup into isolated staging.
- **3.3** Cohort rhythm: a recurring gathering and a weekly read of
  `scripts/beta_metrics.py`. The
  [pilot protocol](../evaluation/2026-09-12-pilot-protocol.md) defines the
  measurements; depends on M7.
- **4.1** Litestream-style continuous replication, the first post-launch
  infrastructure batch (ADR-005; the phase-2 plan).
- **4.2** The `/app` device, accessibility and onboarding checks before using
  the cohort's devices. The owner selected `/app` as the pilot default on
  2026-11-04 (ADR-005); that choice does not supply the missing device or human
  evidence. `/` remains the world-map alternate (decision D7).
- **4.3** The world-speaks-first experiment, now subsumed by the ADR-032 draft.
- **4.4** A task-specific comparison of suitable providers, models and versions
  under [ADR-034](../decisions/ADR-034-provider-and-model-optionality.md). The
  assessment's model recommendation is a candidate, not a standing preference;
  select on observed quality, capability, latency, reliability and total cost.
  [ADR-035](../decisions/ADR-035-openai-compatible-chat-completions.md)
  (Proposed) is the adapter shape for that comparison. It selects no model,
  approves no destination, and does not run the comparison. The adapter and
  an eval harness that can run it are on `main` (#134, #146); no live
  evaluation has been run (checklist M3).
- **4.5** Routing extraction from `server/handlers.py` (2,229 lines at
  `7a7b632`). The
  sub-API modules (`server/intervention_api.py`, `ideas_api.py`,
  `participant_api.py`, `situation_api.py`) are the pattern to follow.
- **4.6** Constellation-style arcs at a third scale pair, as evolution content
  under ADR-029 if it is ratified.
- **4.8** Publish the cost-engineering case study.
- **4.9** Hashed Python locks generated from `pyproject.toml`, the dev lock
  layered over the runtime lock. `requirements.lock` and
  `requirements-dev.lock` exist but carry no hashes.

Shipped since that plan was written, for the record: 3.4 the return recap
(journal recap, #100); 3.5 the agent renewal-epoch mismatch (M4, #97); 3.6
per-node deep links (#100); 4.7 display names for deep-scale suffixes.

## Declined (binding until an ADR revisits it)

Recorded in the pre-launch window so that no session relitigates them from a
cold start. The archived plan carries the full argument.

- **A second dimensional scale.** Per-universe law profiles already deliver
  different physics at universe boundaries; dimensionality is a reading the
  lore offers, not a structure the generator needs. ADR-033 (Proposed) would add
  lateral *kinds* without a new content vertical.
- **Wrapped causality.** No convergence guarantee under full-strength law
  profiles (ADR-008).
- **Extensive frontier growth.** The world's stance is intensive infinity:
  finite extent, closed by the loop, deepening under attention. Growth, if it
  comes, is breadth-only and under ratification (ADR-029, Proposed); ADR-008
  forecloses depth 12.

## Archived

Listed with reasons in [`docs/archive/README.md`](../archive/README.md): the
Phase 1 beta scope, the pre-launch window plan and the ensemble action plan.
