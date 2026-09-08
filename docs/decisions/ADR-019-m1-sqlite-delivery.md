# ADR-019: Atomic SQLite Delivery for M1

**Status:** Proposed for development-team review, 2026-09-08. This is the
implementation choice in the M1 draft PR; neither this record nor the planning
merge ratifies ADR-013's broader situation/action contracts.

## Context

Both delayed queues committed `DELETE … RETURNING` before applying work.
The September 7 assessment reproduced application loss; the M1 regressions
also terminate real processes. An origin, its initial work, a hop's effect,
and its continuation previously crossed separate commit boundaries.
All authoritative consequences here are bounded local SQLite operations.

## Decision

Use the SQLite writer lock as the claim. `due_work` returns candidate IDs;
`deliver_work` takes `BEGIN IMMEDIATE`, rechecks status/due/retry time, then
commits the effect, actual historical delta, derived pressure, puzzle rearm,
required continuation rows, and completion together. Each item owns a separate
transaction. Process death before commit leaves it pending; a duplicate
candidate after commit sees completed state and never applies again. There is
no committed in-progress state, lease duration, or lease-expiration race.

Origin acceptance likewise commits its existing chronicle row, immediate
material change (if any), pressure, initial causal ring, and maturation patch
(if any) together. HTTP, CLI, and cast producers share this boundary. HTTP
puzzle sessions rehydrate under the SQLite lock and invalidate on rollback;
entangled solves and a newly completed constellation join that solve's commit.
Room locks precede the database lock and are reentrant for session helpers.

A thread-local transaction scope lets the explicitly participating persistence
helpers borrow one connection. Nested helpers cannot commit independently;
a nested exception dooms the outer transaction even if caught. World birth,
pinning, migration, backup, and restore keep their independent connection
lifecycles. Workers ensure a world is born before entering the effect transaction.
No network, external model call, room broadcast, or transport acknowledgment
belongs inside the transaction. Workers catch post-commit notification failures;
reload/read APIs recover the authoritative outcome without replaying it.

Migration **0018** adds only columns and indexes to the two existing queues:

- Existing table plus integer ID is the durable work identity. Completed rows
  are retained as the duplicate-delivery fence and inspection record.
- `status` is `pending` or `completed`. `outcome` distinguishes `applied`,
  `tunneled`, `law_dropped`, `below_threshold`, `missing_node`, and (for an
  empty maturation) `empty_patch`. Completed does not necessarily mean a
  material effect. Unknown/malformed work stays pending with an error.
- `attempts`, `last_error`, and `retry_at` record application exceptions.
  Retry waits are 1, 2, 4, … seconds, capped at 300, with no discard limit.
  Other eligible items continue. A killed attempt may leave no diagnostic
  increment, but its input remains. `retry_work` clears backoff on pending
  work after operator inspection; it never resets completed work.
- New work links to its existing origin through `source_event_id` and causal
  successors through `parent_id`. Old rows retain null links; do not infer
  ambiguous historical provenance. New arrival data adds a queue/ID `delivery`
  reference to its existing event kind. No old history is rewritten.
- `semantics_version=1` explicitly means the existing rules: pre-law hops
  without `_hop` arrive at their stored strength; `_hop` rows use current
  per-hop law physics; maturation stores and lands the accepted **absolute
  patch**. Existing payloads, due times, IDs, actors, and meaning are preserved.
  Distinct accepted acts remain distinct even if their patches are identical.
  Unsupported versions remain pending, never run through the v1 interpreter.

The v1 version labels this release's interpretation; it is not a new situation
engine or a snapshot of arbitrary future effect code. A future change to laws,
effects, or action semantics must retain a v1 interpreter or explicitly drain
v1 work under this implementation before switching. Do not repurpose v1 for
M2's prospective contribution, coalescing, exclusive-action, or saturation rules.

## Trade-offs accepted

SQLite still serializes all writers. World hydration and local computation
hold the write lock for one bounded item; batching is limited to 64 causal or
32 maturation candidates, with a commit between items. This prioritizes a
provable recovery boundary over throughput. Measure contention before changing it.

Completed rows are retained indefinitely in this change, adding storage.
There is no pruning or bulk history rewrite. Backoff isolates poison items
without a new dead-letter service; operators must inspect persistent failures.
If even error recording fails (for example, a full disk), the input remains
pending and the pump logs the error. Recovery then requires repairing storage.

**No mixed-version workers:** pre-M1 binaries ignore the new status column and
would consume completed rows. Stop every writer before upgrade, take a backup,
start only M1-compatible binaries, and verify pending/outcome counts. For binary
rollback, stop writers and restore the pre-upgrade whole-database backup with
the matching old binary. New history since that backup would be lost; prefer
forward repair if play has continued. A v18 backup restores safely to this version.
No deployment or production restore is authorized by this draft PR.

The guarantee is one committed database application per durable queue ID in
these tests, not exactly-once HTTP or WebSocket transport. There are no request
idempotency keys: a retried `/act` request is another legacy action. Work already
lost by an old delete-on-claim worker cannot be reconstructed from this migration.
Missing-node terminal outcomes are inspectable, not fabricated material effects.

## Revisit when…

- Measured writer contention makes per-item transactions too slow.
- Work requires external I/O during application: add recoverable leases and
  an idempotent/outbox boundary for that seam, rather than holding this lock.
- Retained completion records create a measured storage problem: review a
  retention design that preserves deduplication, provenance, and backup safety.
- M2 changes action meaning: version new operations while keeping accepted v1
  patches and causal rules resolvable.

## Rejected alternatives

- Delete-on-claim: a claim is not a successful effect.
- Committing an effect before a continuation or completion: retries lose the
  continuation or duplicate pressure, material changes, and historical deltas.
- Timed leases now: unnecessary expiry/fencing complexity for local work that
  can commit atomically in the same database.
- Deduplicating by node/verb/patch: collapses distinct accepted legacy actions
  and silently decides M2's product policies.
- A broker, new situation engine, new event kinds, or world regeneration.
