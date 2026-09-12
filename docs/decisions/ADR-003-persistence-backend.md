# ADR-003: Persistence backend and a continuity-preserving migration

**Status:** SQLite retained; migration criteria and recovery contract revised
2026-09-12 under the owner's request to implement the decision review. No backend
migration, production measurement, or deployment is claimed.

## Context

The May 2026 estimate treated this as a localized SQL port. The database now
owns born worlds, append-only event/version history, pending causal deliveries,
versioned delayed actions, active content, participant aliases and retry receipts.
SQLite `BEGIN IMMEDIATE` provides the writer fence used for acceptance, eligibility,
material effects and completion. Changing that fence changes correctness.
The old half-day estimate, inferred 30-user capacity and routine rollback write
loss are retired; they were not measured capacity or an acceptable continuity policy.

## Decision

Keep SQLite for the current single-host implementation. Keep connection ownership
in `persistence/`; domain modules call persistence helpers rather than opening
connections. Operational scripts may inspect explicit backup files. New modules
in `persistence/` share `transaction()` and `_connection()` with the existing API.

Start a migration investigation when a representative load test or live evidence
shows sustained lock contention, queue lag, transaction latency, database growth
or backup/restore duration exceeding an explicitly chosen service objective, or
when a real multi-host requirement arises. Record workload, hardware, duration,
percentiles, concurrent participants and ambient-agent activity. A single lock
error prompts diagnosis; neither a fixed user count nor a row-count guess orders
a migration. No new scale claim is made by this batch.

Before choosing a backend, exercise the actual workflows: concurrent puzzle
solves, competing decisions, additive delayed actions, first-use content pinning,
credential rotation, duplicate requests, overlapping workers, process death and
restoration with pending work. Benchmark slow voice calls separately from local
transaction latency. Diagnose query plans and batch boundaries first.

A future backend must preserve:

1. Born node names/properties, write-once metadata, event IDs/order, node versions,
   historical actor aliases, answer definitions and renewal identities.
2. Atomic acceptance plus receipt, and atomic material effects plus completion.
   Recheck work eligibility under the target backend's effective locking model.
3. Exactly one owner for a shared transition, with durable work retained on failure.
4. Compatible readers/interpreters for all pending definition/operation versions.
5. Account ownership and private journal boundaries, including revoked credentials.

The SQL port must inventory JSON expressions, timestamp representation, UPSERT
semantics, generated IDs/sequences, nested transaction ownership and backup APIs
across `persistence/`. Placeholder translation is only one part. Pooling, transaction
isolation, retry policy and process coordination must be designed before cutover.
Do not advertise a database URL switch or Postgres migrations that do not exist.

## Cutover and recovery requirements

Rehearse on a disposable restored copy with the same application version and a
representative pending-work set. Stop **all** writers: HTTP actions, WebSocket
writes, heartbeat, causal pump and other operators. Disabling AI or images alone
does not quiesce the world. Take and verify a fresh complete backup.

Copy and verify every durable table, key, sequence and relevant index. Compare
full canonical row hashes or an equivalently complete reconciliation; sampled
history alone cannot prove continuity. Resume a single designated writer only
after the concurrency, pending-work and restore checks pass.

After new writes are accepted, reverting to the pre-cutover SQLite file would
lose history. It is not ordinary rollback. Prefer a forward repair; otherwise
quiesce again and reconcile all accepted post-cutover data into a tested reverse
migration before switching. Restoring an older backup remains the exceptional
ADR-004 disaster path with explicit data-loss accounting and owner authorization.
Never silently discard new events because the cohort is small. Keep backups under
an explicit retention policy; do not delete the source after an arbitrary week.

## Trade-offs accepted

A single writer remains a scaling constraint. This avoids a speculative backend
project while preserving a concrete correctness contract. Retained content and
receipts increase storage; their archival is a separate reviewed decision.

## Revisit when…

Measured service objectives fail, multi-host operation becomes necessary, or
recovery tests expose an unsupported continuity requirement. Re-estimate after
a backend prototype passes the behavioral contract, with copy/verification and
operational work included.

## Rejected alternatives

- A half-day mechanical switchover with acceptable lost writes on rollback.
- Migrating because the project reaches an invented concurrency threshold.
- Treating Redis, ASGI or disabling paid APIs as a substitute for end-to-end
  writer fencing and recovery.
