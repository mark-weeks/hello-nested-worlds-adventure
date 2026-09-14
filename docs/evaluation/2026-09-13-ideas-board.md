# Ideas board: implementation and verification

This local change starts from main `62e822a` (PR #100), which includes the
community policy/licensing and participant ownership work. The original checkout
and its uncommitted guidance changes were preserved in a separate worktree.
This report describes executed fixture/browser evidence, not cohort use or deployment.

## Board and moderation

Migration 0024 adds six operational tables, reusing existing participants.
No migration rewrites world identity, chronicle, puzzles or agent memory.
Owner-approved visibility, withdrawal and rolling limits are in ADR-026.

The focused Python suite contains 35 cases. It sends 24 concurrent submissions
with one receipt ID and observes exactly one idea. Forty concurrent support
requests from two accounts leave two votes; twenty repeated undo requests leave
one vote and three actual support-change events. Authentication is required with
an otherwise open game gate. The revocation race holds a writer transaction
until both HTTP authentication preflights have seen the old credential, then
commits revocation before the operation obtains its lock: no idea/vote is accepted.
Rotation preserves receipt ownership and support. Withdrawal preserves the
receipt fence without returning the original text or recreating the idea.

For each recent/supported/own view, a 55-idea fixture changes votes, inserts a
new idea and hides an unseen idea between pages. Pagination returns exactly
54 unique original visible IDs, including the changed vote target, and excludes
the insertion and hidden record. Wrong-viewer, changed-query and expired cursors
are rejected. A constant-clock regression against the initial ranking code returned
53 visible results instead of 54: a vote timestamp can precede the first page while
its transaction commits afterward. Snapshot-bound monotonic vote revisions fix
that boundary and survive pruning; the corrected 35-case HTTP suite passed in
19.63s. This correction is included in the board commit. Input, malformed body, secret-shaped text, local-only moderation,
member/IP quotas, and explicit availability evidence are exercised through HTTP.
A fresh Python process reads the same persisted idea/vote/decision. Rows in
`world_nodes`, `world_mutations`, `world_meta`, `agent_memory` and `puzzle_results`
are equal before and after board operations.

Eight focused Chromium tests exercise map and scene links at 1440×1000 and
390×844; the shared board at 1280×900 and 390×844; keyboard tab/Enter access;
empty/search/own/supported views; validation; literal script/image payloads;
withdrawal dialog focus/Escape; and lost submission/vote responses. The lost
submission response is simulated **after the real server commits**, then the
page reloads and retries the persisted receipt: exactly one idea remains.
The lost vote response leaves the visible state unchanged; repeating the desired
state recovers one vote. Native new tabs retain the original game's URL/position
and have no opener. Browser searches use JSON request bodies so draft titles
and search text do not become request URLs.

Screenshots were inspected for both clients on desktop/mobile and for board
empty/detail/loading/validation/network-failure states. Inspection found a
long-title mobile overflow (427px document on a 390px viewport); wrapping the
heading fixed it to 390px, and the browser test now checks the populated state.
The first map test sampled position before initial loading completed; it now
waits for a saved position before checking that opening Ideas preserves it.

Canonical gate: **1,145 Python passed in 161.49s; 113 Vitest passed;
51 Chromium passed in 2.2m**. Ruff, byte-fresh production bundle and installed-wheel
verification passed. The affected HTTP suite was repeated after the browser-search
privacy change: **35 passed**; the canonical browser run exercised the new route.
Tests use disposable databases and no paid model calls. No PR, issue, merge or
deployment was published. Prepared PR descriptions are local review artifacts.

## Diff-based irreversibility assessment

| Door | Evidence and result |
| --- | --- |
| Migration | Additive 0024 creates community operational tables only. Authorized in the implementation request; ownership, limits and redaction ratified in this task. Existing migrations are unchanged. |
| Birth/golden pins | No changes to generator banks, generator version, stored node writers or continuity pins. |
| Chronicle writes | No new world mutation call sites or SQL writes. Operational moderator decisions are separate. |
| World metadata | No pinning, update or delete paths added. |
| Era banks | No changes. |
| Withdrawal | Approved irreversible logical removal of community text only; fences/decisions remain. Existing backups and independently published issues are outside this removal. |

GitHub promotion is evaluated separately in the second change. This first
change neither stores a GitHub credential nor performs remote publication.
