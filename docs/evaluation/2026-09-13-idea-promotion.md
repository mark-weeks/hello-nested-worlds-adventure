# Ideas promotion: privacy and interrupted-publication evidence

This is the second change, based on board/moderation commit `951acd0`.
It implements offline reviewed public brief preparation/preview, explicit issue
publication, token-based reconciliation and verified manual issue linking. All
remote-write tests used a local fake GitHub service. No live GitHub issue, PR,
merge or deployment was created. The integration has not been tested against a
live write-enabled GitHub credential; that remains an operator deployment check.

## Boundaries exercised

Migration 0025 adds two operational tables. Preparation creates a retained intent
before any remote call. It accepts only deliberately authored public fields and
requires explicit review of privacy, rights, scope and acceptance criteria.
Template review defaults false; public credit defaults false and is checked
against the submitter's stored opt-in. Tests place private text in the source,
profile and journal and verify that none is copied into preview. Known participant
IDs, credential aliases, credential-shaped strings, email/device identifiers and
opt-out name attribution are rejected. Plain-text rendering prevents input from
creating HTML, images or active Markdown syntax in the brief.

An exact preview hash binds publication to the reviewed title/body/repository.
Amending a prepared brief preserves its reconciliation token and invalidates
an older preview hash. The HTTP create fixture reads the database at arrival and
observes a committed `publishing` intent. A separate writer acquires the SQLite
lock while that HTTP call is in progress, proving that network I/O does not hold
the shared world database's writer lock. Only title and body are sent: no assignee,
agent-launch command, vote threshold or new scheduling path exists.

The test suite exercises these failure windows:

| Event | Observed recovery |
| --- | --- |
| Eight simultaneous publish calls | Exactly one remote POST; other calls reconcile or report the in-flight claim. |
| Remote acceptance followed by a disconnected response | Local state becomes uncertain; temporarily absent results cause no resend; later token reconciliation links the one existing issue. |
| Remote connection closes before acceptance | One attempted POST remains fenced through repeated publish calls; no inference of non-creation from an empty listing. |
| Worker exits after claim but before POST | A fresh process leaves a durable publishing claim; later publish performs reads only and does not create an issue. |
| Worker exits after remote acceptance but before saving link | Retained claim reconciles to the one issue; no second POST. |
| Remote success followed by local link-write failure | Safe uncertain diagnostic, retained intent, and recovery by token without another POST. |
| Local publish-claim write aborts | No remote POST; intent remains prepared. |
| GitHub definitive 422 rejection | Prepared intent remains eligible for a corrected explicit publish; upstream private error body is not copied. |
| Matching closed issue on page two of 101 records | Found through repository enumeration, without search or creation. |
| Two matching token-bearing issues | Fail closed; operator can explicitly verify the intended existing issue link. |
| Redirect response | No redirect followed; credential is not forwarded to the Location target. |
| Source withdrawn before claim | Brief is scrubbed and cancelled; publication refused. |
| Source withdrawn during an authorized request | Source and local brief are scrubbed immediately; the already-authorized remote result/link can still be retained. |

Issue URLs are derived from the verified repository/issue number, ignoring an
upstream fixture's malicious `html_url`. Manual linking refuses wrong repositories,
query strings, wrong numbers and absent tokens. Completed publication does not
alter the idea's community status or any world, puzzle or agent table.
The API exposes the retained URL without exposing the public brief, token,
operator or private mapping. Browser-only attempts to prepare/publish/reconcile
are refused. The operator credential exists only in the CLI environment.

The Ideas outer request guard now also prevents unexpected authentication/database
failures from forwarding private request frames to exception telemetry. Responses
remain safe, bounded product errors with `no-store`; the focused fault injection
contains a private sentinel and verifies that it is neither returned nor captured.

The board base commit includes the final pagination correction and its constant-clock
regression. Its snapshot-bound monotonic revisions survive event pruning; see the
[board evidence](2026-09-13-ideas-board.md). This keeps the two reviewable changes
separated into board operations and explicit public handoff.

## Verification and limits

Canonical gate: **1,179 Python passed in 186.13s; 113 Vitest passed;
52 Chromium passed in 2.3m**, with Ruff, byte-fresh bundle and the enhanced
installed-wheel checks. The combined focused suite passed **69 cases**. After
the final ranking fix, the affected HTTP suite passed **35 cases in 19.63s**,
including monotonic revisions across event pruning. A controlled run of the
constant-clock regression against the earlier ranking code failed as expected:
**53** unique visible results instead of **54**. The corrected code returns all 54.
Nine focused Chromium cases passed, including an intercepted external issue-link
navigation with no credential header or referrer and a visible “Merged — awaiting
release” status. The promoted/merged board screenshot was inspected. The installed
wheel gate now explicitly requires both migrations, the board HTML/JS and promotion
module, and reads the promotion table from the installed artifact.

These are deterministic fixture results, not live-service availability or cohort
outcomes. After an ambiguous pre-send crash, no general API can prove a remote
request was never accepted; the implementation deliberately retains uncertainty
and requires investigation rather than risking a duplicate. Public brief privacy
also requires semantic maintainer review; pattern checks are not a classifier.
A restored backup may predate an intent, so operators must independently reconcile
with GitHub before resuming publication after database restore.

## Diff-based irreversibility assessment

Migration 0025 is additive and authorized by the requested explicit-promotion scope.
Publication is an intentional external action gated by operator command and exact
reviewed artifact hash; this implementation task did not execute a live publication.
Source withdrawal scrubs prepared briefs while retaining the token/link fence.
No golden/birth pins, generator banks/version, world-meta pins, era banks, existing
migrations or world-mutation writers change. Promotion remains operational data
separate from permanent world history. The status remains local and undeployed.


## Integration after the PR #102 review

The promotion branch inherits board correction `fd519a2`. Authentication privacy
and local safe diagnostics now belong to the board base. The CLI's promotion
commands follow the relocated `persistence.ideas_cli` registration, with GitHub
imports deferred until a promotion command runs. Source withdrawal scrubs the
promotion brief directly inside the storage transaction, without importing the
HTTP/GitHub adapter. List/search include published issue links through one batch
query, keeping page query counts constant at nine for both 1 and 50 results.

The combined affected board/review/promotion suite passed **93 tests in 55.77s**.
The final canonical gate passed: **1,203 Python in 195.21s, 113 Vitest,
58 Playwright**, Ruff, byte-fresh bundle and installed-wheel smoke from a clean
build. The browser suite includes all 15 Ideas cases, including the published-link
privacy fixture. Live GitHub writes
remain limited to local fake-service fixtures in tests; no test issue is published.
The only migration in this PR remains additive 0025; no world-history, birth pin,
world-meta or era-bank changes accompany the review integration.
