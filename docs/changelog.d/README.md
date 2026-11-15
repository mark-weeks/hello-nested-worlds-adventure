# Changelog fragments

A change batch records its CHANGELOG entry here, as one file, instead of editing
[`docs/CHANGELOG.md`](../CHANGELOG.md). Every pair of pull requests from different
agents that was open at the same time between #111 and #173 touched the same status
documents, and the changelog was in all of them
([record](../evaluation/2026-11-14-parallel-agent-work.md)). A file per branch cannot
collide.

The rule is in [AGENTS.md](../../AGENTS.md) ("Working in parallel" and "Verification
and completion"); the entry format is the
[`changelog-entry` skill](../../.claude/skills/changelog-entry/SKILL.md).

## Writing a fragment

Name the file after the branch, lowercased, with slashes as hyphens: branch
`codex/report-flow` writes `docs/changelog.d/codex-report-flow.md`. It goes directly
in this directory, not in a subdirectory. If your branch has a generic name such as
`patch-1`, put your GitHub login in front.

```text
Section: Added
Status: checklist S3: Not started to Partial (report endpoint merged, UI pending)
Status: roadmap index: add under "Safety, moderation and integrity"

- **Bold headline naming what changed and why it matters** (`server/report_api.py`,
  `tests/test_report.py`). Narrative with measured evidence.
  **Verified:** the checks actually run, with their counts.
  **Irreversibility check:** none — why, from the diff.
```

- `Section` is `Added` for a new capability or `Fixed` for a correction.
- Each `Status:` line is optional and names one change the batch calls for in a status
  document: the roadmap index, the launch checklist, or a standing count in the README
  or runbook. The pull request does not make that change itself.
- The entry is one bullet. Lines after the first are indented two spaces.

`python scripts/fold_changelog.py --check` validates every fragment. The Python gate
runs the same validation in `tests/test_changelog_fragments.py`, so a malformed
fragment fails its own pull request.

## Folding

The status pull request, prepared by Claude Code when the owner asks, runs this in a
checkout with full history (`git fetch --unshallow origin main` in a cloud session):

```bash
python scripts/fold_changelog.py
```

The order of entries comes from git: the time each fragment reached `main`, so a
fragment merged later lands above one merged earlier whatever their file names. The
script stops if it cannot read that history. It moves each fragment under the first
`## [Unreleased]` heading of the changelog, newest first within its section, deletes
the fragment, and prints the `Status:` lines.
The status pull request then applies those lines by hand, updates
`tests/test_beta_checklist_counts.py` when a pinned checklist status changes, restamps
the roadmap index's verification line, and runs `./scripts/check.sh`. It writes no
fragment of its own.

A pull request opened before this rule merged keeps the direct entry it already has.
