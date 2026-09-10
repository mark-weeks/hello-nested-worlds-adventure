# Inspecting and recovering delayed work

M1 retains causal and maturation work in SQLite; M2 adds versioned operations.
`pending` includes backed-off
failures; `completed` means an inspectable terminal outcome, which can be an
applied effect, intentional physics stop/tunnel, missing node, or empty patch.
M2 maturation also records `already_satisfied` and `precondition_changed` as
completed no-ops with a `SCALE_ACT_MATURED` explanation and no material delta.
The canonical pump still drains only its configured world. Other seeds' work
remains durable and paused.

Use these read-only queries on an operator-approved database copy (or a live
read connection). Queue payloads retain player attribution and should remain
operator data, not a new public feed:

```sql
SELECT status, outcome, COUNT(*) FROM causal_queue GROUP BY status, outcome;
SELECT status, outcome, COUNT(*) FROM verb_maturation GROUP BY status, outcome;
SELECT id, world_seed, node_name, attempts, last_error, retry_at
FROM causal_queue WHERE status = 'pending' AND last_error IS NOT NULL;
SELECT id, world_seed, node_name, attempts, last_error, retry_at
FROM verb_maturation WHERE status = 'pending' AND last_error IS NOT NULL;
```

From the configured application environment, `persistence.inspect_work(queue, id)`
returns the full preserved row. After inspecting and repairing a pending failure,
`persistence.retry_work(queue, id)` clears its backoff. Accepted due time remains
in force; the next pump tick rechecks it. Never reset completed status, edit a
historical delta, or delete pending work to make an alert disappear. The last
error is retained after eventual success as diagnostic context. Attempt counts
cover recorded failures and completion, not every process-killed attempt.

Without intervention, failures retry after 1, 2, 4, … seconds, capped at five
minutes, without a discard ceiling. An invalid item does not suppress the rest
of the eligible batch. A storage outage can also prevent error recording; that
failure is logged and the worker still tries other candidates. Attempts/backoff
can remain unchanged, so the item may be eligible again next tick. If the outage
also prevents reading or applying work, repair storage and resume the normal
pump. Its pending row remains the recovery source. Notification failures require a reload/reconnect, not a queue reset.

## Upgrade and rollback

Before any later authorized deployment, stop **all** application writers and
take the runbook backup. Migrations 0018 and 0019 are additive, preserving
existing inputs, IDs, due times, born rows, hinge, and history. For M2 start only
M2-compatible workers. M1 workers refuse v2 operations and can still accept new
v1 patches; pre-M1 workers ignore `status` and can consume completed rows again.
Neither mixed-version configuration is supported. There is no supported
in-place binary downgrade.

Rehearse the [launch runbook §7 restore](fly-deployment.md#7-backups) with pending
work on disposable staging. Check queue counts/input IDs, a representative
origin/continuation chain, material state and Wayback before and after restore;
restart workers so room caches match the restored database. Section 8's
pre-launch restore rehearsal remains a deployment gate.

For rollback to an M1 or pre-M1 binary, stop all writers and restore its matching
pre-upgrade whole-database backup. This abandons history since the backup;
prefer a forward repair after continued play. M2 can restore and upgrade v18
backups and recover mixed v1/v2 work from v19 backups, retaining completed
duplicate-delivery fences. Rehearsals use disposable local databases only;
they do not perform or authorize a production restore or deployment.

## M2 accepted meaning

`semantics_version=1` maturations still land their stored absolute `changed`
patch; never translate them to operations or merge equal patches. V1 causal
pre-law strengths and `_hop` law behavior remain unchanged. V2 maturation uses
the frozen `multiverse/delayed_v2.py` interpreter and `operation` inputs; its
`changed` column is empty, not an effect to apply. A newer effects function must
not reinterpret that accepted operation. Keep the v1 and v2 interpreters until
a separately reviewed retirement/drain plan preserves every accepted promise.

Distinct contribution requests get separate work IDs. Mark-only requests can
join pending v2 work with the same one-time flag; this is deliberate coalescing,
not HTTP request deduplication. The response names the shared work and retains
its due time. Joining creates no additional origin, pressure or participant
credit. See [ADR-020's policy table](../decisions/ADR-020-m2-delayed-actions.md).

When inspecting mixed pending versions, account for legacy patches that may
overwrite later state: preserving that meaning is intentional. Never clear a
completed fence or rewrite an accepted row to make versions look uniform.
Unknown versions/operations remain pending with backoff and diagnostic errors;
repair forward using compatible code. Queue rows can contain private actor
identity. Public clients receive only aggregate pending summaries and their
request's work reference; errors and raw inputs remain operator data. Mixed
versions produce one public node/verb count, not duplicate version-labeled lines;
inspect the durable rows to distinguish their preserved meanings.

For client recovery, `/node?node_name=...&seed=...` is the bounded authoritative
state read; `/world` remains the tree/return read. Neither is a delivery or queue
reset. The existing origin `event_id` in acceptance responses/notices only lets
clients avoid reading twice for the same HTTP response/socket echo. Maturation
is a separate event, and this optimization adds no HTTP request idempotency.
Do not use display-name matching to infer duplicate work or participant identity.

Completed work and error details are retained indefinitely. No pruning is
introduced. Revisit retention and transaction contention using measured storage
and latency rather than silently removing completion fences.


## M4 attention alongside accepted work

Migration 0020 adds `agent_memory.scan_cursor`, `agent_attention` and a partial
history index. It changes neither v1/v2 work nor completed fences. The cursor is
fair-scan progress; `change_id` and `puzzle_epoch` are consumed opportunities,
not player credit or commitments. Never clear these rows to make an inhabitant
look active: that refunds autonomous opportunities without a new world change.
The original pending work remains the recovery record after acceptance.

Before a later authorized upgrade, stop writers, back up the whole database,
and start compatible M4 heartbeat workers together. Mixed heartbeat versions do
not enforce one attention policy. M3 ignores the added metadata but resumes its
known inactivity behavior; no in-place downgrade is authorized by this PR.
Prefer forward repair. If restoring a matched older database/binary, retain the
existing explicit loss-of-intervening-history warning and §8 restore rehearsal.

On a disposable copy, compare memory names, recent context, cursor and attention
markers together with pending inputs and completed fences before/after restore.
The M4 tests include SIGKILL before/after marker commit and fresh-process recovery
of accepted work, plus a pending-work backup/restore. Attention commits in the
same acceptance transaction. A missed notice never refunds it.

Tick summaries separately report recent candidates screened (`priority_screened`,
at most 64), traversal inspections (`inspected`, at most 40), projected ancestor
names, visits, puzzle/persona admission attempts, origin effects, initial hops,
conversation count and sampled SQL VM steps. Budget for up to 104 candidate
checks, not just the 40 traversal inspections. `agent_runs.nodes_visited` and
completion notices count actual visits; `fresh` remains the discovery count.
These corrections apply to future writes only; prior rows/context are not rewritten. A
`projection_limited` summary flags an exhausted history read. `status=work_limit`
means the total SQL cutoff interrupted the run: earlier commits remain durable,
so absent counts are unknown, not zero. Do not replay the whole tick to undo a
notice failure. If these limits recur, inspect a copy and tune the read projection
under review; do not disable the limits or reset history. See
[ADR-022](../decisions/ADR-022-m4-responsive-inhabitants.md) for policy and limits.
