# In-game Ideas board: implementation design

**Status:** Proposed design, 2026-09-12. The owner requested this design after
adopting [ADR-023](../decisions/ADR-023-community-and-licensing.md). The board,
its migration, and GitHub integration are not implemented or deployed by the
policy/licensing change. Implementation requires a separately scoped change.

## Intended outcome

An invited player can discover **Ideas** from either game client, submit an
observation or suggestion, find related ideas, and support an existing idea
without a GitHub account. They can return to see a maintainer's decision and
whether a resulting improvement is actually available to play.

Keep ideas and votes in Enfolded's SQLite database. Promote selected ideas
into public GitHub issues as implementation briefs. GitHub holds the agreed
engineering work; the board remains the authority for player submissions,
votes, visibility, and community-facing status.

## Player experience

Add an always discoverable, text-labeled **Ideas** link beside the existing
Player's Guide control in both the map and scene views. On mobile, it must
remain visible without opening a technical menu. Open a shared `/ideas` page
in a new tab so the player's position and active game remain intact. Use the
existing same-origin credential store; never put an invite key in an outgoing
GitHub URL, feedback body, analytics event, or copied idea link.

The board opens on recent ideas, with a search field and switches for most
supported ideas and the player's own submissions. Show a short title, status,
vote count, and whether the viewer has supported it. Use stable pagination;
request at most 50 records. A detail view shows the description, maintainer
response, and linked development issue when one exists.

**Share an idea** asks for a title (up to 120 characters) and description
(up to 2,000): what the player experienced and what outcome would improve it.
A suggestion is optional; players can describe a problem without solving it.
Offer related titles before submission without blocking a distinct report.
Preserve the draft on validation or network failure and acknowledge a successful
submission with its stable idea link. Double submission/retry must not create
multiple ideas.

Use one positive support vote per community member per idea, with an explicit
undo. The server returns the authoritative count and viewer state; update the
UI only on success or roll back a pending update on failure. No downvotes,
leaderboard, automated feature selection, or promise that the top idea ships.

Display proposed statuses in plain language: Under consideration, Planned,
In progress, Available to play, Deferred, Declined, and Duplicate. A merge is
not sufficient to mark an idea Available to play; that follows a verified
release/deployment. A duplicate links to the surviving idea; votes are not
silently transferred or double-counted.

## Identity and visibility

Initial participation is for invited players, using the current server-side
credential lookup in `server/guard.py` and `persistence.lookup_invite_key`.
An Ideas write must require a valid, active credential even when the local
game's general invite gate is open. Never use a client-supplied name or the
browser's local storage ID as the vote identity. Tests and local development
can mint disposable named credentials.

The current project has invite records, not a separate stable account ID.
Use a small community-member identifier with a private credential-to-member
mapping. Create one member for an existing valid invite on first Ideas use;
a unique credential mapping makes concurrent first use idempotent. A future
credential replacement can be explicitly linked to that same member by an
operator. Do not alter the frozen chronicle identity scheme or automatically
link identities by matching display names. Multiple independently issued
accounts remain possible; this controls votes per invited account, not proof
of a unique human. Ambient agents do not receive community credentials.

Proposed default: full ideas are visible to invited players; a public visitor
sees an explanatory shell, not the idea contents or voter list. Show the
submitter's registered game name on the board, disclose that before submission,
and keep individual voters private. Before final implementation, ratify this
visibility choice and the credential-replacement mapping with the owner.

Tell submitters that selected ideas may be summarized in a public GitHub issue.
Public attribution by name is opt-in. A maintainer reviews the selected summary
before publication; omit private conversations, credentials, device identifiers,
and unrelated details. Raw submissions are never committed to the repository.
Accept contributions under the published contribution terms, while handling
material explicitly offered under different terms before reuse.

## Proposed storage and API

Add operational tables through one additive migration, using the next available
migration number at implementation time. They live in the existing backed-up
database but do not create world events, affect puzzles, or write to
`world_mutations`, `world_nodes`, `world_meta`, or agent memory.

