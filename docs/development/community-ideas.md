# Operating the Ideas board

This is a local implementation of the [Ideas design](../roadmap/community-ideas.md)
and [ADR-026](../decisions/ADR-026-community-ideas-operations.md), not a deployment
announcement. Both clients open `/ideas` in a new tab and keep the active game.
The board uses the same browser credential store, but sends credentials only in
`X-Beta-Key` headers. Reload Ideas after rotating a credential. Drafts are scoped
to the authenticated participant in session storage, with an in-memory fallback.
Keep the tab open if browser storage is unavailable. Uncertain submissions stay
frozen until the same receipt can be confirmed; definite rejections keep an
editable draft. Related title lookup does not block distinct submissions.

## HTTP contract

All data endpoints require a live personal credential even in ungated local
mode. Responses/errors are `no-store`; public assets contain no submitted data.
Public idea links contain only the random idea ID. Submitted text is rendered
as text, not HTML or active Markdown. No comments, uploads, downvotes or new
analytics are included.

| Endpoint | Contract |
| --- | --- |
| `GET /ideas/list` | `sort=recent/supported/own`, optional `q` (120 characters), `limit=1..50` (default 20), optional signed `cursor`. Returns items, next cursor, viewer ID/name. Cursors expire after 15 minutes and are bound to viewer and query; counts shown are current, ordering is frozen. |
| `POST /ideas/search` | Read-only equivalent of list with filters in the JSON body. Browser search and related-title lookup use this route so drafts and search text never enter URLs. |
| `GET /ideas/detail?id=...` | Description, current support/owner state, public maintainer decisions, duplicate survivor and verified availability. Hidden/withdrawn IDs return the same unavailable response as unknown IDs. |
| `POST /ideas/submit` | `title` (1–120), `description` (1–2,000), `public_credit` (boolean, default false), `request_id` (8–80 URL-safe letters/digits/underscore/hyphen). Same participant/ID/content returns the original receipt, including after withdrawal. Changed content returns 409. Supplied names/owner IDs have no authority. |
| `POST /ideas/vote` | `{id,supported:true/false}`. One support per participant; repeats are no-ops. Returns authoritative count and viewer state from the committed transaction. |
| `POST /ideas/withdraw` | `{id}` owned by the caller. Idempotently removes text/display and support associations; retains operational fences and decision/link history. |

Ideas bodies are limited to 8 KiB. Server text validation rejects obvious
credentials/invite links and control characters. Local blocklist screening
performs no model calls. No automated filter can establish that a report is
safe or that its assertions are true; maintainers still review persistent text.
The public export in the promotion change is a separate reviewed document.

The accepted rolling limits are 5 new ideas/24h/member, 60 support changes/h/member
and 300 authenticated community write attempts/h/IP. Retries/no-op votes still
count against the IP request cap. Rotation and withdrawal do not reset member
quotas. Errors use product language and never echo supplied credentials or bodies.

## Operator moderation

Run commands against the intended database, using the existing operator runtime.
The CLI has no browser admin role. `show`/`list` are **private operator inspection**,
not public export: do not commit or distribute their output. Examples use placeholder
IDs and do not execute publication or change the hosted database during tests.

```sh
python main.py ideas list --visibility visible --limit 50
python main.py ideas list --visibility hidden
python main.py ideas list --visibility withdrawn --before 120
python main.py ideas show IDEA_ID
python main.py ideas decide IDEA_ID --operator 'Maintainer' --status planned --explanation 'The crossing needs a clearer destination cue.'
python main.py ideas decide IDEA_ID --operator 'Maintainer' --visibility hidden --explanation 'Hidden pending review.'
python main.py ideas decide IDEA_ID --operator 'Maintainer' --visibility visible --explanation 'Reviewed and restored.'
python main.py ideas decide IDEA_ID --operator 'Maintainer' --status duplicate --duplicate SURVIVOR_ID --explanation 'Tracked in the surviving idea.'
python main.py ideas decide IDEA_ID --operator 'Maintainer' --visibility withdrawn --explanation 'Original text redacted at the submitter’s request.'
python main.py ideas decide IDEA_ID --operator 'Maintainer' --status implemented --explanation 'Implemented and tested; awaiting review.'
python main.py ideas decide IDEA_ID --operator 'Maintainer' --status merged --explanation 'Merged; not yet released to players.'
python main.py ideas decide IDEA_ID --operator 'Maintainer' --status available --availability 'Release and deployment reference; verification date and result' --explanation 'Verified on the playable release.'
python main.py invite rotate UNIQUE_CREDENTIAL_DIGEST_PREFIX
```

Available statuses: `considering`, `planned`, `in_progress`, `implemented`, `merged`,
`available`, `deferred`, `declined`, `duplicate`. Decisions must not repeat private
conversations or secret-bearing reports. Operator names are never sent to players.
A duplicate cannot point to another duplicate, itself or an invisible idea. Redirect
its existing dependents first if a surviving idea later needs consolidation.
Votes remain with the original submission.

Withdrawal cannot restore content. The original title/description, response,
credit preference and current availability text are cleared from the live record.
Decision history and the minimal retry fence survive. This does not securely erase
SQLite pages/WAL, existing backups or a public GitHub issue. Backups remain private;
follow existing backup retention and restore procedures. No world table is written,
no seed is selected or born by board operations, and no agent receives a report.
