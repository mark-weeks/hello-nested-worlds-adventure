# Puzzle answer withdrawal: staging follow-up

Date: 2026-11-11. Base: `main` at `bd03148`, after PR #169. In a Codex
working session, the owner asked: "Shall we proceed with remaining
implementation in the recommended sequence?" That sequence included
withdrawing puzzle answer disclosure. PR #170 interprets the request as
preparation of ADR-036 D8 batch **1a alone**; the owner's approval of that PR
will confirm its bounded scope, wording and interim behavior. It does not ratify
the larger Proposed temperament design or supply merge/deployment approval.
The review update integrates `main` at `a5c6a19` (#167 and #168), retaining
its roadmap refresh and backup-cadence evidence. Those merges change no
application code.

## Scope and result

`POST /puzzle/attempt` no longer includes `correct_answer`, whether an attempt
is wrong, exhausts the shared pool, succeeds, or finds an already solved
puzzle. The CLI and both browser clients use the same failure line,
"The question keeps its answer.", and ignore the retired answer field.

The shared attempt count, `FAILED` result, solver/contributor credit, hints,
solves and existing `PUZZLE_ATTEMPT` / `PUZZLE_FAILED` writes retain their
current behavior. In particular, this does not make `FAILED` a new permanent
lock or introduce a send-away period. A newcomer encountering a persisted pool
already beyond its limit still receives `FAILED`, without the answer.

**Interim behavior retained for batch 1b:** the server has no per-puzzle cap
on guesses after the pool is exhausted. A later wrong guess still passes
through moderation screening and appends a `PUZZLE_ATTEMPT` and a
`PUZZLE_FAILED` row; a legitimately derived or scripted correct guess can
still solve it. The existing per-IP write rate limit bounds request rate,
not the lifetime number of attempts or rows. Screening can resolve locally;
it does not mean every guess makes a paid model call. These paths already
exist in `bd03148`. This batch removes the direct answer release rather than
changing shared access or the write contract. Failure alone does not re-arm
a puzzle.

Both browser inputs disable immediately after `FAILED`. On reopening, the
map keeps the exhausted pool disabled, while `/app` re-enables its input.
That existing difference is pinned explicitly by the corrected browser
tests. Unified exhaustion/access behavior is a batch-1b dependency, together
with its server-side controls; it is not silently selected in this batch.

This is the separate rollback floor described by
[ADR-036 D8](../decisions/ADR-036-puzzle-temperament.md#d8-batches-in-order).
Batch 1b has not been implemented. Before it is activated, its deployment
procedure must exclude images older than this answer-withdrawal floor.
The intended release order puts 1a in the first production image, before
the first production boot, so every production rollback image already
withholds answers. That ordering and the interim behavior above are part
of the scope put to the owner in PR #170; no production deploy is performed.
Nothing in this change publishes a release, deploys staging, ratifies the
remaining ADR, adopts a puzzle salt, removes ambient agent attempts, or changes
temperament, daily limits, hints or renewal rules.

Removing this direct answer channel does not prevent reconstructing an
unsalted deterministic puzzle from repository code or deriving its answer
from the served clues. ADR-038's salt proposal remains a separate decision.

## Sequence and remaining dependencies

PR #169 completed temporary-world consent, a locally verified `0.1.2rc1`
candidate and authenticated hosted-soak tooling. Its final six GitHub checks
passed before the owner-authorized merge. Isolated staging remains the next
operational step; this environment has no configured Fly credentials.
The operator must also supply the notice and research prerequisites before
newcomers enter. No tag, first deploy or live-model call is authorized by this
implementation record.

Provider, budget and reporting-track decisions belong to the
[decision packet](../roadmap/decision-packet-2026-11.md), particularly sections
1 and 10–12. This puzzle record makes no chat-retention or data-destination
decision; that work needs its own scoped record and implementation.

## Review corrections

The original full run below passed all 181 cases, but its two legacy-response
cases did not intercept keyed requests: the glob `**/puzzle/attempt` missed
the query string. Their coverage claim was overstated. With Playwright
**1.61.1**, adding actual-payload assertions while keeping that glob produced
**2 failures out of 2 legacy cases**. The corrected path predicate matches
keyed requests. Each legacy case now requires two intercepted upstream
responses, exactly one injected failed response, and the synthetic field in
the browser's received JSON before asserting that the UI does not show it.

The review also replaces a duplicated HTTP helper with the shared fixture.
The persistence case now describes what it actually tests: clearing room
state and rehydrating stored multiplayer misses within one running server.
The CLI uses the browsers' authored line. ADR-038 and the roadmap distinguish
their pre-#170 observations from the answer-withdrawal implementation.

## Verification

The complete `ENFOLDED_E2E=1 ./scripts/check.sh` gate exited **0** on
2026-11-11, 16:32:36Z–16:50:20Z, with Python **3.11.14**, Node **20.19.0**
and system Chromium:

- Ruff passed; **3,611 Python passed / 1 skipped** (the optional absent
  historical QA tag).
- **189 Vitest tests passed** in 19 files.
- Production build and committed-bundle freshness passed.
- Installed `enfolded-0.1.2rc1` wheel verified schema **31**.
- **181 Playwright tests passed** in 5.5 minutes, including four new cases
  exercising both clients against a real pinned two-attempt fixture pool.

Before that gate, **279 focused Python tests** and **6 focused browser tests**
passed. The original backend case used two HTTP server instances and cleared
room state, not process death. The original run did not establish legacy
response injection or assert the reopened controls; the review correction
above supersedes those coverage claims. The CLI regression uses a synthetic
answer sentinel.

**Review verification (current code):** the combined
`ENFOLDED_E2E=1 ./scripts/check.sh` gate exited **0** on 2026-11-11,
18:46:02Z–19:03:55Z, after integrating `main` at `a5c6a19`: Ruff passed;
**3,611 Python passed / 1 skipped** (the optional absent historical QA tag);
**189 Vitest passed**; production bundle byte-fresh; installed
`enfolded-0.1.2rc1` wheel verified schema **31**; **181 Playwright passed**
in 5.6 minutes. All four answer-withdrawal cases passed, including actual
legacy-field injection and the explicit reopened-control assertions.

Before that run, **156 focused Python tests** and **6 focused browser tests**
passed. Restoring the old matcher with the stronger assertions failed both
legacy negative controls under Playwright **1.61.1**. The final test uses the
shared HTTP fixture and verifies room-state rehydration, not restart. The
review correction retains every one of the **217 upstream CHANGELOG
headlines** and the backup-cadence roadmap row. No application code or tests
changed during the combined run; later edits fill in verification evidence
and documentation only.

The initial independent read-only review found no blockers. Its check of
**61 relative file links** in the original record, ADR-036 and the original
roadmap index passed. The review update, including ADR-038 and refreshed
main, checks **72 relative file links**, with no missing targets; whitespace
checks pass. Production code and tests stay frozen during each full gate;
verification documentation is filled in afterwards.

Verified browser assets:

- `index-C9c3scMI.js`: SHA-256 `2d2c7a27589cf6763d1b125fa54130be0123113b32352b8a982c1cad8b70bc9f`.
- `index-1EslDMRk.css`: SHA-256 `2d4038cec1d8e8e71eb8e21e1bffe3d9e912ea6b0e2f7f2a4791351aeea98b4b`.

## Irreversibility check

None — no migration, golden re-pin, generator/birth change, new
`world_mutations` write path, world-meta pin or era-bank edit. The production
diff removes a response field and three display consumers. Existing pooled
attempt and history-writing paths are unchanged. ADR-036's larger write-path
and frozen-temperament decisions are outside this batch.
