# Inspecting and recovering delayed work

M1 retains causal and maturation work in SQLite. `pending` includes backed-off
failures; `completed` means an inspectable terminal outcome, which can be an
applied effect, intentional physics stop/tunnel, missing node, or empty patch.
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
of the eligible batch. A storage outage can also prevent error recording; repair
the storage and restart the normal pump. Its pending row remains the recovery
source. Notification failures require a reload/reconnect, not a queue reset.

## Upgrade and rollback

Before any later authorized deployment, stop **all** application writers and
take the runbook backup. Migration 0018 is additive, preserving existing inputs,
IDs, due times, born rows, hinge, and history. Start only M1-compatible workers.
Do not run an old worker beside them: old code ignores `status` and can consume
completed rows again. There is no supported in-place binary downgrade.

Rehearse the [launch runbook §7 restore](fly-deployment.md#7-backups) with pending
work on disposable staging. Check queue counts/input IDs, a representative
origin/continuation chain, material state and Wayback before and after restore;
restart workers so room caches match the restored database. Section 8's
pre-launch restore rehearsal remains a deployment gate.

For rollback to a pre-M1 binary, stop all writers and restore its matching
pre-upgrade whole-database backup. This abandons history since the backup;
prefer a forward repair after continued play. To recover on M1, restoring a
v18 backup preserves pending inputs and completed duplicate-delivery fences.
The M1 PR rehearses both backup formats only on disposable local databases;
it does not perform or authorize a production restore or deployment.

Completed work and error details are retained indefinitely. No pruning is
introduced. Revisit retention and transaction contention using measured storage
and latency rather than silently removing completion fences.
