# Roadmap index — what governs now

*Verified against `main` at #109 (`8cfa6cb`, 2026-10-03).* This is the one
place that says which roadmap documents are live, which decisions are open,
and which plans are archived. Update it whenever a plan ships, a decision is
ratified, or a document moves to [`docs/archive/`](../archive/README.md).

## Where the project stands

- **Not deployed.** The hosted world at enfolded.world has never run, the
  chronicle is empty, and there are no external players. Two QA prereleases
  (`v0.1.1-qa.1`, `v0.1.1-qa.2`) were cut from `main` on 2026-08-31 for local
  QA; no production release has been cut. The
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
  ratification of ADR-012 through ADR-022 (their code is merged, their status
  is still Proposed) and of the ADR-029 through ADR-033 drafts; the decision
  agenda below.

## Live documents

| Document | What it governs | Status |
|---|---|---|
| [Discovery, identity and return](discovery-and-return.md) | Product sequence M0–M8, pilot gates, identity stages, the puzzle and speech tracks | M1–M4 merged; bounded M0/M5/M6 merged (#100, #101); M7 and M8 open |
| [Phase 2 scale plan](phase-2-scale.md) | The standing continuity policy; capacity triggers at 100 users and beyond | Standing; edit in place as triggers fire |
| [Community Ideas board](community-ideas.md) | Player-submitted ideas, support votes, moderation, explicit GitHub promotion | Merged (#102–#104); not deployed |
| [Expressive world: next steps](expressive-world-next-steps.md) | The boundary of the #105–#107 batches and their remaining gaps | Checkpoint; the gaps feed the decision agenda |
| [Beta readiness record](../evaluation/2026-10-03-beta-readiness.md) | Beta scope and promise, the remaining launch gates and their owners, the October 31 conditional target | Current (#109); not launch approval |
| [Pilot protocol 2](../evaluation/2026-09-12-pilot-protocol.md) | The M7 study: curiosity, attempted-action and observed-consequence understanding, unprompted and useful return | Ready to run; no cohort observed |
| [2026-10-03 assessment](../evaluation/2026-10-03-ambition-and-boundaries.md) | The decision agenda and a proposed 90-day sequence | Findings for the owner; ratifies nothing |

## Decision agenda (the owner's; nothing here is ratified)

The 2026-10-03 assessment put nine decisions to the owner. Five are drafted as
ADRs. All five are **Proposed** and introduce no runtime behavior, migration or
write path; citing them authorizes nothing.

| Decision | Draft | Recommendation in the assessment |
|---|---|---|
| D1 Evolution grammar: births, renames, re-aspect, traversal reparenting, merge/retire, era turns and law shifts as chronicled events | [ADR-029](../decisions/ADR-029-evolution-grammar.md) | Yes |
| D2 Model authorship of persistent canon under ratification, with provenance | [ADR-031](../decisions/ADR-031-model-authorship.md) | Yes, with a deterministic validator, proposal ledger, audit sample and disclosure |
| D3 A recorded, state-addressed render contract in place of renderer determinism | [ADR-030](../decisions/ADR-030-render-contract.md) | Yes |
| D4 Budgeted inhabitant cognition and an open agent roster | [ADR-032](../decisions/ADR-032-inhabitant-cognition.md) | Yes, after pilot evidence |
| D5 A scale registry and lateral kinds; no twelfth depth | [ADR-033](../decisions/ADR-033-scale-registry.md) | Yes to the registry; keep ADR-008 |
| D6 What must precede first production history | none | Only the identity/alias and provenance schema |
| D7 One client | none | `/app` primary, explorer retired after the device gates; needs an ADR-005 update |
| D8 Budget posture | none | Dollars per day, not calls per day |
| D9 Process re-tune | none | Keep five covenants; demote the rest to guidance |

Known conflict to settle before building either draft: ADR-029 and ADR-030
both claim migration number 0028.

## Standing commitments carried from archived plans

Still open when the ensemble action plan was archived; its item numbers are
kept so the archived text can be cross-read.

- **1.2** Activate hosted backups: set `FLY_API_TOKEN`, `ENFOLDED_BACKUP_APP`
  and, before permanent history, `ENFOLDED_BACKUP_REQUIRED=true`; dispatch
  `.github/workflows/backup.yml` (now every 30 minutes with SQLite validation),
  inspect the artifact, and prove freshness with `scripts/backup_health.py`
  (runbook §7–§8; readiness record "Remaining gates").
- **1.3** Run the ADR-005 staging rehearsal on the disposable twin (runbook §3a):
  2–3 observed newcomer sessions, WebSocket soak, live-voice and intention
  probes, and a restore of a downloaded hosted artifact into isolated staging.
- **3.3** Cohort rhythm: a recurring gathering and a weekly read of
  `scripts/beta_metrics.py`. The
  [pilot protocol](../evaluation/2026-09-12-pilot-protocol.md) defines the
  measurements; depends on M7.
- **4.1** Litestream-style continuous replication, the first post-launch
  infrastructure batch (ADR-005; the phase-2 plan).
- **4.2** The `/app` device, accessibility and onboarding gate that precedes any
  change to the invite default (ADR-005, 2026-09-12 revision; decision D7).
- **4.3** The world-speaks-first experiment, now subsumed by the ADR-032 draft.
- **4.4** A model A/B on live transcripts; the assessment recommends moving the
  default voice model off `claude-opus-4-8` in its Phase 0.
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
