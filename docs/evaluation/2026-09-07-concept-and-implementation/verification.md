# Assessment evidence and reproduction

Assessment date: September 7, 2026. Application baseline:
`87a7cf24bba67505c11aaf4c19a2f562db3d4289`.

## Initial assessment

- Python 3.11.15: `python -m pytest tests/ -q` — **908 passed in 80.63s**.
  The initial restricted attempt could not bind localhost sockets; the full
  run with local socket access passed. Pytest fixtures isolate persistence.
- Node 24.2.0: `npm test --prefix frontend` — **95 passed**, nine files.
  This was a supplemental run outside the repository's Node 20 contract.
- `ruff check .` — passed.
- `python scripts/world_quality.py --seed 382` — passed, **4,208 nodes**,
  100% readable and unique names under the census checks.
- `python scripts/puzzle_quality.py --seed 382` — passed, **4,208 puzzles**,
  65.61% world-reading, 33.72% decode, 99.90% unique prompts, 54.06% unique
  answers, largest family 19.94%.
- Walkthrough: fresh local seed-382 database, both browser clients, one
  sampled `AuditVisitor` entry, arrival puzzle inspection, planet seeding,
  and resulting history. External AI/images and heartbeat were disabled;
  the causal pump ran. This does not evaluate live voice, normal ambient
  occupancy, or player retention.

## Portable probes

After repository setup, run from its root:

```bash
.venv/bin/python docs/evaluation/2026-09-07-concept-and-implementation/probes.py
```

The script locates imports relative to its file, so it can also be invoked
by absolute path from a different directory. It creates its own temporary
databases and accepts no existing database path. It invokes existing runtime
writers against those databases, restores the database path and hop-delay
environment on exit, and makes no network or model calls. Run it as a
standalone diagnostic process, not inside a running game server.

[probes.json](probes.json) records baseline observations, not desired
behavior. The script does not assert that known defects must keep occurring.
Compare output to that record when reproducing the assessment; add tests for
the corrected behavior in subsequent implementation PRs.

The cast probe constructs a fully explored memory state. It establishes a
terminal failure condition, not how often or how soon it occurs. Queue probes
inject Python exceptions after claim; process termination, duplicate delivery,
and recovery under concurrent workers remain follow-up validation. The kindle
comparison evaluates two queued absolute outcomes against two sequential verb
applications; the team must decide whether contributions should accumulate
or deliberately coalesce.

## Assessment PR verification

Packaging validation on September 7, 2026 used Python **3.11.15**, Node
**20.19.0**, and locked dependencies installed by `./setup.sh` in an isolated
worktree. No application files differed from the baseline.

- `./scripts/check.sh` — **passed**: Ruff, **908 Python tests in 81.73s**,
  **95 Vitest tests**, production build with byte-fresh committed bundle,
  and installed-wheel smoke for `enfolded-0.1.1rc2-py3-none-any.whl`.
- Browser E2E was skipped locally by the check script's default. The existing
  GitHub CI workflow runs browser smoke tests on the PR; no result is claimed
  here before that workflow completes.
- The portable probe command, invoked by absolute path from `/tmp`, reproduced
  every field of the checked-in baseline JSON.
- An import-and-run isolation check reproduced the same observations with an
  absent sentinel database as the caller's configured path and hop delay 17:
  the sentinel file was never created, and the path and delay were restored
  after execution.
- All **22** Markdown links in the assessment and verification record were
  checked for portable targets: local artifacts resolve within the repository;
  code references use immutable GitHub links to the reviewed baseline.
- `git diff --check` — passed. Scope is five added/modified documentation and
  diagnostic files; no application or built-bundle changes.

## Irreversibility

This change adds documentation and an opt-in diagnostic script only. It
re-pins no golden world, changes no migration, and introduces no application
chronicle writer. Executing the diagnostic calls existing writers only after
redirecting persistence to its own disposable databases. It changes no existing
world, player state, or production history. Proposed evolution mechanisms
remain unratified and require separate design and implementation review.