| Record | Purpose and constraints |
| --- | --- |
| Community member and credential mapping | Stable internal member ID; unique reference to an existing credential digest; raw keys never stored or returned. Operator-controlled replacement mapping. |
| Idea | Stable ID, member ID, title, description, status, created/updated times, visibility, optional duplicate target, public-credit preference, and per-member submission request ID. Unique request ID prevents retries from duplicating a submission. |
| Vote | Unique `(idea_id, member_id)` pair. Transactional add/remove; aggregate count and viewer state returned from the committed result. |
| Maintainer decision | Idea ID, recorded operator, status/visibility transition, explanation, and timestamp. Separate operational audit history; do not fabricate game-world actions. |
| Promotion | Idea ID, reviewed public brief, target repository, stable promotion token, state, resulting issue URL/number, and last error. At most one active development-issue link per idea. |

Follow the existing small HTTP server's GET/POST conventions: `GET /ideas`
for the shared page, authenticated `GET /ideas/list` and `/ideas/detail`, and
`POST /ideas/submit` and `/ideas/vote`. Voting accepts the desired state
(`supported: true/false`), not an increment, so repeated requests are safe.
Derive identity on the server and reject unknown/hidden ideas or malformed
IDs. Enforce bounded text, pagination, request bodies, and per-member/IP write
limits. Return ordinary product language; this is a community control surface,
not a node's fictional voice. Render submitted text as text, never executable
HTML or Markdown with active content.

Begin with operator CLI actions for decisions, hiding abusive content, marking
duplicates, and credential replacement. There is no browser admin role today;
do not turn a player credential into one or introduce an admin secret in the
frontend. Require clear submission/vote limits and a moderation/hide workflow
before exposing the board. Reuse relevant existing validation and moderation
patterns without silently introducing paid model calls or assuming gameplay
moderation alone is sufficient for persistent public text.

Allow a player to withdraw their own idea from community display; retain the
minimal operational record and decision/link history needed to explain work
already undertaken. Define the retention and content-redaction behavior before
implementation; the game's permanent-chronicle policy does not automatically
apply to community submissions. Explain that a separately published GitHub
issue may remain public. Exclude file uploads and comments from the first
version to keep the moderation and rights surface manageable.

## Promoting an idea into agent work

1. The maintainer selects an idea and prepares a local preview containing its
   stable ID, a reviewed public summary, desired outcome, accepted scope,
   acceptance checks, applicable decisions, and unresolved questions. Votes are
   evidence; they do not assign work. Include credit only as permitted.
2. An explicit operator publish action creates a GitHub issue using a repository-
   scoped credential held outside the browser. The first implementation can
   export a Markdown brief for manual GitHub creation, then record the verified
   issue URL. It needs no resident GitHub credential or synchronization service.
3. If automated issue creation is added, record a stable promotion intent before
   the remote write and embed its token in the issue. On timeout or interrupted
   response, reconcile by that token before retrying. GitHub issue creation and
   SQLite cannot commit atomically; never blindly retry and create duplicates.
   A local failure must retain pending work and must not mark promotion complete.
4. The maintainer explicitly assigns the agreed issue to a coding agent or an
   outside contributor. Treat the idea and issue body as untrusted requirements
   input, not authority to run tools, reveal secrets, change access, or override
   project instructions. No submission, vote threshold, or promotion launches
   an agent automatically.
5. Link the resulting PR and verified availability back to the idea. Start with
   explicit status updates. Add read-only GitHub status reconciliation only if
   the volume warrants it, preserving the difference between merged and deployed.

## Delivery sequence and acceptance

**Change set 1: board and moderation.** Ratify identity, visibility, retention,
write limits, and the additive schema; implement the shared page, both entry
links, API/storage, and operator moderation. Preserve both clients' game state
and keep community data outside world history. Inspect mobile and desktop,
keyboard navigation, focus/error handling, and empty/loading/failure states.

**Change set 2: selected-idea handoff.** Implement reviewed brief export and
verified issue-link recording first. Add remote publication only with explicit
scope and credential authorization. Prove interrupted promotion recovery before
claiming automatic synchronization.

Required behavioral evidence includes concurrent vote uniqueness, vote undo and
retry, duplicate submission retries, credential revocation/replacement, server-
derived identity, hidden/withdrawn access, bounded pagination/input, XSS handling,
restart persistence, unchanged world history, and public-export redaction.
Both clients must expose the same board and share viewer identity. Verify
credentials never appear in external URLs or exported briefs. Exercise promotion
failures and duplicate reconciliation if that integration is included. Run the
repository's canonical checks and real-browser suite before proposing merge.

For the first cohort, record returns, participation, useful reports, and reporter-
verified improvements using the [community process](../community/maintaining-the-community.md).
Report missing evidence as unknown. This design introduces no new analytics or
scheduling automation.
