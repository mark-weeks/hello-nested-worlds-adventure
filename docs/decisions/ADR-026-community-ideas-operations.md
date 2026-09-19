# ADR-026: Private Ideas operations and explicit public handoff

**Status:** Visibility, retention and write limits accepted by Mark Weeks in the
2026-09-13 implementation task. Board and promotion merged on 2026-09-19
(#102 `a3db4d7`, #103 `4e8df96`); not deployed. Identity and
credential replacement reuse ADR-024. GitHub publication is a separate explicit
operator action, never permission to launch an agent.

## Context

ADR-023 adopts community contribution terms. Players need a shared feedback
surface without creating GitHub accounts or putting operational community data
in the world's permanent history. The Ideas design left visibility, retention
and write limits for an owner decision. Migration 0023 was already on main when
this work began, so the board uses additive migration 0025 (renumbered from 0024 when main took that number for history read indexes in #101).

## Decision

- Reuse participant IDs and private credential aliases from migration 0021.
  Active credentials are required for reads and writes even if the game gate
  is open. Authenticate Ideas with a same-origin request header, never a query
  parameter or supplied player name. Recheck authentication inside each write
  transaction. Rotation preserves ownership, receipts and support.
- Only active invited players see ideas, registered submitter names and decision
  explanations. Disclose this before submission. Public visitors see a shell;
  voter identities, operator identities and credential mappings are private.
  Public GitHub attribution defaults off and requires the submitter's opt-in.
- Withdrawal removes player access and logically erases title and description
  from live records immediately. Remove support associations. Keep the minimal
  ownership/request fingerprint fence and decision/link history, so retries
  cannot recreate withdrawn submissions and undertaken work stays explainable.
  This is logical application redaction, not secure erasure of SQLite pages,
  WAL files, backups or separately published GitHub issues. Hidden content is
  retained for operators until explicit withdrawal/redaction. Hiding does not
  suspend the submitter’s withdrawal right; no moderation evidence hold is
  authorized. Community records
  do not inherit the permanent-chronicle retention rule.
- Allow 5 new submissions per participant per rolling 24 hours, 60 support
  changes per participant per hour, and 300 authenticated community write
  attempts per IP per hour. Retries/no-op support requests do not spend member
  quotas. List/detail/search use the existing per-IP read limiter instead of
  consuming this write allowance. Store HMAC-derived IP buckets, not raw IP addresses, for this limiter.
  Short-lived limiter/ranking rows are pruned on subsequent relevant writes;
  an idle database can retain expired rows until its next write.
- Submission request IDs bind normalized content to a participant; changed
  content with the same ID is a conflict. Support is a desired boolean state
  under a transaction and a unique `(idea, participant)` constraint.
- Recent/own pages use a stable creation ceiling and keyset. Most-supported
  pages freeze their ranking at the first page’s database snapshot; monotonic support
  revisions allow reconstruction
  for a 15-minute signed cursor bound to viewer and query. Each request returns
  at most 50 ideas, displays current counts and rechecks current visibility.
- Local moderation blocks the existing unequivocal blocklist without invoking
  a paid classifier. Ambiguous reports remain operator-review work. Operator
  decisions are separate operational rows. Duplicates link to visible survivors;
  votes are never transferred. Implemented and merged are distinct from available;
  available requires an operator's verified release/deployment evidence.
- The separate promotion change (migration 0026) persists the reviewed public brief and
  reconciliation token before any GitHub write. A timed-out publication cannot
  be blindly retried. The committed publish claim is the external-action boundary:
  withdrawal cancels an unclaimed brief, while a request already in flight may
  complete and retain its link after source/brief redaction. Preparation/publication never assigns or launches an agent.

## Trade-offs accepted

The same database simplifies backup/restore but must be treated as private,
including community operations. Credential ownership limits votes per invited
account, not per unique human. Local screening is limited; operators must review
and hide abuse. Stable supported pagination retains bounded-window vote events
privately. Withdrawals cannot retract independent public issues or old backups.

## Revisit when

- Cohort write limits cause repeated legitimate denials: review measured cases
  and adjust the documented limits without adding analytics by default.
- Moderation volume exceeds operator capacity: agree review workflow and cost
  before introducing classifiers or additional roles.
- Community retention creates material storage or privacy requirements: specify
  archival, backup expiry and erasure while retaining retry/promotion fences.

## Rejected alternatives

- New community accounts or matching display names: conflicts with ADR-024.
- Public raw submissions or voter lists: exceeds the approved visibility.
- Automatic feature selection or agent assignment from votes: votes are evidence.
- Treating merges as proof of availability: players need verified playable results.
