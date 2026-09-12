---
name: irreversibility-check
description: Assess the actual Enfolded diff for irreversible changes when preparing a CHANGELOG entry, PR, or merge decision.
---

# Irreversibility check

Assess the diff when documenting a change batch or preparing its PR/merge.
Record the result even for a draft whose verification is incomplete; the canonical
checks still must pass before proposing merge. Human questions apply only to a
tripped one-way door whose decision has not already been ratified.

## Procedure

1. Identify the actual comparison scope. For a PR, use its current head and
   actual base (refresh the relevant remote ref when needed); a stale local
   `main` can falsely trip or hide a door. For an uncommitted local batch,
   inspect its staged and unstaged changes plus new files. Read the relevant
   hunks below and exclude unrelated pre-existing work. Do not create or fetch
   a PR merely to assess a local documentation edit.

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
   - **World-meta pin touched?** `world_meta` rows are write-once
     first-selection records (ADR-008: the wrap hinge) — the stored value
     IS the fact from then on. Any new `persistence.pin_world_meta` call
     site, any change to a pinning rule (e.g. the hinge selector in
     `multiverse/wrap.py`) that runs before first production pin, or —
     never acceptable without an ADR — any code path that would rewrite a
     pinned row. Selector edits after a world is pinned cannot move it
     (`TestSelectorEditImmunity`), so the danger window is pre-pin tuning
     and new pin keys.
   - **Era display banks touched?** The two banks in
     `multiverse/chronicle.py` are read at render time and stay frozen
     (exact strings pinned) until eras are materialized (ADR-006).

3. Write the check in the house format used throughout `docs/CHANGELOG.md`
   — 2–3 lines, starting `**Irreversibility check:**`. For most PRs:
   `none — no migration, no golden re-pin, no new world_mutations write
   path; <what the diff actually is>`. Never write "none" without the
   "here's why" clause; the clause is the evidence you actually looked.

4. **If a door trips**, record existing ratification and resolve only questions
   not already answered by the owner's instructions or reviewed evidence. Before
   the dependent change or merge, ask the human the unresolved questions:
   - re-pin → which pins change and why the change is safe pre/post launch;
   - migration / write path → what the new row or table is and how the
     continuity policy holds;
   - launch-relevant → which `fly-deployment.md` §8 scenario covers it.
   Record material clarifications in the batch's CHANGELOG entry.

Use the same result in the batch's CHANGELOG entry and the PR body when a PR exists.

## Review and merge authorization

Apply the authorization boundaries in `CLAUDE.md` → "Verification and completion".
This assessment supplies evidence for review, not permission for a subsequent action.

## Completion

Done when the actual diff scope and evidence support the check, and each tripped door
names its ratification or the specific pending decision. Put the result in the CHANGELOG
and PR body when one exists. Reassess when the diff changes.
