# Beta readiness: current experience, recovery, and observed return

**Date:** 2026-10-03. **Baseline:** `9be903dcbd2620de557b146e7f42e652cf7e24fd`.
**Status:** readiness implementation and local rehearsal; not launch approval.
The owner requested the actions available now after reviewing the readiness
findings. This batch changes instructions, research reporting, backup verification,
the server's startup and waiting-connection backlog, and tests. It does not deploy, change credentials/access, recruit participants,
ratify proposed ADRs, or change the public client default.

## Assessment of the attached review

The four central findings are valid. The newer baseline adds proposed ADRs and an
ambition assessment but no runtime changes relative to the reviewed `20c3f10`.
A canonical local checkout is available now; the original review's inability to
find one was an access limitation, not evidence that no checkout existed.

| Finding | Assessment and disposition |
|---|---|
| Off-host recovery is unproven | Confirmed: run `37103410985` skipped backup/download/upload; newer run `37123272246` also produced no recovery artifact. The live artifact check returns missing. Local safeguards and rehearsal now exist; hosted proof remains required. |
| Pilot and onboarding are stale | Confirmed against the retired HTTP choice path and current Act surface. Protocol, guide, README, and launch guidance are corrected in this batch. |
| Motivation and useful return are unvalidated | Valid evidence gap. Automated passing checks do not close it; the revised study is ready to run. |
| Selected-release production readiness is unproven | Valid evidence gap. Full local checks now pass, but deployed revision, recovery, live models, monitoring, and target devices remain separate gates. |

“Enough implemented capability” is a reasonable scope judgment for an invited
study. “Ready on October 31” is conditional, not established by the code review.
Keep the feature set bounded and spend the next effort on recovery and observed
play. More capability is justified when those observations identify a need.

## Beta scope and promise

Prepare one continuing seed-382 world for 8–12 invited people. Test exploration,
Speak, Puzzle, Act, journal/recap, and Ideas. Actions commit attempts and resolve
against the conditions they meet. Optional sound is available. New rankings,
spoken input/playback, crafting, guilds, Hyperleap, and expanded agent cognition
are outside this batch. Observed navigation or consequence-recognition failures
remain actionable even when they are called polish.

The explorer remains the invite default under ADR-005; the scene is available as
an alternate. Desktop Chromium is the locally exercised browser, not a promise
of support on every device. Before recruitment, list the cohort's actual devices
and complete the applicable browser, keyboard, accessibility, and fallback checks.

Use disposable staging for 2–3 newcomer sessions and operational rehearsal. Tell
those participants their world is temporary. Before the seven-day cohort, declare
whether its world is retained research or production; never reset a world promised
to persist. The staging/production boundary and invitations need an operator decision.
October 31 is a conditional target, with the seven-day study ideally complete by
October 24. The calendar is not a substitute for recovery or observed play.

### Open-issue disposition

