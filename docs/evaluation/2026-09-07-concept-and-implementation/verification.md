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
the corrected behavior at the layer changed in subsequent implementation PRs.
A fix outside the layer a probe exercises need not change that probe's output.

The cast probe constructs a fully explored memory state. It establishes a
terminal failure condition, not how often or how soon it occurs. The
known-but-corrupted subtree illustrates the same known-name skip branch, which
does not inspect condition; it is not independent change-detection coverage.

Queue failure probes inject Python exceptions after claim; process termination,
duplicate delivery, and recovery under concurrent workers remain follow-up
validation. The kindle probe directly enqueues two absolute outcomes and
compares their landing with two sequential verb applications. It bypasses the
`/act` handler and its guards. Refusing or coalescing overlapping requests in
that handler could correctly leave this direct probe's density at 438; such a
fix needs endpoint regression coverage. The team must decide whether accepted
contributions should accumulate or deliberately coalesce.

## Assessment PR verification

Packaging validation on September 7, 2026 used Python **3.11.15**, Node
**20.19.0**, and locked dependencies installed by `./setup.sh` in an isolated
worktree. No application files differed from the baseline.

- `./scripts/check.sh` — **passed**: Ruff, **908 Python tests in 81.73s**,
  **95 Vitest tests**, production build with byte-fresh committed bundle,
  and installed-wheel smoke for `enfolded-0.1.1rc2-py3-none-any.whl`.
- Browser E2E was skipped locally by the check script's default. On assessment
  commit `ea45cbd77f3e48cdbc42483b00861061875d5e48`, the PR's
  [CI run 34145070129](https://github.com/mark-weeks/hello-nested-worlds-adventure/actions/runs/34145070129)
  passed all three jobs: Python tests, frontend build, and browser E2E smoke
  (**14 Playwright tests passed in 19.0s**).
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

## Review follow-up verification

The follow-up clarifies probe scope, removes an overwritten constructor
argument, and standardizes the CHANGELOG entry and PR check text. It changes
no application behavior or recorded baseline results.

- The revised diagnostic, invoked by absolute path from `/tmp`, reproduced
  `probes.json` byte-for-byte (`cmp` passed).
- `.venv/bin/ruff check .` — passed.
- All **23** assessment/verification links resolved to local artifacts,
  immutable baseline code locations, or the completed CI run.
- `git diff --check` passed; CHANGELOG placement and labels were checked, and
  its irreversibility text matches the PR body exactly.
- The full packaging and CI results above describe their recorded revision;
  they are not a claim that the follow-up commit has already passed CI.

## Irreversibility

This change adds documentation and an opt-in diagnostic script only. It
re-pins no golden world, changes no migration, and introduces no application
chronicle writer. Executing the diagnostic calls existing writers only after
redirecting persistence to its own disposable databases. It changes no existing
world, player state, or production history. Proposed evolution mechanisms
remain unratified and require separate design and implementation review.
