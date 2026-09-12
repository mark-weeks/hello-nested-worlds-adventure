# ADR-024: Participant ownership and active-content continuity

**Status:** Implementation contract for the owner's 2026-09-12 request to
implement the decision review. This branch is reviewable implementation, not
deployment. It adopts the bounded account/content work below; it does not adopt
every candidate in ADR-014 through ADR-018.

## Context

An invite key currently supplies authentication and a frozen historical actor
hash. The proposed journal/profile and Ideas board need the same person to
survive credential replacement. Separately, stored born nodes do not pin puzzle
definitions rebuilt by current code. M1/M2 fence delivery, not HTTP intent.

## Decision

- Add an opaque participant ID with explicit credential aliases. Create it on
  first authenticated use, atomically. An operator may replace a live credential
  by its secret or unique stored digest prefix. Preserve the existing name and
  saved position; invalidate the old credential. Never merge by name, rewrite
  historical actor hashes, or expose those hashes as profile IDs.
- Journals and home bookmarks remain private. Bio/goals/avatar are independently
  editable operational data; publishing a profile is explicit. No private notes
  enter an agent prompt, world chronicle, public profile or research export.
- Pin each actually opened puzzle's definition, version and evidence snapshots
  for its `(world, canonical node, renewal epoch)`. Stored definitions win over
  generator updates. Existing question names/attempts/solves remain unchanged;
  first-use pinning cannot recover an older definition that was never stored.
  Deploy this support before changing content. Pure generation/quality tools
  remain available for evaluating future content.
- Keep answer checking server-side and preserve the current exact normalized
  answer policy. Evidence snapshots are labeled conditions at opening, not
  current state or proof that a particular player witnessed them.
- Add optional authenticated request IDs to scale acts. Commit the receipt and
  acceptance/effects together. Reusing an ID with a changed action is rejected;
  a retry returns the original receipt without rebroadcasting or applying again.
  Requests without IDs keep their existing semantics. New consequential
  situation operations require IDs. No heuristic deduplication by verb/time.
- Keep receipts and old puzzle definitions. No automatic retention policy is
  introduced. New migrations only add operational/content tables.

## Trade-offs accepted

First-use definitions and receipts increase storage. Credential replacement is
operator-controlled; this does not create password login or self-service account
recovery. Existing historical identities remain credential-derived aliases; the
new ID owns new resources. Unpublished profile content and notes can be edited
or deleted without changing world history. Resume stays on the invite record.

## Revisit when…

- Credential replacement demand requires self-service: design recovery proof
  and revocation before exposing it to players.
- Retained definitions/receipts create measured cost: design archival that keeps
  active work solvable, retry fences intact, and restored backups compatible.
- Additional answer policies are needed: add a versioned interpreter rather
  than broadening acceptance for existing instances.

## Rejected alternatives

- New credential means a new person; matching people by mutable display names.
- Separate incompatible identities for journal, community and recognition.
- Rebuilding active content after deployment or changing old answers silently.
- Treating queue IDs as proof of exactly-once HTTP requests.
