# Ideas promotion review corrections — 2026-09-14

Scope: the 12 inline comments on PR [#103](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/103),
checked against `0db99bf`. The owner authorized necessary corrections and documented
reasons for differing approaches. Shared handler/attribution corrections belong to
PR #102 (`0e083a1`); #103 inherits them and remains the separate promotion increment.
No merge, deployment or live test issue is part of this batch.

## Findings and disposition

| Finding | Disposition and evidence |
| --- | --- |
| URL parsing inside the error handler throws again | Fixed in #102. GET/POST share `_fail_dispatch`; malformed targets receive private JSON 400s. Access-log cleanup also guards parsing and uses a constant route. Four raw HTTP cases cover both methods without logging a supplied secret. |
| Duplicate GET/POST failure blocks | Fixed with that shared helper. Additional POST fault injection preserves the existing private diagnostics contract. |
| Settled publication reported as uncertain at the claim | Re-read terminal states inside the claim transaction: return the retained published link, report cancellation explicitly, and reserve uncertainty for an in-flight request. Reconciliation also refreshes local state after the remote read. Deterministic interleavings exercise both boundaries. |
| Definitive rejection races with reconciliation or withdrawal | Settle either `publishing` or `uncertain` after a definitive rejection. An intact brief returns to `prepared`; an erased brief becomes `cancelled`. A concurrently verified published link wins. Local fake-service tests cover corrected retry, withdrawal with/without concurrent reconciliation, and a concurrent verified manual link. |
| `@` text corrupted by escape ordering | Public fields now use literal fenced text blocks; their fence is longer than every backtick run in the field. Exact rendered text is preserved. |
| Bare URLs remain active (two comments) | Fixed by the same rendering boundary, verified with GitHub's GFM renderer with repository context. The renderer-only punctuation-escaping fixture still produced three active links: a user mention, an email link and an issue reference (email text is separately rejected by brief validation). The final 11-line fixture renders only `pre`/`code` elements and preserves every character. |
| Repository change while prepared is refused | Retain the fixed target and correct the ambiguous guide and misleading error. A prepared preview can already have been published manually in its original repository. A regression verifies that a refused target change preserves the full intent and that reconciliation finds the original manual issue without creating another. See the trade-off below. |
| Author-name lookup duplicated | #102 introduces one deterministic batched lookup; board list/detail and public credit reuse it. A credential-replacement regression confirms consistent registered attribution, and page query counts remain bounded. |
| Missing brief file falsely claims stored intent | File read errors give a safe local-file message, without the path or a persistence claim. Generic preparation/preview errors also avoid claiming a retained publication. Missing files, directories, permission errors and preparation failures are covered. |
| Repository default duplicated | The CLI resolves the promotion module's default only when executing the command. Parser registration remains independent of server imports. Both implicit and explicit target tests pass. |
| Withdrawal imports the server for SQL | Already fixed before this review batch: withdrawal performs its SQL in persistence within the same transaction. The latest code retains that boundary. |

## Different approaches and retained limitations

**Keep parser registration independent of the server.** Importing a single constant
from a Python module still executes that module and its package imports. The
suggestion to import the server constant while building the parser would restore
the dependency problem fixed in #102. Resolve the default after the existing lazy
import instead; the fresh-process import guard remains required.

**Do not silently retarget or clear an intent.** `prepared` means no automatic
request is currently claimed, not that no public issue exists: offline previews
can be published manually. Replacing the repository, or cancelling and discarding
the intent to start afresh, could stop the reconciliation token from finding the
first issue. This batch does not add either shortcut. The guide now states the
first-preparation boundary and advises leaving a wrong-target intent unpublished,
without withdrawing the player's idea or deleting its fence. Safe target correction
would need retained prior repositories and explicit reconciliation across them;
that remains outside this version. Same-repository amendments continue to preserve
the token and invalidate the previous review hash.

**Use literal blocks rather than weaker escape promises.** GitHub performs mention
and issue enrichment beyond ordinary Markdown parsing. Entity/backslash escaping
was insufficient in the live rendering check. Literal blocks preserve exact text
and disable that enrichment, at the cost of monospace presentation. Maintainers
still review whether the public content itself is appropriate; inert formatting
does not make private content public-safe or grant tool permissions.

## Verification

The focused corrected suite passed **87 cases in 51.48 seconds**, including **22 new
promotion regressions**. A control run loading the reviewed promotion module against
six new recovery/rendering cases failed **all six** as expected; those cases pass
with the correction. The 11-line synthetic GFM response is retained beside its
exact input/Markdown in `tests/fixtures/idea-public-render.json`, and a regression
binds the current output to that independent rendering evidence. No issue was
created by this rendering request or by the local fake-service tests.

The inherited #102 base separately passed Ruff, **1,176 Python**, **113 Vitest**,
fresh bundle, clean installed-wheel smoke and **57 Playwright** (2.2 minutes).
The complete corrected promotion stack passed Ruff, **1,232 Python in 212.21s**,
**113 Vitest**, byte-fresh bundle, clean installed-wheel smoke and **58 Playwright**
(2.2 minutes), including all 15 Ideas browser cases. Both narrow-screen client links,
the desktop board detail and the mobile recovery layout were reinspected. Nine local
Markdown targets and `git diff --check` pass. These are fixture and local verification
results, not live cohort or deployed-service outcomes.

## Diff-based irreversibility assessment

The correction adds no migration, golden/birth change, world-history writer,
world-meta pin or era-bank change. The complete #103 diff still adds only the
owner-authorized operational migration 0026. No existing migration is altered.
An external issue still requires an explicit operator publish action and the exact
review hash; uncertain publication is never resent on the strength of an empty
read. Withdrawal retains only its approved recovery/link boundary. No world,
puzzle, participant-ownership or agent-memory semantics change in this batch.


## September 19 base integration and follow-up

Integrated board base `16de499` (including main `a133dcd`) into #103, preserving
both histories. The board uses migration 0025; promotion is renumbered to 0026.
The wheel manifest, ADR, operating guide and evaluations use the same sequence.
The merge retains main's recovery tooling and read protections, the base's
active-credential-before-quota behavior, all draft-recovery browser tests, and
promotion's batched links and storage-only withdrawal redaction.

Two populated upgrade regressions start at schema 24 (main) and 25 (board), then
run the integrated migration runner twice, applying only the pending migrations
on the first run and none on the second. The follow-up clears the process-local
initialization cache between runs and asserts both runner results. Both retain
every pre-existing table row, including a private note and the board's idea/support, preserve the two history
indexes, and end at versions 24/25/26 with eight community tables. Offline public
brief preparation succeeds after either upgrade. Fresh-database initialization
is also exercised throughout the full suite.

The eight-publisher test now records each outcome, requires at least one caller
to return `published`, permits only `published` or the documented in-flight
`Uncertain` result, and still requires exactly one remote POST. Unexpected
exceptions propagate and fail the test.

A second rendering fixture comes from a **complete valid `prepare()` output**,
including all body headings, opted-in credit, public board reference and the
reconciliation marker. GitHub's GFM renderer received only that synthetic brief
on 2026-09-19; no issue was created. The captured input/body/HTML are retained in
`tests/fixtures/idea-prepared-render.json`. The regression runs the real prepare
and preview paths, normalizes only the random board reference, and checks the
captured rendering: seven literal text blocks preserve their exact values,
submitted HTML/mentions/links/references remain inert, the rendered body contains
no anchors at all, and the hidden token remains in the Markdown without displaying
in HTML.
The older helper-only rendering fixture remains useful as a separate fence probe.

**Retained conservative reconciliation state.** A concurrent read may change a
healthy in-flight claim from `publishing` to `uncertain` before its response settles.
This can briefly show an operator warning, but does not permit a duplicate POST.
We did not adopt the suggested claim-age heuristic: elapsed timeout cannot prove
whether a process is alive or whether a remote request was accepted, and a fresh
claim may already belong to a crashed process. Both labels must remain fenced.
Successful publication/verified linking clears the warning, and definitive
rejection safely settles to prepared or cancelled. A future UI may distinguish
an in-flight observation without weakening the durable recovery state.

The integrated canonical gate passed Ruff, **1,273 Python tests in 224.10s**,
**113 Vitest**, byte-fresh production bundle, clean installed-wheel smoke at schema
26, and **60 Playwright tests in 2.2 minutes**, including all 17 Ideas cases. Both
clients on desktop/mobile, the separate recovery layouts and the promoted issue
view were visually inspected. Local documentation links and diff whitespace pass. The
base independently passed Ruff, 1,214 Python, 113 Vitest, fresh bundle, wheel smoke
and 59 Playwright tests before integration.

**Irreversibility check:** relative to current #102, the only migration is the
already authorized additive promotion migration, now numbered 0026 to avoid main
and board collisions. Renumbering an unmerged, undeployed migration changes no
production schema. No golden/birth pin, world chronicle write path, world-meta pin,
era bank or existing migration changes. Live publication still requires a reviewed
hash and an explicit operator action; no live test issue, merge or deployment.
