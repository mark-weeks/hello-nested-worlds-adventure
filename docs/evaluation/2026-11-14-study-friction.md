# Study-admission scope — 2026-11-16

The #173 admission-only change is rebased onto merged main `bf05f5a` (#174),
whose tree is identical to the tested #174 head `a37245a`. The admission scope
and Go/no-go text come from #173 candidate `e7857ff`. The
[owner decision on PR #173](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/173#issuecomment-6896202913)
rejects the earlier explorer retirement and directs a fresh admission-only branch
under the existing PR number. The previous branch is retained locally for history;
its retired-client runtime changes and verification are not imported into this
admission change. Runtime landed with #174 and is unchanged by this admission batch.

## Included

- Eight entry requirements with separate Watch and Cohort columns; study outcomes
  and later improvements remain separate from entry.
- All 95 inventory IDs and the other 94 criterion/status/evidence records from
  #174, including #171's P3 snapshot-start freshness criterion and #172's
  destination/dollar-spend controls. The S4 exception below is owner-directed.
- A recorded watch before the cohort, plus the cohort-specific requirements.
- AI-off route permissions through the frozen policy; the moderation off-switch is
  not an AI-off mechanism and safe holds remain required.
- S4 keeps #173's explicit adult-entry criterion and Partial classification,
  using implementation evidence inherited from #174. Personal invite holders
  acknowledge age/current notice regardless of collection. The minimum age is
  fixed at 18 in code; the legacy TEST_MIN_AGE setting is optional and accepts
  only 18. This batch adds no runtime behavior and establishes no hosted
  sign-up result.
- ADR-005's amendment is limited to study entry; agent-rule changes stay in #175.

## Cohort requirements

The owner supplied “Enfolded · decisions on open PRs #173, #174, #175 · 15 Nov
2026”, **version 4**, directly in the working chat after the public decision
comment. Decision 3 states the three additional requirements:

> Before the cohort: a report reaches a person within 24 hours, there is a same-day
> path for threats or doxxing, someone is named on duty each day; the cohort runs
> on an exact, labelled release that passed every automated test; and every
> full-checklist item applies to the cohort unless the owner excuses it in writing.

These are now recorded above and in the Watch/Cohort checklist. No stage label or
watch-only applicability choice excuses a cohort item; record the owner's written
exception against the item ID. Decision 6 additionally requires the report queue
to be checked twice a day and a second operator to be named before the cohort.
The source gap is closed; no requirement is claimed satisfied by recording it.

The published review follow-up restored all 20 inventory/reference section links
in Contents and the CHANGELOG continuation format. Watch requirement 4 keeps the
assigned operator (the owner for the watch) checking open and acknowledged
queues at least twice a day when traveler messages and in-client Report are enabled. The cohort uses an assigned operator and requires a second operator
in place before it starts. The [operator queue guide](../development/community-reporting.md#operator-queue)
is part of merged #174 and its link resolves.

This admission change reconciles S4 against merged #174: the other 94 records remain
unchanged, including #174's Partial G2/G12 report evidence. It counts **13 Done,
45 Partial, 35 Not started and 2 Unknown**. Stage totals remain **40 admission
evidence, 22 study measurement and 33 later improvement**. These counts describe
the evidence inventory; they do not establish study admission readiness.

## Excluded

The map, D3, nodeart, root response, client features, two-client E2E coverage,
third-party notices, wheel checks, runtime and capture tooling are identical to
the merged #174 base. No client consolidation, documentation-test shortcut,
covenant rewrite, new runtime implementation, migration or historical-state
change is added by this admission batch.

## Verification after the main rebase

On the 2026-11-16 rebase onto merged main `bf05f5a`, focused checklist,
instruction, changelog and deployment-document readers passed **188 tests /
one historical-tag skip** in **7.84 seconds**, using Python 3.11.14. All
**140 local references / 55 Markdown anchors** resolve, all **25 Contents
targets** follow document order, one existing changelog fragment is valid,
and whitespace checks pass.

Before publication, the conditional preview on `a37245a` passed **188 focused
readers / one historical-tag skip** in **8.26 seconds**, using Python 3.11.14,
with **140 local references / 55 Markdown anchors**. The earlier `25caf0e`
preview passed 133 readers/one historical skip and 138 local references/53 anchors.

A direct comparison verifies all 95 IDs and #173 Stage cells, the other 94
criterion/status/evidence prefixes byte-for-byte against #174, the authorized S4
exception and an unchanged P3 prefix. The authoritative #173 Go/no-go section
is preserved verbatim; the old blanket gate is not restored from #174. Both
changelog bullets remain; #174's entry is byte-identical to merged main `bf05f5a`,
and both use contiguous two-space
continuations. The full runtime gate is not repeated: only documents and the
inventory-counter tests differ from merged #174. Runtime verification remains
in #174's implementation record; this admission batch adds no runtime or hosted
proof. No deployment or participant observation was performed.

## Historical verification of published #173

On the review follow-up `20ebe9f`, rebased onto main `def0f54` (#177),
Python 3.11.14 and Node 20.19.0:

- `ENFOLDED_E2E=1 ./scripts/check.sh` exited 0: Ruff clean; **4,008 Python
  passed, 1 skipped** (763.30 s); **189 Vitest** passed in 19 files; bundle
  byte-fresh; installed `enfolded-0.1.2rc1` wheel verified at schema **32**;
  **183 Playwright** passed (6.0 min), covering both clients.
- Five focused checklist/instruction tests passed on the rebuild. After the
  version-4 update, the checklist, deployment-document, changelog and instruction
  readers passed again: **133 passed, 1 skipped**. The inventory recount is
  **13 Done, 43 Partial, 37 Not started, 2 Unknown**; its stage totals are
  **40 admission evidence, 22 study measurement, 33 later improvement**.
- **136 local references / 53 Markdown anchors**, changelog format and whitespace
  checks passed after restoring the Contents links and the follow-up formatting.
  The diff contains no client, server, renderer, capture-tool, working-rule,
  migration or installed-wheel-check changes.

Earlier results from the client-retirement branch do not validate this rebuilt
scope and are superseded. No hosted deployment or participant observation was
performed. After the owner supplied version 4, the documentation was updated with
the exact cohort requirements and the affected document readers and links were
checked again. This branch does not claim cohort admission is cleared.
