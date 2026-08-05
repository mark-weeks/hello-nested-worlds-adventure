---
name: changelog-entry
description: Write the required docs/CHANGELOG.md entry for the current change batch in this repo's house format. Use for every change before merge — one entry per change, quantified evidence, verification counts, and the irreversibility check inline.
---

# CHANGELOG entry

`docs/CHANGELOG.md` is the running deviation-and-surprise log the next cold
session navigates by. One entry per change batch, written so a reader who
wasn't there learns what actually happened — quantify surprises, don't just
describe outcomes.

## House format (match the existing entries exactly)

Entries live under `## [Unreleased]` → `### Added` or `### Fixed`, newest
first. Each entry is ONE bullet with this shape:

1. **Bold headline** — a sentence naming what changed and why it matters,
   followed by a parenthesized list of the load-bearing files touched.
2. **Narrative with measured evidence.** Numbers over adjectives:
   "+1 syllable renames 77/83 nodes", "70.68% of nodes", "~350 ms once per
   seed", "530 KB → 428 KB". If a surprise or deviation occurred during the
   work, it belongs here with its magnitude — that is the log's purpose.
3. **`Verified:` sentence** — the actual check outcomes: Ruff green,
   **N Python passed**, **N Vitest passed**, bundle byte-fresh,
   installed-wheel smoke, Playwright count if E2E ran.
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
- Decisions get an ADR in `docs/decisions/` house style (Context /
  Decision / Trade-offs accepted / Revisit when… / Rejected alternatives),
  preferably written before building.
- If the human's merge-gate quiz caught a missed answer, fold it into the
  entry.
