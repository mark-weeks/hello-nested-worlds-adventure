# Roadmap index — what governs now

*Verified on 2026-11-21 against `main` at #190 (`00fa804`, 2026-11-21).
The text changed in this pass was re-read at that commit, and the shipped
list below runs through #190. No `v0.1.2*` tag exists; the newest tag is
`v0.1.1-qa.2`. Hosted state was not re-checked in this pass. The last check,
on 2026-11-11, went through GitHub only (releases and workflow runs); the Fly
account and enfolded.world were not reachable then. So "not deployed" below
rests on the record on `main` and is otherwise unverified.*
This is the one place that says which roadmap documents are live, which
decisions are open, and which plans are archived. Update it whenever a plan
ships, a decision is ratified, or a document moves to
[`docs/archive/`](../archive/README.md).

## Study admission — owner decision, 2026-11-15

The [PR #173 owner decision](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/173#issuecomment-6896202913)
adopts the [eight Watch entry requirements](beta-launch-checklist.md#admission-gate).
Study measurements and later improvements remain distinct. The 8–12 person cohort
starts only after a recorded newcomer watch and its additional entry requirements;
a watch is not itself a cohort start or continuing-world recovery clearance.
S4 is decided as 18 or older, asked at sign-up. AI-off is controlled by model-policy
route permissions, preserving moderation's safe holds.

The owner supplied the three cohort tightenings in version 4 of the decision page
in the working chat: a report reaches a person within 24 hours, a same-day path
for threats or doxxing and named daily duty coverage; an exact labelled release
that passed every automated test; and every full-checklist item applying unless
the owner excuses it in writing. The narrower watch and the inventory stage labels
do not supply cohort exceptions.

This records admission direction, not completion of a watch or the start of a
cohort. No deployment, recruitment or hosted verification is established here.
The owner rejected explorer retirement in #173. Consolidation is now directed
(item 2, O10): X1 put the world map inside `/app` (#190). X2 (#191, open, not merged)
would switch `/` to the React app and move the current map to `/map` until
the cohort read-out.

## Owner decisions, 2026-11-18

The [18 November owner decisions](owner-decisions-2026-11-18.md) adopt answers
to 47 numbered items and record the owner's own words as D-A to D-J. The watch
runs with AI on, names are natural and unique
([ADR-041](../decisions/ADR-041-natural-unique-names.md)), and agents are in
scope for the first cohort. The record builds, deploys and recruits nothing.

## Owner decisions, 2026-11-20

The [20 November owner decisions](owner-decisions-2026-11-20.md) adopt the
owner's items O1 to O17 of the
[20 November batch plan](batch-plan-2026-11-20.md). They set the watch route,
spend amounts, backup bucket, people and dates, and the defaults to bring to the
read-out. The plan names the next parallel batch. Neither merges, deploys or
spends anything.

## Where the project stands

- **Not deployed.** The hosted world at enfolded.world has never run, the
  chronicle is empty, and there are no external players. Three QA prereleases
  were cut for local QA (`v0.1.0-qa.1` and `v0.1.1-qa.1` on 2026-08-30,
  `v0.1.1-qa.2` on 2026-08-31); no production release has been cut. The
  [beta readiness record](../evaluation/2026-10-03-beta-readiness.md) (#109)
  named October 31 as a conditional target for an 8–12 person invited study.
  **That date has lapsed.** The re-plan
  ([packet decision 6](decision-packet-2026-11.md#6-re-plan-date-q4-decision-a))
  is now set: watch sessions on Tuesday 8 December (two testers) and
  Thursday 10 December 2026 (a third tester, if there is one), with Friday
  11 December spare; if G3 has not merged by 2 December, the 8 December
  session moves to the 10 and 11 December slots (O8). The read-out is on
  Monday 14 December. The
  January targets are withdrawn (item 39). The cohort start is still set at
  the read-out, so no cohort date is set (O8, O17). The hosted and human
  gates the readiness record lists are
  still open on the record: backup activation, hosted restore, freshness
  alerting, live models, hosted runtime and devices, first-session
  observations, the seven-day return.
- **Shipped on `main` since `0.1.0-beta`** (the `[Unreleased]` section of
  [`docs/CHANGELOG.md`](../CHANGELOG.md) holds the measured record). Since
  the readiness record, #110–#182, #184, #185, #187, #188 and #190, by
  subject and newest first within each:
  - *Play and players:* the world map opens inside the `/app` client beside
    the same Speak, Puzzle, Act and Travelers panel; arrow keys browse places
    and activating a marker travels there (X1, #190);
    a co-viewer's Act panel shows another player's delayed action while it is
    pending (#185); the map page keeps every traveler name as text, quotes
    included (#177); a recorded identity exchange is left out of the
    history fed to other voices (#166); personal blocking of live speech
    and presence for human and agent travelers in both clients, migration
    `0030_participant_blocks` (#161); agents and places never claim to be
    human and answer a sincere identity question plainly, and players are
    told at entry (#158); a returning player with no invite key is told how
    to return (#154); a held or declined chat line comes back to the
    player's input (#151); invitations and return links stay in the `/app`
    scene client, the bounded D7 pilot default (#150); a puzzle or scale act
    reaches the same first ring at every view depth (#129); idle sessions
    stay connected (#121); player and operator wording no longer names the
    text vendor (#116).
  - *Safety, moderation and integrity:* new human traveler chat goes to a
    private log kept until deletion, with reporting in both clients and an
    operator queue, migration `0033_private_chat_reports` (ADR-040, #174);
    failed puzzle attempts no longer disclose the answer (ADR-036 batch 1a,
    #170); name uniqueness and reserved names
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
  - *Providers and models:* the watch's model-policy example, which the
    offline check refuses until the owner fills it, a per-route reservation
    report and the Chat Completions endpoint check (G1, #187); hosted staging
    and production need an explicit model policy and durable USD reservations
    before external text calls, migration `0032_model_spend` (ADR-039, #172);
    each text task can name its own provider, and
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
  - *Operations and measurement:* the off-host backup job runs in a `backup`
    environment and reads its Fly token and bucket secrets there (G4, #188);
    they stay out of repository scope only once the owner limits that
    environment to `main` and deletes the repository copies;
    disposable staging requires the current
    participant notice before play, migration `0031_participation_consents`,
    with a `0.1.2rc1` candidate (no tag published) and a hosted WebSocket
    rehearsal probe (#169); beta metrics read the pilot as it happens
    and keep ambient agent traces out of human counts (#155, #162); a manual
    workflow redeploys only the staging twin (#157); same-schema release
    rollback, a binary that refuses a newer chronicle, and the incident
    playbook (#152); off-host backups go to a private bucket, not public
    GitHub artifacts (#136).
  - *Records, plans and working rules (no runtime change):* the co-viewer
    delivery test waits for the explorer's world before it counts reads
    (#184); the 20 November batch plan and the owner's decisions O1 to O17
    (#182); the owner's five puzzle-design answers (#181); browser tests keep
    the first-notice stub route for the life of the page (#180); the owner's
    18 November decisions and ADR-041 (#179); CI on the exact head may replace
    the local full run for eligible documentation-only pull requests (#178);
    parallel-work rules for three agents, Copilot review tiers and changelog
    fragments (#176); a delivery priority for agent-chosen work until the
    first cohort starts (#175); study admission scoped to eight entry
    requirements (#173); the three texts the backup cadence record queued
    (#171); the backup cadence measurement (#168); this index brought in line
    with `main` at #169 (#167); the identity-answer counting tests no longer drop counts on a slow disk
    (#165); Proposed ADR-038 (#164); the prospective M8 cross-scale
    cooperative mystery (#163); Proposed ADR-036 and ADR-037 (#159, #160);
    the owner's 2026-11-06 and 2026-11-07 decisions (#156); documentation
    corrections (#117, #145); the November decision packet,
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
  cohort start date, set at the 14 December read-out, and the other undecided
  items in the [November decision packet](decision-packet-2026-11.md);
  ratification of the bounded parts of ADR-013 and ADR-014 realised under
  ADR-024/025, whose code is merged while their status is still Proposed;
  ADR-012's direction, realised so far only as that bounded first situation;
  ADR-015 through ADR-018 (referential puzzles, spoken interaction,
  multidimensional leaderboards, collectibles), which remain unimplemented
  directions pending both implementation and ratification; ratification of
  D3, D6, D7 and D8 of
  [ADR-037](../decisions/ADR-037-agents-as-conversational-players.md), the
  design for agents in chat, after its refresh against `main`; ratification of
  the ADR-029 through ADR-033 drafts; ratification of
  [ADR-035](../decisions/ADR-035-openai-compatible-chat-completions.md), a
  Proposed design for a second text adapter (the record registers nothing
  and changes no runtime behavior; the adapter merged for evaluation in
  #134; status still Proposed); the build and deployment of
  [ADR-038](../decisions/ADR-038-deployment-puzzle-salt.md)'s puzzle salt
  (B1 and B2), adopted in principle on 2026-11-18 and, by the owner's answer
  of 2026-11-19, due before the first production boot (item 22); two
  questions the 18 November record leaves open for the owner (section 5,
  entries 16 and 17): the exact golden-pin diff of the naming change, and
  later of the puzzle redesign, each approved in its own pull request, and
  three `AGENTS.md` wordings approved in the working-rules pull request ("live
  presence may distinguish", the agent-solve covenant and ADR-038's D8
  wording); the decision agenda below.

## Live documents

| Document | What it governs | Status |
|---|---|---|
| [Discovery, identity and return](discovery-and-return.md) | Product sequence M0–M8, pilot gates, identity stages, the puzzle and speech tracks; [prospective M8 cross-scale cooperative mystery](discovery-and-return.md#prospective-m8-item-one-cross-scale-cooperative-mystery) | M1–M4 merged; bounded M0/M5/M6 merged (#100, #101); M7 and M8 open. Mystery recorded 2026-11-06 as a candidate for U5's next situation; unassigned and contingent on player evidence |
| [Phase 2 scale plan](phase-2-scale.md) | The standing continuity policy; capacity triggers at 100 users and beyond | Standing; edit in place as triggers fire |
| [Community Ideas board](community-ideas.md) | Player-submitted ideas, support votes, moderation, explicit GitHub promotion | Merged (#102–#104); not deployed |
| [Expressive world: next steps](expressive-world-next-steps.md) | The boundary of the #105–#107 batches and their remaining gaps | Checkpoint; the gaps feed the decision agenda |
| [Beta readiness record](../evaluation/2026-10-03-beta-readiness.md) | Beta scope and promise, the #109 evidence for the remaining launch gates and their owners, the October 31 conditional target (lapsed; the re-plan, packet decision 6, is set: watch sessions 8 and 10 December 2026, read-out 14 December; items 39, O8) | Current (#109); not launch approval. The checklist governs exit criteria; the Q4 plan governs order |
| [Beta launch checklist](beta-launch-checklist.md) | Eight Watch entry requirements, study measurements and later improvements, over 95 inventory items, with the decisions held for the owner. The Q4 plan governs order | Living. Since #173 it holds the eight Watch entry requirements, the study measurements and the later improvements, with all 95 IDs kept. Row statuses carry their own dates and evidence. F2 stays Partial: the candidate remains `0.1.2rc1`, whose schema-32 wheel #172 verified. Thresholds marked as proposals are not decided |
| [Owner decision packet, November 2026](decision-packet-2026-11.md) | Twelve decisions with needed-by dates, what each blocks, and options with costs: S5 chat permanence, the newcomer-watch venue, puzzle failure semantics, world status, minimum tester age, the re-plan date, reserving Observer and Scout, the lapsed Q4 decisions A, C and H, S2, E2 and Q4 decision I | Prepared 2026-11-02 at `23b8830`. Decision 7 decided 2026-11-03; decision 2 decided (a) and decision 3's options superseded by owner direction on 2026-11-06; decision 10 decided as a policy, decision 2 updated (the Fly staging twin preferred) and three of decision 3's questions answered on 2026-11-07; decision 10's operating rules were proposed by agent. Later owner records answer more: decision 6, the re-plan, is set by item 39 and O8, and decision 10's operating rules 1 to 4 are accepted (item 25); decisions 1 and 5's Version 4 study policies were selected on 2026-11-15; the [18 November](owner-decisions-2026-11-18.md) and [20 November](owner-decisions-2026-11-20.md) records answer further decisions |
| [Newcomer watch facilitator kit](../evaluation/2026-11-02-newcomer-watch-kit.md) | Setup, script, capture and teardown for 2 to 3 protocol-2 newcomer sessions on the Fly staging twin, with a local, declared-disposable world as the fallback | Draft. Venue: the Fly staging twin, preferred by the owner on 2026-11-07, with the local world allowed on 2026-11-06 kept as the fallback; the kit's per-scale silence with no provider key is superseded: the watch runs with AI on (D-A, item 3). O3 names the incumbent's compatible endpoint, with OpenAI's own endpoint as the fallback; G1's [endpoint check](../evaluation/2026-11-20-chat-completions-endpoint-check.md) recommends OpenAI's endpoint. The owner's data-use note for it is not yet signed. The kit's refresh is C2 (item 8), not yet merged; code citations re-verified at the branch head (`3200eed` code) on 2026-11-10, runbook citations by section. Recruits nobody and deploys nothing |
| [2026-11-06 next-build evaluation](../evaluation/2026-11-06-next-build.md) | The evidence, plans and critique behind the owner's 2026-11-06 decisions on agent disclosure and structural parity, the watch venue and puzzle failure; the first production boot as the one-way door | Findings with the owner's 2026-11-06 decisions recorded, and an addendum listing the 2026-11-07 decisions on the venue, provider data and puzzles and, as item 4, the owner's two 2026-11-10 decisions on place voices and identity answers (#166). Ratifies no ADR and authorizes no build |
| [Pilot protocol 2](../evaluation/2026-09-12-pilot-protocol.md) | The M7 study: curiosity, attempted-action and observed-consequence understanding, unprompted and useful return | Ready to run; no cohort observed |
| [2026-10-03 assessment](../evaluation/2026-10-03-ambition-and-boundaries.md) | The decision agenda and a proposed 90-day sequence | Findings for the owner; ratifies nothing |
| [Next steps, Q4 2026](next-steps-2026-q4.md) | The dated critical path to the M7 pilot, the owner's decisions and their needed-by dates, the parallel maintenance track, and the November–January batch order for ADR-029 to ADR-033 as ratified | Plan (2026-10-04); ratifies nothing |
| [ADR-037: agents as conversational players](../decisions/ADR-037-agents-as-conversational-players.md) | The owner's 2026-11-06 decisions on agent disclosure and structural parity and the owner's 2026-11-07 puzzle answers, designed against `f3ead74`: travelers (human or agent) are talked to in chat and places in Speak; no human-or-agent label on any player-facing surface, live notices and prompts included; the honesty, notice, no-solicitation and mute/report guardrails; triggers, caps and the AI-off floor; puzzle help only on a human's explicit request, never submitted, with its batch shared with ADR-036; five ordered batches | D1, D2, D4 and D5 ratified on 2026-11-18 (item 40), with two exceptions: D4's question about cast names (answered by D-B and ADR-041) and D5's proposed covenant text (item 44). D3, D6, D7 and D8 stay Proposed until the refresh against `main`. All five open questions answered (question 4 on 2026-11-19: an agent's puzzle help can be given in the shared chat; question 5's second half on 2026-11-20, O16(c): with AI on, an honesty answer is kept as that agent's chat lines are kept (D8), out of the history fed to other voices; with AI off nothing is stored; a repeat from the same asker to the same agent within ten minutes is stored nowhere). Changes no code; approves no player-text destination or spend. S2: a policy is recorded in #156, and the destinations (L3) and the terms check (L4) are still open. S5's policy is set by ADR-040 (checklist S5 stays Partial): new human traveler chat goes to a private log (#174), accepted as implemented on 2026-11-18 (item 43). E2's amounts are adopted in O4; their confirmation waits for the policy file |
| [Incident response](../infrastructure/incident-response.md) | One-page operator playbook: kill switches, redaction, rollback versus restore, who decides | Operational. Records no policy decision |
| [ADR-036: Puzzle temperament](../decisions/ADR-036-puzzle-temperament.md) | The owner's 2026-11-06 and 2026-11-07 puzzle decisions designed against the code: per-node temperaments, puzzle-wide grumpiness and per-player send-aways (always after a warning, within a proposed 24-hour cap of 12 misses) in place of the fixed pool and its answer release (F10), whole-answer warmer/colder bands measured per family over a day (the [band-searcher record](../evaluation/2026-11-07-puzzle-band-searchers.md)), no ambient agent attempts (superseding ADR-022's puzzle-eligibility paragraph in part), agents who help only on a human's proposal and never see the answer; four ordered batches, the first shipping its answer withdrawal alone as a rollback floor, and eight open questions | Ratified on 2026-11-18 with its recorded answers as starting values (item 19); batches 1b and 2 directed (item 20). Batch 1a, the answer withdrawal, merged in [#170](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/170) ([record](../evaluation/2026-11-11-puzzle-answer-withdrawal.md)); the shared pool, FAILED and write paths remain until batches 1b and 2. Batches 1b to 4 remain to be built; the eight open questions are answered by the recorded starting values (item 19). Question 6, from batch 3, is separately directed: only right or wrong is stored for a guess, shipped before the first cohort invitation (item 21) |
| [ADR-038: Deployment puzzle salt](../decisions/ADR-038-deployment-puzzle-salt.md) | Whether the hosted world gets a secret salt for puzzle content before its first boot: keep seed 382 (no puzzle draw reads the seed, and `/world` serves it); HMAC-key every draw in puzzle generation, difficulty and the Augury election included (amending ADR-010 in part), with a per-deployment salt, renewals keeping their epoch-0 difficulty and Augury family, birth unkeyed and the unsalted path byte-identical; a marked deployment refuses to run without it; separate staging and production salts; Sentry stops sending frame locals. Measured on seed 382 (the [salt-probe record](../evaluation/2026-11-11-puzzle-salt-probes.md)): an offline attacker using 400 salts of their own still guesses 15–16% of epoch-0 answers first time and 31–32% within today's 3–5 pooled attempts (every sealed lock and lineage), so the salt keeps at most about 84–85% off a one-guess table and 68–69% off such a list; every family stays mechanically solvable once its prompt is served; its answer-release observations describe pre-#170 code, with direct disclosure withdrawn separately by ADR-036 batch 1a in [#170](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/170) | Proposed 2026-11-10, revised 2026-11-11; adopted in principle on 2026-11-18, with separate staging and production salts. Its first open question was answered on 2026-11-19: the salt, B1 and B2, comes before the first production boot (item 22). No code is written and no secret is set. Its D8 wording is open for the working-rules pull request |
| [Backup schedule cadence](../evaluation/2026-11-11-backup-schedule-cadence.md) | What GitHub's schedule delivers for `backup.yml` against ADR-005's one-hour bound and the 60-minute default of `scripts/backup_health.py`: 1,018 runs measured, the consequence for standing commitment 1.2 and checklist P3 and P5, and five options with their costs | Findings for the owner (2026-11-11). The options and the recommendation are proposed by agent, not decided. Changes no workflow, threshold or ADR status |
| [ADR-039: controlled model dispatch and spend](../decisions/ADR-039-controlled-model-spend.md) | Frozen destination/model/options permissions, durable USD reservations and conservative settlement, incident stops and operational ledger retention | Proposed for implementation review, 2026-11-11; stays Proposed until the staging rehearsal of item 28. Implementation requested in session, unverified from the repository, not independently ratified. The first controlled adapter/vendor remains an owner decision. Every Fly app, production included, starts all-off; live voice waits for ADR-035 acceptance or a controlled Anthropic path plus approved destinations, prices, amounts and retention. Its migration merged as `0032_model_spend` (#172) |
| [Controlled-model implementation evidence](../evaluation/2026-11-11-model-spend-controls.md) | The prepared control boundary, measured checks, known limitations and remaining live gates | Implementation evidence, not provider evaluation, live activation or approval of policy values. Chat retention is outside this batch |
| [ADR-040: private chat retention and reporting](../decisions/ADR-040-private-chat-and-reporting.md) | The operational storage boundary for new human traveler chat, private reports and operator triage, legacy-history projection and aggregate art continuity | Accepted as implemented on 2026-11-18 (item 43). Version 4 prepares the owner's until-deleted private chat policy, complaint holds, deletion commands and affirmative adult participation. Report windows of 90 days for the watch and 180 days for the cohort are documented decisions only; rollout policy, contact and backup treatment still require operator configuration. Its additive migration merged as `0033_private_chat_reports` (#174) |
| [Community retention and reporting](../development/community-reporting.md) | Offline community-policy checks, private report and chat-deletion commands, complaint holds, end-of-study review, backup limits and queue polling | Implementation guidance. No policy file means new traveler chat and reports are disabled in hosted and local modes. Until-deleted chat and the documented report windows supply no deployment defaults, live staffing commitment or external notifications |
| ADR-019 to ADR-022 ([019](../decisions/ADR-019-m1-sqlite-delivery.md), [020](../decisions/ADR-020-m2-delayed-actions.md), [021](../decisions/ADR-021-m3-history-narration.md), [022](../decisions/ADR-022-m4-responsive-inhabitants.md)) | M1–M4: delivery, delayed actions, history narration and inhabitant attention | ADR-019, ADR-020 and ADR-021 accepted as implemented on 2026-11-18 (item 43). ADR-022 accepted as implemented except its puzzle-eligibility paragraph, which the owner's 2026-11-06 decision overruled |
| [Owner decisions, 2026-11-18](owner-decisions-2026-11-18.md) | The owner's answers to 47 items and his words D-A to D-J: the AI-on watch, natural names, agents in the first cohort, puzzles, spend, backups, people and dates | Adopted by the owner's merge. Builds, deploys and recruits nothing. Of its open questions for the owner, entries 16 and 17 remain; entry 18 was answered on 2026-11-20 (O16(c)) |
| [ADR-041: natural, unique names](../decisions/ADR-041-natural-unique-names.md) | Names are labels and the path is the address: no cast or place name carries appended characters, and a cast name used in production stays reserved forever, even after retirement (D5); place names are unique within each world (D2) | Accepted 2026-11-18 (D-B). Changes no code; the naming pull request carries the build, and the owner approves its exact pin diff there |
| [Owner decisions, 2026-11-20](owner-decisions-2026-11-20.md) | The owner's batch, O1 to O17: the watch route and data-use note, dollar amounts, call caps, notice values, the backup bucket, people and dates, the old map's path, merge order, rehearsals, alerts and the read-out defaults | Adopted by the owner's merge. Performs no act and supplies no owner-held value; the read-out declarations are not made in advance |
| [Batch plan, 2026-11-20](batch-plan-2026-11-20.md) | The next parallel batch for the three coding agents, its single-writer holds and merge order, and the owner's items that O1 to O17 decide | Plan; authorizes no merge, deployment or spend |

The owner's 2026-10-04 provider/model optionality direction is recorded in
[ADR-034](../decisions/ADR-034-provider-and-model-optionality.md). It supersedes
ADR-005's vendor-family preference, not the release gates or the open decisions below.

[ADR-035](../decisions/ADR-035-openai-compatible-chat-completions.md)
(Proposed, 2026-11-01) records the design of one further text adapter,
`openai_compatible`: stdlib HTTP, OpenAI-compatible Chat Completions, an
operator-set base URL, no default model ids, and the existing voice-budget
bucket left in place. Mark Weeks approved the source plan the same day. The
record is not accepted, and stays Proposed until item 24's endpoint is
settled: by O3 it is accepted for one endpoint once G1's check record and
G3's first live probe on the twin show its five requirements met. It
registers no adapter, approves no destination for player text, and sets no
spend ceiling. Citing it authorizes nothing.
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
not ratify the five drafts or approve map retirement. D6 was decided on
2026-11-18 (item 17); the heading keeps its earlier wording because other
pages link to it.

| Decision | Draft | Recommendation in the assessment |
|---|---|---|
| D1 Evolution grammar: births, renames, re-aspect, traversal reparenting, merge/retire, era turns and law shifts as chronicled events | [ADR-029](../decisions/ADR-029-evolution-grammar.md) | Yes |
| D2 Model authorship of persistent canon under ratification, with provenance | [ADR-031](../decisions/ADR-031-model-authorship.md) | Yes, with a deterministic validator, proposal ledger, audit sample and disclosure |
| D3 A recorded, state-addressed render contract in place of renderer determinism | [ADR-030](../decisions/ADR-030-render-contract.md) | Yes |
| D4 Budgeted inhabitant cognition and an open agent roster | [ADR-032](../decisions/ADR-032-inhabitant-cognition.md) | Yes, after pilot evidence |
| D5 A scale registry and lateral kinds; no twelfth depth | [ADR-033](../decisions/ADR-033-scale-registry.md) | Yes to the registry; keep ADR-008 |
| D6 What must precede first production history | none | Only the identity/alias and provenance schema. Decided 2026-11-18 (item 17): the identity/alias migration comes before the first structural operation, not before the pilot |
| D7 One client | [ADR-005](../decisions/ADR-005-launch-operations.md) | Pilot `/app` default approved 2026-11-04 for consistent first arrival and return. Device and human gates remain. The current explorer moves to `/map` until the cohort read-out, and the shared React Map view lands at `/` (O10). The in-session World map is in `/app` beside the living scene (X1, #190); the public entry switch and the legacy `/map` alias follow in X2 |
| D8 Budget posture | none | Dollars per day, not calls per day |
| D9 Process re-tune | none | Keep five covenants; demote the rest to guidance. Closed as stale, 2026-11-18; no covenant is demoted, and three `AGENTS.md` wordings wait for the working-rules pull request (item 44) |

### Migration numbering rule

Migration numbers are assigned at merge time. The first batch to merge takes
the next free number. Drafts must not reserve numbers. The current top
migration on `main` is `0033_private_chat_reports` (private traveler chat and
reports, [ADR-040](../decisions/ADR-040-private-chat-and-reporting.md), #174).
Before it, `0032_model_spend` merged with the controlled-model batch
([ADR-039](../decisions/ADR-039-controlled-model-spend.md), #172); neither
number is provisional now, and neither migration enables a provider. ADR-029
through ADR-033 each describe a migration they would add; whichever of those
batches merges first takes the next free number. The open draft #183, the
ADR-041 naming change, may add one; if it merges first, it takes the next free
number.

### Known open conflicts (unresolved; pending owner decision)

Every entry below is now resolved; the heading is kept because other pages
link to its anchor. Line numbers in this section were re-read at the commit in
the verification stamp at the top of this page. Each link also carries its section anchor,
which survives edits that move lines.

- Resolved 2026-11-18 by the owner (item 17): ADR-029 batch 1 lands before
  the first structural operation, not before the pilot. ADR-029 batch 1 says
  it must precede first production history
  ([ADR-029](../decisions/ADR-029-evolution-grammar.md#implementing-batches-and-the-doors-they-trip)
  line 199). Decision C states "Before the first structural operation, not
  before the pilot."
  ([next-steps-2026-q4.md](next-steps-2026-q4.md#part-2-decisions-the-owner-must-make-and-by-when)
  line 127). The beta-readiness record states: do not add ADR-029
  implementation as a prerequisite for ordinary beta history on the evidence
  currently available; require it before enabling the structural operations
  that depend on it
  ([2026-10-03-beta-readiness.md](../evaluation/2026-10-03-beta-readiness.md#identity-timing-recommendation-not-ratification)
  lines 146–148).
- Resolved 2026-11-18 by the owner (section 3): there is no inhabitant
  cognition in the first cohort, and budgeted cognition and the open roster
  wait for pilot evidence. ADR-032 says batch 1 ships dark and can be turned
  on for the pilot cohort
  ([ADR-032](../decisions/ADR-032-inhabitant-cognition.md#d8-economics-and-gating)
  lines 208–209). The Q4 plan schedules D4 after the pilot: decision F says
  "D4 only after pilot evidence"
  ([next-steps-2026-q4.md](next-steps-2026-q4.md#part-2-decisions-the-owner-must-make-and-by-when)
  line 130), and the November–January order places ADR-032 batch 1 after
  pilot evidence, January at the earliest
  ([next-steps-2026-q4.md](next-steps-2026-q4.md#part-4-after-the-read-out-november-to-january-as-ratified)
  line 193). Row D4 of the
  [decision agenda](#decision-agenda-the-owners-only-bounded-d7-pilot-default-is-decided)
  above records the same timing.
- Resolved 2026-11-18 by the owner (section 3): ADR-032's solo puzzle
  attempts, persona tags and Speak delivery are superseded by the owner's
  decisions of 2026-11-06 and 2026-11-07 and by ADR-037. ADR-037 (D1, D2, D4 and D5 ratified 2026-11-18; the rest Proposed) talks to
  agents in chat and leaves Speak to places, keeps every traveler unlabeled,
  and lets an agent only suggest a puzzle
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

- **1.2** Activate hosted backups, in this order:
  1. Create the `backup` environment and limit its deployment branches to
     `main`.
  2. Set its secrets: `BACKUP_FLY_SSH_TOKEN` and the private-bucket secrets in
     [backup-bucket.md](../infrastructure/backup-bucket.md).
  3. Delete the repository copies of those secrets and any repository
     `FLY_API_TOKEN`. GitHub falls back to a same-named repository secret when
     an environment secret is missing (`.github/workflows/backup.yml`), so the
     job reads its credentials only from the `backup` environment (G4, #188)
     once this step is done.
  4. Set the repository variable `ENFOLDED_BACKUP_APP`.
  5. Dispatch `.github/workflows/backup.yml` by hand (SQLite validation,
     private bucket, no GitHub artifact) and confirm a validated snapshot was
     stored.
  6. Only then, before permanent history, set `ENFOLDED_BACKUP_REQUIRED=true`
     and enable the external schedule.
  7. Prove freshness with `scripts/backup_health.py` (runbook §7–§8;
     readiness record "Remaining gates").

  For production, O14 sets the same order after the first production deploy;
  the staging restore is the evidence before that boot. O7 names Cloudflare R2 with 30 days' retention. Item 11
  directs an outside scheduler to dispatch the backup every 30 minutes and
  requires the one-hour bound to be proven over seven consecutive days on the
  twin. The scheduler service is still the owner's to name, and the workflow
  still runs on GitHub's own cron. Kept as
  history, from the
  [2026-11-11 cadence record](../evaluation/2026-11-11-backup-schedule-cadence.md),
  which measured one run in about five hours on GitHub's own schedule.
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
  The tooling is on `main`: the manual twin redeploy workflow (#157), and
  the participant notice gate, the `0.1.2rc1` candidate and the hosted soak
  probe (#169; the
  [staging candidate record](../evaluation/2026-11-10-staging-candidate.md)
  holds the scope and the held operator settings). As of 2026-11-11, the
  last time it was checked, the twin had not been deployed through that
  workflow: `deploy-staging.yml` had zero runs. That hosted state has not
  been re-checked since. No `v0.1.2-qa.1` tag exists in the repository.
- **3.3** Cohort rhythm: a recurring gathering and a weekly read of
  `scripts/beta_metrics.py`. The
  [pilot protocol](../evaluation/2026-09-12-pilot-protocol.md) defines the
  measurements; depends on M7.
- **4.1** Litestream-style continuous replication, the first post-launch
  infrastructure batch (ADR-005; the phase-2 plan). The
  [2026-11-11 cadence record](../evaluation/2026-11-11-backup-schedule-cadence.md)
  lists bringing it forward as one of the owner's options for 1.2's one-hour
  bound; that is proposed by agent, not decided.
- **4.2** The `/app` device, accessibility and onboarding checks before using
  the cohort's devices. The owner selected `/app` as the pilot default on
  2026-11-04 (ADR-005); that choice does not supply the missing device or human
  evidence. Until X2 (#191) merges, `/` remains the world-map alternate
  (decision D7). After X2, `/` serves the React app and the old map moves to
  `/map` until the cohort read-out (O10).
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
- **4.5** Routing extraction from `server/handlers.py` (2,276 lines at
  `00fa804`). The
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
