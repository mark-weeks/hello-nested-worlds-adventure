---
name: irreversibility-check
description: Write the merge-gate irreversibility check for the current diff. Use before proposing any merge or opening a PR in this repo — it scans the diff for one-way doors (golden re-pins, migrations, world_mutations write paths, era-bank edits, GENERATOR_VERSION changes) and produces the 2–3 line check CLAUDE.md requires in every merge request.
---

# Irreversibility check

CLAUDE.md's merge gate: after tests pass, the author (you) answers the
irreversibility questions from the diff and puts the answer in the merge
request. The human is quizzed only when a one-way door actually trips.

## Procedure

1. Get the real diff surface: `git diff main...HEAD --stat`, then read any
   file that touches the areas below.

2. Answer each question **from the diff, with the file that proves it**:

   - **Golden re-pin?** Any change to the pinned digests/canaries in
     `tests/test_continuity_freeze.py`, the content banks or breadth ranges
     in `multiverse/generator.py`, or `GENERATOR_VERSION` in
     `multiverse/store.py`. A bank edit changes what NEW worlds are born as
     (born worlds are immune — `TestBankEditImmunity`); a pin change must be
     conscious. If yes, the `repin-goldens` skill is the procedure.
   - **Migration added or altered?** Anything under
     `persistence/migrations/`. Migrations are additive only — new tables or
     new columns with defaults; never a destructive rewrite of
     `world_mutations`, `agent_memory`, `puzzle_results`, or `world_nodes`.
   - **New `world_mutations` write path or chronicle row?** New call sites
     of `persistence.record_mutation` (or any new INSERT into
     `world_mutations`). The chronicle is append-only with exactly three
     sanctioned maintenance mechanisms (redaction, double-gated pruning,
     disaster restore) — a new write path is a covenant-level change.
   - **Era display banks touched?** The two banks in
     `multiverse/chronicle.py` are read at render time and stay frozen
     (exact strings pinned) until eras are materialized (ADR-006).

3. Write the check in the house format used throughout `docs/CHANGELOG.md`
   — 2–3 lines, starting `**Irreversibility check:**`. For most PRs:
   `none — no migration, no golden re-pin, no new world_mutations write
   path; <what the diff actually is>`. Never write "none" without the
   "here's why" clause; the clause is the evidence you actually looked.

4. **If a door trips**, do not merge on green. Escalate to the human with
   only the 1–2 questions that door raises, hardest first:
   - re-pin → which pins change and why the change is safe pre/post launch;
   - migration / write path → what the new row or table is and how the
     continuity policy holds;
   - launch-relevant → which `fly-deployment.md` §8 scenario covers it.
   Fold any missed answer into that PR's CHANGELOG entry.

The same check text belongs in two places: the PR body (the template has a
section for it) and the batch's CHANGELOG entry.