Read [#87](https://github.com/mark-weeks/hello-nested-worlds-adventure/issues/87),
[#88](https://github.com/mark-weeks/hello-nested-worlds-adventure/issues/88), and
[#89](https://github.com/mark-weeks/hello-nested-worlds-adventure/issues/89) on
October 3; all remain open. No issue was edited or closed.

| Issue | Beta decision |
|---|---|
| #87, stateful visuals and direct navigation | Partly overlaps the shipped scene/history and visual-language work. Full acceptance is not demonstrated: the blinded 80% scale-classification test and complete spatial-hotspot criteria remain unverified. Fix observed orientation/consequence-recognition problems; do not require the whole epic before the study. |
| #88, Hyperleap | Defer. The epic introduces destination eligibility, recorded movement, and a new navigation action. There is no participant evidence here that it is necessary for a useful first visit or return. |
| #89, scale actions and puzzle progression | Substantial overlap with current scale-native actions and durable puzzle work, but neither complete reward/ecology coverage nor strategic value is established. Its requirement that every action response contain a property delta conflicts with ADR-028's accepted/pending/partial/moot outcomes. Revise those criteria before further implementation; preserve bounded Act behavior and use the pilot to identify any missing reason to return. |

## Completed changes

- Revised [protocol 2](2026-09-12-pilot-protocol.md) replaces the retired signal
  branches with free exploration, attempted-action understanding, observed
  consequence understanding, and return evidence. The session script, consent/data
  boundaries, optional prompt, denominators, and decision guidance are runnable.
- `scripts/pilot_report.py` accepts a versioned protocol-2 record. It refuses old
  choice fields, scoring observers as failed actors, incomplete return windows,
  and useful-return observations without an observed return. Legacy list files
  remain explicitly protocol 1; their data is not reinterpreted or pooled.
- README and development notes describe the current Act and Ideas experience.
  The player guide no longer promises a consequence preview. The August beta
  brief is explicitly historical rather than silently presented as current.
- The [launch runbook](../infrastructure/fly-deployment.md) uses v3 attempts and
  recovery cases rather than opening a scripted situation. It distinguishes
  local checks, hosted rehearsal, real model quality, and human observations.
- `backup.yml` can target an explicitly configured app. With repository variable
  `ENFOLDED_BACKUP_REQUIRED=true`, missing Fly credentials fail; malformed values
  also fail instead of disabling enforcement. Prelaunch no-ops are labeled inactive.
  Backups run every 30 minutes against the unchanged 60-minute freshness limit.
  Downloaded SQLite files are retained even if integrity, journal-mode or schema
  validation fails; those copies have a quarantine prefix and leave the run failed.
  Healthy artifact names identify the app and snapshot-start time.
- `scripts/backup_health.py` checks all GitHub artifact pages, ignores other apps,
  expired/empty/quarantined copies and future timestamps, and uses snapshot time
  rather than upload time. It also verifies successful completed `backup.yml` run
  provenance on `main` in the same repository. It exits nonzero for missing, stale,
  or unavailable evidence. It runs independently after completion: requiring a
  running workflow to prove its own final success would prevent first activation.
  The independent scheduler and notification destination still need configuration.
- The server accepts a waiting-connection backlog of 64 rather than Python 3.11's
  default 5. The existing 12-client concurrent-voting test reproduced connection
  resets before this change; the complete Ideas suite and final release checks
  pass afterward. This is local burst evidence, not a hosted capacity claim.
- The shared server avoids reverse DNS when setting its display name, so the fix
  covers production, direct test constructors, and the browser/recovery launcher.
  A captured startup traceback identified the lookup as the cause of a 15-second
  rehearsal timeout. Bound addresses and port behavior remain unchanged.

## Recovery evidence and its limits

`tests/test_beta_rehearsal.py` starts a real HTTP server against a disposable
world. It closes the invite gate, saves a private note and position, opens a
puzzle, accepts a delayed v3 Scatter, rotates the credential, and takes an online
snapshot. It kills the server, copies only the completed backup file, makes that
copy read-only, restores into a different database, and starts a fresh server.

The rehearsal verifies:

- Download-equivalent local copy has SQLite integrity `ok`, `DELETE` journal mode,
  no required WAL sidecar, and a logical digest identical to the restored database.
- The participant ID and saved position survive; the old credential stays revoked.
  The owner can read the note; the second participant cannot.
- The opened puzzle definition survives. Original request replay recovers the
  accepted receipt with one pending attempt.
- Accelerating only the disposable worker clock changes density 400 → 360,
  completes downstream work, and makes repeated receipt retries/drains inert.
- Every fixture history row joins to its born node by seed/name without rewriting
  the history, supporting the identity feasibility argument below.

This is not a downloaded hosted artifact or a Fly recovery rehearsal. It does not
measure production restore time, live-model quality, capacity, or natural-play
frequencies. Existing process-death/retry and browser tests provide additional
local coverage; none supplies human comprehension or return evidence.

## Identity timing: recommendation, not ratification

**Do not add ADR-029 implementation as a prerequisite for ordinary beta history
on the evidence currently available. Require it before enabling the structural
operations that depend on it.** ADR-029 remains Proposed and unchanged.

The narrow argument:

1. `persistence/migrations/0013_world_nodes.sql` already stores `(world_seed, path)`
   as the primary key and the immutable born name alongside it. Its original
   migration comment explicitly describes mapping existing name-keyed chronicle
   rows to these stored nodes without a history migration.
2. `multiverse/store.py::resolve_node_by_name` resolves the name's path suffix and
   verifies it against the stored born name. Existing application operations do
   not rename that row. Until the first rename, a stored seed/name therefore has
   a stable referent; an alias can be seeded from the born row later.
3. An additive alias table and read-time joins can preserve old rows unchanged.
   New writes may acquire path fields when that feature is implemented. History
   before aliases retains the born name; the first actual rename needs its own
   alias interval and chronicled structural event before it can be accepted.
4. The new local fixture checks the join over populated history. This establishes
   feasibility for that fixture, not completed migration readiness for every
   legacy database or every nested payload.

Before implementing ADR-029, audit a representative authorized backup for missing
born rows, duplicate names, legacy name formats, and orphan references. Then test
all name-keyed consumers: history/Wayback, overlays, opened puzzles, saved positions,
home/notes, agent memory/attention, every queue and frozen interpreter, receipt
replay, and generation from born identity. Unresolvable historical names must remain
explicit; never guess lineage or rewrite history to make the migration pass.

What cannot be retrofitted is provenance for a structural change that was never
recorded. That is a boundary before the first such change, not evidence that all
ordinary history must wait. Accepting this recommendation is not approval to add
renaming, frontier growth, model authorship, or any of ADR-029–033's write paths.

## Remaining gates and owners

| Gate | Current evidence | Next responsible action |
|---|---|---|
| Hosted backup activation | Read-only GitHub artifact check returned `missing`; no qualifying app-specific copy | Operator configures target app, token and required flag, then dispatches and inspects backup runs. |
| Hosted restore | Local cold-process rehearsal passes; no hosted artifact available | Operator downloads the intended app's backup and restores into isolated staging; records checksum, release, timing, identity/privacy and queue results. |
| Freshness alerting | Script and workflow checks implemented locally | Operator configures an independent check and notification destination, and exercises a stale/missing condition. |
| Live models | No model API credential available in the checked environment | Operator supplies authorized staging model configuration; run node voice and intention success/clarification/refusal probes. |
| Hosted runtime and devices | Local browser evidence only | Verify deployed SHA, closed gate, budgets, monitoring, WS/reconnect and cohort devices on the selected build. |
| First-session observations | Script prepared; no newcomers observed | Research lead recruits 2–3 staging participants, obtains consent and observes without leading. |
| Seven-day return | Protocol/report ready; no cohort data | Research lead declares retained-world status, observes 8–12 people and reports counts/unknowns before recommending expansion. |

No Fly CLI, Fly API token, or model API key was present in the current process or
checked checkout configuration. This does not establish that production does not
exist or that credentials do not exist elsewhere. No secret values were printed.

## Verification before PR review

On Python 3.11 and Node 20.19.0, `ENFOLDED_E2E=1 ./scripts/check.sh` completed with
exit 0: Ruff passed; **1,382 Python tests passed in 245.90 seconds**; **131 Vitest
tests passed**; the production bundle was byte-fresh; installed-wheel smoke passed;
**96 Playwright tests passed in 2.4 minutes** under the production CSP.

The first full Python pass had 1,380 passes and two failures: the new recovery
fixture's startup timeout and the existing concurrent-voting reset. Both were
investigated and fixed as described above. After the backlog change, all 36 tests
across the Ideas suite and recovery rehearsal passed before the final full gate.

Manual local inspection covered the corrected guide, invite entry, the explorer's
Act controls, and the scene alternate at the saved place. Both exposed the current
four scale-native actions and intention entry. The browser's captured error log
was empty. The local fixture was stopped afterward. This does not establish human
comprehension, model quality, or physical-device accessibility.

The protocol's JSON example parsed and reported all five metrics as unknown;
all 83 local link targets in the final changed Markdown existed.
The backup workflow parsed as YAML, its gate passed shell syntax validation,
and the final diff passed whitespace validation.

Dependency triage found one high-severity production dependency entry from
`npm audit --omit=dev`: transitive `@xmldom/xmldom` (affected through 0.8.14;
[upstream advisory](https://github.com/advisories/GHSA-8344-3jmq-59r6)). A write-disabled
production build's emitted module graph contained zero `@xmldom` or
`WebWorkerAdapter` modules. Pixi's browser adapter uses the browser's native parser;
the worker adapter imports xmldom. This supports deferring a dependency update
from this batch, not declaring the package safe. Update it before introducing
that worker path and recheck dependencies when selecting the release. No lockfile
or dependency versions changed here.

## PR #109 review corrections

All 11 inline findings were accepted, including the non-blocking test/tooling gaps.

| Review concern | Correction and evidence |
|---|---|
| Repository-variable typos silently disable enforcement | Pass the raw value into the shell gate; test unset, false, true, typo, uppercase and numeric values, with and without a token. Invalid values fail even with credentials present. |
| A matching artifact name can come from an unrelated run | Match trusted workflow ID/path, completed success, main branch, schedule/manual event, repository identity and commit metadata. Tests reject foreign, failed and in-progress runs; a real subprocess with a fixture GitHub CLI exercises the API calls. |
| Validation failure loses the downloaded off-host copy | Retain every successfully downloaded file through an always-run upload. Failed validation uses `unvalidated-worlds-backup-...`, keeps the workflow failed and cannot satisfy freshness. Current, older-schema and damaged SQLite fixtures remain byte-identical after validation. Hosted upload remains unexercised without Fly credentials. |
| Read-only URI handling and connection cleanup | Use explicit `uri=True` and `closing()` in validation and rehearsal; missing paths are not created, and filenames containing URI metacharacters work. |
| Hourly cadence leaves no freshness slack | Run at :17 and :47, retaining the one-hour recovery threshold. This improves headroom without weakening ADR-005; scheduling failure still needs independent monitoring. |
| Reverse DNS still blocks shared/production constructors | Move the bind override into `_ThreadedServer`; loopback and wildcard listeners bind/connect when `getfqdn` is forced to fail. |
| Hidden startup errors and fixture coupling | Capture bounded stderr diagnostics, distinguish early exit/bad port/timeout, and clean up failed children. Move shared accounts/HTTP fixtures to `conftest.py`; the reusable Python helper and Playwright both invoke `scripts/e2e_server.py`. |
| Top-level pilot fields bypass row validation | Reject extra envelope fields without echoing private content. |
| Backlog change lacks portable regression coverage | Queue 32 real HTTP requests before starting accept and verify connections remain open. A handshake-only control could pass before asynchronous resets; the corrected test passes at backlog 64 and fails with backlog 5 restored in memory. |

Review verification: focused backup/protocol validation passed **55 tests**;
server, recovery, participant, Ideas and intervention checks passed **83 tests**.
The corrected startup/burst checks passed **6 tests**, and the old-backlog control
failed as intended. The final canonical gate exited 0: Ruff passed; **1,417 Python
tests passed in 246.97 seconds**; **131 Vitest tests passed**; the production bundle
was byte-fresh; installed-wheel smoke passed; **96 Playwright tests passed in
2.7 minutes**. Actionlint 1.7.12 validated the workflow structure and expressions;
shell syntax, 83 local Markdown targets, protocol JSON and diff whitespace passed.
The revised live read-only checker returned missing. Hosted checks run on the
published PR revision; hosted recovery and participant gates remain outstanding.

**Irreversibility check:** none — no migration, golden re-pin, generator/born-row
change, new application chronicle writer, world-meta/hinge pin, or era-bank edit.
The diff contains documentation, research/backup tooling, workflow checks, one guide
sentence, shared server startup/backlog behavior, and test infrastructure. All rehearsal effects
are confined to disposable databases.
