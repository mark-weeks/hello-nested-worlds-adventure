# Roadmap index — what governs now

*Verified against `main` at #109 (`8cfa6cb`, 2026-10-03).* This is the one
place that says which roadmap documents are live, which decisions are open,
and which plans are archived. Update it whenever a plan ships, a decision is
ratified, or a document moves to [`docs/archive/`](../archive/README.md).

## Where the project stands

- **Not deployed.** The hosted world at enfolded.world has never run, the
  chronicle is empty, and there are no external players. Three QA prereleases
  were cut for local QA (`v0.1.0-qa.1` and `v0.1.1-qa.1` on 2026-08-30,
  `v0.1.1-qa.2` on 2026-08-31); no production release has been cut. The
  [beta readiness record](../evaluation/2026-10-03-beta-readiness.md) (#109)
  names October 31 as a conditional target for an 8–12 person invited study
  and lists the hosted and human gates still open: backup activation, hosted
  restore, freshness alerting, live models, hosted runtime and devices,
  first-session observations, the seven-day return.
- **Shipped on `main` since `0.1.0-beta`** (newest first; the `[Unreleased]`
  section of [`docs/CHANGELOG.md`](../CHANGELOG.md) holds the measured record):
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
- **Open:** M7 (pilot cohort) and M8; deployment and its launch gates;
  ratification of the implemented-but-Proposed contracts — ADR-019 through
  ADR-022 (M1–M4) and the bounded parts of ADR-013 and ADR-014 realised under
  ADR-024/025 — whose code is merged while their status is still Proposed;
  ADR-012's direction, realised so far only as that bounded first situation;
  ADR-015 through ADR-018 (referential puzzles, spoken interaction,
  multidimensional leaderboards, collectibles), which remain unimplemented
  directions pending both implementation and ratification; ratification of
  the ADR-029 through ADR-033 drafts; ratification of
  [ADR-035](../decisions/ADR-035-openai-compatible-chat-completions.md), a
  Proposed design for a second text adapter that registers nothing and
  changes no runtime behavior; the decision agenda below.

## Live documents

| Document | What it governs | Status |
|---|---|---|
| [Discovery, identity and return](discovery-and-return.md) | Product sequence M0–M8, pilot gates, identity stages, the puzzle and speech tracks | M1–M4 merged; bounded M0/M5/M6 merged (#100, #101); M7 and M8 open |
| [Phase 2 scale plan](phase-2-scale.md) | The standing continuity policy; capacity triggers at 100 users and beyond | Standing; edit in place as triggers fire |
| [Community Ideas board](community-ideas.md) | Player-submitted ideas, support votes, moderation, explicit GitHub promotion | Merged (#102–#104); not deployed |
| [Expressive world: next steps](expressive-world-next-steps.md) | The boundary of the #105–#107 batches and their remaining gaps | Checkpoint; the gaps feed the decision agenda |
| [Beta readiness record](../evaluation/2026-10-03-beta-readiness.md) | Beta scope and promise, the #109 evidence for the remaining launch gates and their owners, the October 31 conditional target | Current (#109); not launch approval. The checklist governs exit criteria; the Q4 plan governs order |
| [Beta launch checklist](beta-launch-checklist.md) | Exit criteria before 8 to 12 invited people play: 95 items, evidence, and the decisions held for the owner. The Q4 plan governs order | Living. Statuses are as of `main` at `23b8830` (2026-11-02). Thresholds marked as proposals are not decided |
| [Owner decision packet, November 2026](decision-packet-2026-11.md) | Twelve decisions with needed-by dates, what each blocks, and options with costs: S5 chat permanence, the newcomer-watch venue, puzzle failure semantics, world status, minimum tester age, the re-plan date, reserving Observer and Scout, the lapsed Q4 decisions A, C and H, S2, E2 and Q4 decision I | Every recommendation is proposed by agent; not decided. Records no decision (2026-11-02, `23b8830`) |
| [Newcomer watch facilitator kit](../evaluation/2026-11-02-newcomer-watch-kit.md) | Setup, script, capture and teardown for 2 to 3 protocol-2 newcomer sessions on a local, declared-disposable world | Draft, contingent on the owner's venue ruling (packet decision 2). Recruits nobody |
| [Pilot protocol 2](../evaluation/2026-09-12-pilot-protocol.md) | The M7 study: curiosity, attempted-action and observed-consequence understanding, unprompted and useful return | Ready to run; no cohort observed |
| [2026-10-03 assessment](../evaluation/2026-10-03-ambition-and-boundaries.md) | The decision agenda and a proposed 90-day sequence | Findings for the owner; ratifies nothing |
| [Next steps, Q4 2026](next-steps-2026-q4.md) | The dated critical path to the M7 pilot, the owner's decisions and their needed-by dates, the parallel maintenance track, and the November–January batch order for ADR-029 to ADR-033 as ratified | Plan (2026-10-04); ratifies nothing |

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
migration in this tree is `0030_cost_budget_names` (`main` before this batch is `0029_sanctions`). ADR-029, ADR-030,
ADR-032 and ADR-033 each describe a migration they would add; whichever of
those batches merges first takes the next free number.

### Known open conflicts (unresolved; pending owner decision)

- ADR-029 batch 1 says it must precede first production history
  ([ADR-029](../decisions/ADR-029-evolution-grammar.md) line 192). Decision C
  states "Before the first structural operation, not before the pilot."
  ([next-steps-2026-q4.md](next-steps-2026-q4.md) line 110). The beta-readiness
  record states: do not add ADR-029 implementation as a prerequisite for
  ordinary beta history on the evidence currently available; require it before
  enabling the structural operations that depend on it
  ([2026-10-03-beta-readiness.md](../evaluation/2026-10-03-beta-readiness.md)
  lines 130–132).
- ADR-032 says batch 1 ships dark and can be turned on for the pilot cohort
  ([ADR-032](../decisions/ADR-032-inhabitant-cognition.md) lines 201–202). The
  Q4 plan schedules D4 after the pilot: decision F says "D4 only after pilot
  evidence" ([next-steps-2026-q4.md](next-steps-2026-q4.md) line 113), and the
  November–January order places ADR-032 batch 1 after pilot evidence, January
  at the earliest ([next-steps-2026-q4.md](next-steps-2026-q4.md) line 171).
  The decision agenda above records the same timing (line 69).
- Resolved 2026-10-25 by the owner in chat. ADR-004 section 2 said
  "Fail-open everywhere" for moderation, and no open agenda item covered that
  posture before outside players arrived. The amendment in
  [ADR-004](../decisions/ADR-004-day-one-data-policy.md) (2026-10-25 moderation
  amendment) closes it: shared text fails closed when moderation cannot
  complete, and private or solo-only text and mechanical gameplay stay
  fail-open. The D1–D9 agenda (lines 64–74) and the Q4 decisions A–H
  ([next-steps-2026-q4.md](next-steps-2026-q4.md) lines 106–115) are unchanged.

## Standing commitments carried from archived plans

Still open when the ensemble action plan was archived; its item numbers are
kept so the archived text can be cross-read.

- **1.2** Activate hosted backups: set `FLY_API_TOKEN`, the private-bucket
  secrets and variables in [backup-bucket.md](../infrastructure/backup-bucket.md),
  `ENFOLDED_BACKUP_APP`, and, before permanent history, `ENFOLDED_BACKUP_REQUIRED=true`;
  dispatch `.github/workflows/backup.yml` (every 30 minutes, SQLite validation,
  private bucket, no GitHub artifact), and prove freshness with
  `scripts/backup_health.py` (runbook §7–§8; readiness record "Remaining gates").
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
  approves no destination, and does not run the comparison.
- **4.5** Routing extraction from `server/handlers.py` (1,612 lines). The
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
