---
name: changelog-entry
description: Write the Enfolded CHANGELOG entry when documenting a completed change batch or preparing its PR.
---

# CHANGELOG entry

`docs/CHANGELOG.md` is the running deviation-and-surprise log the next cold
session navigates by. One entry per change batch, written so a reader who
wasn't there learns what actually happened — quantify surprises, don't just
describe outcomes.

## House format

Add each batch under the first `## [Unreleased]` in `docs/CHANGELOG.md`, newest
first within `### Added` for new capabilities or `### Fixed` for corrections to
existing behavior or guidance. The file also has older bullets above `[Unreleased]`;
leave those historical entries in place, but do not use them as the insertion point.
Keep the release-section scheme. Each batch is one bullet:

1. **Bold headline** — a sentence naming what changed and why it matters,
   followed by a parenthesized list of the load-bearing files touched.
2. **Narrative with measured evidence.** Numbers over adjectives:
   "+1 syllable renames 77/83 nodes", "70.68% of nodes", "~350 ms once per
   seed", "530 KB → 428 KB". If a surprise or deviation occurred during the
   work, it belongs here with its magnitude — that is the log's purpose.
3. **`Verified:` sentence** — the actual check outcomes and measured counts for checks run.
   For code/merge verification, include Ruff, Python, Vitest, bundle freshness,
   installed-wheel smoke, and Playwright if run. For documentation-only work,
   name the document checks; never fill in a passing suite that was not run.
4. **`**Irreversibility check:**` closing line** — produced by the
   `irreversibility-check` skill; "none — <why>" for most batches, or the
   ratified one-way-door statement when a door was consciously walked
   through.

## Rules

- One entry per change batch — never several small bullets for one PR,
  never one bullet spanning two PRs.
- A substantial audit or pre-mortem that drives the batch lands as
  `docs/evaluation/YYYY-MM-DD-<name>.md` in the same PR, and the entry
  points at it.
- Architectural or continuity decisions get an ADR in `docs/decisions/` house style (Context /
  Decision / Trade-offs accepted / Revisit when… / Rejected alternatives),
  preferably written before building.
- Record material clarifications from the irreversibility review in the entry.

## Completion

Done when one entry accurately describes this batch, its measured evidence, verification,
and diff-based irreversibility result. Update the same entry as the batch changes. This
skill does not itself authorize a commit, PR publication, or merge.
