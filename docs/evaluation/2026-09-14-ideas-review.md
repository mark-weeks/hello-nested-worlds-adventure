# Ideas board review corrections — 2026-09-14

Review scope: PR [#102](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/102),
head `951acd0`, against `62e822a`. The owner authorized corrections and documented
disagreements. PR #103 remains the separate promotion increment and inherits these
corrections. No merge, deployment or live issue publication is part of this work.

## Findings and disposition

| Review finding | Disposition and evidence |
| --- | --- |
| Credential-shaped initial idea ID returns to history/request URLs | Validate the ID once; guard every detail opening. Browser regression observes history updates and non-navigation requests after the initial supplied URL. Invalid input is not retransmitted. |
| Unpaired surrogate accepted by validation; nested JSON escapes decoder | Reject surrogate code points before encoding/storage; decoder recursion becomes a clean 400. Regressions include a 2,201-byte nested body below the 8 KiB cap. |
| Trailing-slash public shell incorrectly requires a credential | Normalize the Ideas prefix before dispatch classification. `/ideas`, `/ideas/`, and `/ideas///` are public shells; data routes still require active credentials. |
| Read routes bypass rate limits | GET list/detail and POST search share the existing read limiter (120/min/IP by default), including cross-method requests. They do not consume the separately approved 300/hour community-write quota. |
| Catch-all errors have no useful diagnostic; outer auth failures may expose stack locals | Add a local `ideas_request_failed` diagnostic containing only an allowlisted route and exception class. No message, frames, query, credential or body is logged. Exclude this logger from Sentry. Move the outer privacy boundary into #102 so it is independently safe. Access logs already reported status codes; the missing signal was a safe failure category. |
| Tab-scoped receipt is lost when the tab closes | Retain only the pending submitted payload in participant-scoped local storage; use a Web Lock when claiming/settling it. Unsubmitted drafts remain tab-scoped. Confirmation replaces the payload with a minimal receipt tombstone. Desktop/mobile tests close the original tab, recover in another, then retry from a stale tab without another POST. |
| Duplicate becomes unmoderatable after its survivor is hidden | Validate the survivor when creating/changing the relationship. Later visibility/decision updates remain possible. Hidden/withdrawn survivors are still unavailable to players. |
| Withdrawal with status flags silently loses the requested status | Reject combined status/duplicate/availability flags before any write. Operators record the decision, then withdraw. Regression checks both the rejection and the resulting two-step decision history. |
| CLI parser imports the HTTP runtime | Move Ideas CLI registration into `persistence.ideas_cli`. A fresh-process import guard rejects any attempted `server` import while registering the CLI. Promotion imports remain lazy in #103. |
| Repeated credential lookups | Reads resolve identity once. Writes authenticate before IP charging and recheck inside their transaction; the existing revocation-race regression stays required. Normalize header whitespace without accepting URL/body credentials. |
| Per-row list queries | Batch the page's rows, names and vote summaries. A 50-result comparison uses 156 SELECT/WITH statements at reviewed head versus 8 after correction, with identical public payloads. The regression compares 1- and 50-item page query counts. These are SQLite statement counts, not network round trips or a latency benchmark. |
| Persistence imports a private HTTP moderation helper | Extract the unchanged local classifier into `content_screen.py`, shared by persistence and HTTP moderation. No paid classifier is introduced; existing moderation behavior tests remain required. |
| Successful reload leaves the previous error announced | Scope messages to their operation. A successful list retry clears its own error while preserving submission/withdrawal acknowledgments and stable links. Browser test covers failure after an already successful load. |

## Disagreements and retained policy

**No moderation hold on withdrawal.** The observed ability to withdraw a hidden
idea is intentional under the owner's accepted retention decision in ADR-026:
withdrawal immediately removes the original live title/description; hidden content
is retained only until explicit withdrawal/redaction. Hiding limits visibility,
not the owner's withdrawal right. Blocking withdrawal would introduce an unapproved
evidence-retention exception. Preserve the decision/ownership/retry fences and
published links, and do not restore the original content. A regression now pins
hidden-owner withdrawal and idempotent retries. Revisit only after an explicit
owner decision changes the policy.

**Reads are not community writes.** The unbounded-read finding is accepted; the
suggestion to move `charge_ip` above search is not. Doing so would spend the agreed
write allowance on browsing and related-title searches and would write a persistent
limiter row for each read. Use the existing read limiter instead. Its buckets are
process-local and shared with other expensive reads; the community write quota
remains durable and shared across processes. Tests pin both boundaries.

**Operational errors remain private.** Do not restore raw exception capture to
address missing diagnostics. The correction emits an allowlisted local signal;
Sentry does not receive the community exception or this logger's event. No new
analytics are introduced.

## Verification

Canonical gate passed: Ruff, **1,169 Python tests**, **113 Vitest tests**, fresh
frontend bundle, installed-wheel smoke, and **57 Playwright tests** (2.2 minutes).
The Python suite includes 24 new review cases and passed in 170.45 seconds.
The 14 Ideas browser cases include
both clients on desktop/mobile, inspected recovery layouts, keyboard retry,
private draft isolation, storage denial and stale-tab recovery. The query comparison
and its corrected constant-query regression passed. After finding stale packaging
artifacts from switching between the stacked branches, the installed-wheel smoke
was repeated with this task’s generated build directory removed; the clean wheel
contains the board increment and the relocated CLI/shared classifier.

## Irreversibility check

The correction diff adds no migration and changes no existing migration, birth
bank/golden pin, chronicle write path, world-meta pin or era bank. The complete
board PR retains the owner-approved additive migration 0024. Withdrawal semantics
stay under the approved immediate-redaction policy. Browser receipt retention is
disclosed before submission and removes the payload after confirmation; users may
still clear browser data, which also removes its local recovery receipt.
