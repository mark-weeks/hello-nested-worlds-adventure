# Decision renewal: discovery, continuity and return

**Baseline:** `a8bfcb332539cd56174cb3c221ebbe6817723430` (current main inspected
September 12, 2026). **Authority:** the owner's request to implement the preceding
decision review. Work is isolated on `codex/discovery-return-contracts`; no
production database, deployment, merge or external publication is part of it.

The project has outgrown generated breadth as its main invitation, credentials
as resource ownership, rebuilt active puzzles, and a migration plan that treats
newly accepted history as disposable. It retains its useful foundations: one
shared world, immutable born identity, append-only consequences, per-node puzzle
difficulty, ordinary seals, M1/M2 recovery, M3 provenance and M4 discovery memory.

## Implemented decisions

| Review recommendation | Reviewable result | Remaining evidence boundary |
|---|---|---|
| Give a new arrival a coherent question | Operator-installed signal investigation across eight existing nodes at four scales, with a curated entry and meaningful late-arrival state | Curiosity requires observation of people. |
| Revisit generic repair and first-arrival wins | Preserve/release choices with distinct costs; one changeable preference per participant; a shared window, majority settlement and tie extension | A short window can favor early arrivals. Test timing and fairness. |
| Separate identity from credentials | Opaque participant ownership, explicit credential aliases, operator rotation, private notes/home and selectively published bio/goals/preset avatar | Independent invites remain independent accounts; self-service recovery and live-presence avatar rendering are later work. |
| Preserve accepted intent and active content | Pinned puzzle definitions plus original public evidence; stale-instance rejection; transactional request receipts used by both clients and required by situation choices | Unknown future definition versions require compatible interpreters. Never reconstruct an unrecorded older question. |
| Give an inhabitant a real commitment and relevant recall | Tessera's queued, durable mark; bounded retrieval of actual public commitment records; journal recap selected from saved places and joined investigations | No live model-quality or long-term relationship claim; notes never enter prompts. |
| Make the scene the primary product development surface | Investigation in `/app`, narrow-screen layout, visible text fallback on renderer failure, map compatibility and shared retry logic | Invite default remains `/` until the device/accessibility/onboarding gate is reviewed. |
| Retire the mechanical database-migration doctrine | Revised ADR-003 and scale/runbook guidance: measure first, preserve transaction contracts, quiesce all writers and reconcile post-cutover writes | SQLite retained; no production capacity benchmark, Postgres port or off-host restore rehearsal claimed. |
| Measure reasons to return | Separate pilot protocol and executable report with metric-specific denominators, unknown observations, duplicate rejection and reminder exclusion | No cohort has been recruited or observed in this batch. |

ADRs [024](../decisions/ADR-024-participants-and-active-content.md) and
[025](../decisions/ADR-025-first-situation.md) state the bounded contracts.
The [pilot protocol](2026-09-12-pilot-protocol.md) keeps research separate from
fictional history and private journals. The Ideas roadmap reuses the participant
ID rather than creating another community identity; the board itself remains
outside this batch.

## Verification

`ENFOLDED_E2E=1 ./scripts/check.sh` passed using pinned Python 3.11 and Node
20.19.0: Ruff clean; **1,101 Python tests** (137.62 seconds); **110 Vitest tests**;
production build with byte-fresh committed assets; installed-wheel smoke passed;
**41 Playwright tests** (2.2 minutes). All application code was in place for this
run. Subsequent changes were documentation and a browser-test refinement for
portable capture paths and an explicit keyboard destination assertion.
The refined discovery suite passed **6/6** in 22.5 seconds. Changed Markdown
references and `git diff --check` also pass.

Behavioral coverage includes concurrent identity creation, rotation preserving
notes and old conversation aliases without rewriting history, cross-account
privacy, receipt/effect rollback, replay and changed-intent refusal, active puzzle
content surviving generator changes, renewal racing acceptance, escaped original
evidence, canonical-world rejection, both situation branches, tie/change handling,
late entry, duplicate workers, post-delta failure, real process SIGKILL,
backup/restore with a pending promise, bounded recall amid chatter, and independent
queue failure. Pilot tests distinguish unknown from negative observations and
reject duplicate participant rows and reminder-driven return claims.

Chromium drives the actual production bundle and Python endpoints using
disposable databases: both branches through notes/public profile/late aftermath,
accepted-act response loss and reload in both clients, 390px and 320px layouts,
keyboard travel without GPU contexts, and renderer-initialization failure with a
navigable text scene. The browser situation fixture uses a four-second window,
one-second steps and a 0.2-second pump; product defaults remain 60/20/5 seconds.
These accelerated runs prove delivery and client behavior, not experienced pacing.

Visual inspection covered the scene at 1280×900 and 390×844 and journal captures.
Findings led to responsive stacking, legible focus styles, moving the back control
away from the scene title, and scrolling the explorer sidebar so an action cannot
be obscured by the status/mode panels. The local browser server fixture now uses
an explicit temporary DB rather than depending on a HOME override.

The first complete Python pass found one outdated schema assertion (20 instead
of the new schema head), with 1,092 other tests passing. The retained upgrade test
still compares old world/history/hinge/queue data before and after migration.
Browser testing found a real obscured-action defect and distinguished GPU-free
canvas rendering from total renderer failure; those are now separate cases.
A 12-second browser wait could race the ordinary five-second pump, so the
isolated browser fixture accelerates its pump explicitly instead of relying on
an incidental scheduling phase.

## Continuity assessment

Three additive migrations create participant ownership/private data, active
puzzle definitions/request receipts, and the first situation's instances and
recoverable work. Four new append-only situation event kinds record opening,
commitment, ordered consequences and a participant's reference marker. Their
writers are in `persistence/situations.py`; effects use the existing delta/version
path. The owner's implementation request supplies scoped authority, documented
in ADR-024/025. Production opening is an explicit operator command after the
runbook's staging/backup review, not an application startup side effect.

No generator banks, birth goldens, generator version, born node rows, pinned
world metadata or era-name banks change. Existing causal and maturation rows
retain their versioned interpretation. No historical rows are edited. Private
notes/profile choices are editable operational resources, separate from history.
Retained definitions and receipts add storage; archival requires its own contract.

## Limits

The unsigned inscription is authored evidence with an unknown maker; it does not
claim a former player. The reference marker is a real shared delta, but whether
it creates a worthwhile next action is unproven. A promise that finishes within
the first session may be too weak to motivate next-day return. Device emulation
and keyboard checks are useful evidence, not a full assistive-technology audit
or Safari/iOS certification. The human pilot and production rehearsal remain
explicit work, without claiming this local implementation performed them.
