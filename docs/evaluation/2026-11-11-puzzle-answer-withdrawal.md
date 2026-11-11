# Puzzle answer withdrawal: staging follow-up

Date: 2026-11-11. Base: `main` at `bd03148`, after PR #169. The owner
requested the remaining implementation in the recommended staging sequence.
That sequence includes withdrawing puzzle answer disclosure. This change
implements only ADR-036 D8 batch **1a**, independently of its larger Proposed
temperament design.

## Scope and result

`POST /puzzle/attempt` no longer includes `correct_answer`, whether an attempt
is wrong, exhausts the shared pool, succeeds, or finds an already solved
puzzle. The CLI no longer prints the answer when the pool fails. Both browser
clients replace their answer-bearing failure line with an authored line and
ignore the retired field if an older response supplies it.

The shared attempt count, `FAILED` result, solver/contributor credit, hints,
solves and existing `PUZZLE_ATTEMPT` / `PUZZLE_FAILED` writes retain their
current behavior. In particular, this does not make `FAILED` a new permanent
lock or introduce a send-away period. A newcomer encountering a persisted pool
already beyond its limit still receives `FAILED`, without the answer.

This is the separate rollback floor described by
[ADR-036 D8](../decisions/ADR-036-puzzle-temperament.md#d8-batches-in-order).
Batch 1b has not been implemented. Before it is activated, its deployment
procedure must exclude images older than this answer-withdrawal floor.
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

Provider destination reviews and monetary controls still need the provider
endpoints and dollar limits held in decision-packet sections 10–11. While
this correction was being verified, the owner requested reasoned provider
and budget recommendations and selected an **operator-only chat log with a
retention window** for the reporting track. The exact live-log window,
backup-retention tail and deletion procedure still need to be defined; the
existing chat history is unchanged by this puzzle batch. Those next-track
choices do not require choosing a puzzle temperament or withholding this
bounded removal of answer disclosure.

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
passed. The backend regression checks wrong, successful, already-solved,
mismatched and invalid requests; a new HTTP server instance with cleared
room cache rehydrates several players' stored misses, keeps counting failed
attempts, and accepts a legitimate later solve. This is a server-instance
restart test, not a fresh-interpreter or process-kill claim. The CLI regression
uses a synthetic answer sentinel. Browser tests cover both absent fields and
older payloads carrying a synthetic legacy field, without altering current
controls after failure or reload.

An independent read-only review found no blockers. All **61 relative file
links** in this record, ADR-036 and the roadmap index resolve; whitespace
checks passed. Production code and tests stayed frozen during the full gate;
only verification documentation was filled in afterwards.

Verified browser assets:

- `index-C9c3scMI.js`: SHA-256 `2d2c7a27589cf6763d1b125fa54130be0123113b32352b8a982c1cad8b70bc9f`.
- `index-1EslDMRk.css`: SHA-256 `2d4038cec1d8e8e71eb8e21e1bffe3d9e912ea6b0e2f7f2a4791351aeea98b4b`.

## Irreversibility check

None — no migration, golden re-pin, generator/birth change, new
`world_mutations` write path, world-meta pin or era-bank edit. The production
diff removes a response field and three display consumers. Existing pooled
attempt and history-writing paths are unchanged. ADR-036's larger write-path
and frozen-temperament decisions are outside this batch.
