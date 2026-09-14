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

## Explicit GitHub promotion

The second change adds migration 0025: one durable promotion intent per idea and
an operator audit. No browser credential is an admin token. No submission, support
count, issue publication or status change assigns a coding agent. Remote calls are
limited to GitHub issue reads and one explicit creation attempt at a time.

1. Copy `docs/community/idea-brief.example.json` to a private local working file.
   Author a **separate public implementation brief**. It is not a raw idea export:
   only the listed public fields are accepted. Review privacy, rights/any exceptional
   contribution terms, accepted scope, checks and unresolved questions; then set
   `reviewed: true`. Requesting public name credit additionally requires the
   submitter's stored opt-in. The tool rejects obvious credentials, personal email
   addresses/device UUIDs, private participant aliases and opt-out name attribution;
   these checks do not replace the maintainer's semantic review of private details.
2. Prepare and preview the exact public artifact. Both commands are offline.
   Preparation durably saves the brief and a stable reconciliation token; preview
   prints only public fields, the random idea reference, token and review hash.
   The output can be saved as Markdown for manual creation. Never use `ideas show`
   output as a public brief.
3. Only an explicit `publish` action can create an issue. Supply the hash printed
   by the reviewed preview. Repository-scoped `ENFOLDED_GITHUB_TOKEN` stays in the
   operator environment, not command arguments, browser code, URLs, logs or exports.
   Use a token scoped to the selected repository with Issues read/write permission.
   The transport uses the fixed HTTPS GitHub API, version `2026-03-10`, refuses
   redirects, bounds response sizes and never follows upstream issue URLs.
4. Record a manually created issue with `record-link`; it verifies the repository,
   issue number and exact stable token through GitHub before saving a canonical URL.
   Both automatic and manual publication retain one active issue link per idea.
   Source status remains unchanged until an explicit `ideas decide` command.

```sh
python main.py ideas prepare IDEA_ID --brief /private/path/public-brief.json --operator 'Maintainer'
python main.py ideas preview IDEA_ID
# Optional offline export of the reviewed artifact:
python main.py ideas preview IDEA_ID > /private/path/public-brief.md
# Set ENFOLDED_GITHUB_TOKEN securely in the operator environment before remote actions.
python main.py ideas publish IDEA_ID --reviewed-sha256 EXACT_PREVIEW_HASH --operator 'Maintainer'
python main.py ideas reconcile IDEA_ID --operator 'Maintainer'
python main.py ideas record-link IDEA_ID https://github.com/mark-weeks/hello-nested-worlds-adventure/issues/NUMBER --operator 'Maintainer'
```

`prepare --repository OWNER/REPO` selects an explicit target. A prepared brief can
be amended by preparing the same idea/repository again: its token stays stable,
but its review hash changes and an old preview cannot authorize publication.
After an attempt becomes uncertain or confirmed, the tool refuses amendments or
new target repositories; reconcile the retained intent. Review and amendment of a
public GitHub issue itself is an independent operator action.

The REST contract was checked against the official [GitHub Issues API](https://docs.github.com/en/rest/issues/issues).
No live issues were created to verify this implementation; local fake services
exercise transport and recovery without public test data.

### Publication and recovery boundaries

- `prepared`: no automatic create attempt has been claimed. Before creation the
  tool enumerates **all issue states**, with pagination, looking for the stable
  token; it does not depend on GitHub's search index. A manually created matching
  issue is linked. Multiple matches fail closed for operator resolution.
- `publishing`: the intent and explicit operator action were committed **before**
  the remote POST. SQLite is not held open across the network call. A crash in
  this state is ambiguous, even if it happened before the request left the process.
- `uncertain`: a POST might have succeeded. `publish` now performs read-only
  reconciliation and **never resends**. A temporarily missing result is not proof
  of absence. Reconcile later or verify a matching manual issue link. If the request
  never reached GitHub, this conservative fence may require independent operator
  investigation; there is deliberately no blind reset/resend command.
- `published`: the issue number and canonical URL are retained; repeated actions
  return that link without creating another issue. Publication does not mark the
  feature implemented, merged or available.
- `cancelled`: withdrawing an idea before its publish claim erases its prepared
  brief and prevents publication. Withdrawal **after** the claim immediately hides
  and scrubs the source and stored brief, but cannot retract an already authorized
  request in flight. Its eventual issue link remains recoverable. This is the same
  public-retention boundary as an independently published issue.

Definitive GitHub refusals (such as authorization or validation rejections) leave
a prepared intent eligible for another **explicit** publish action after correction.
Timeouts, incomplete responses, redirects, server failures or local link-commit
failures remain uncertain. Errors retain safe diagnostics rather than upstream
bodies. Search/list failures and enumeration-bound exhaustion never authorize a POST.
A stale database restore can lose recent intents and tokens; follow the existing
restore runbook and reconcile independently with GitHub before new publication.
No local transaction can make a remote issue and an old backup atomic.
