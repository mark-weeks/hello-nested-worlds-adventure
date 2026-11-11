# Controlled staging destinations and USD reservations

Prepared against merged main `09c529b` (PR #170), 2026-11-11. This is the next
bounded implementation batch after staging consent and puzzle answer withdrawal.
It does not deploy staging, approve a provider, enable live calls or complete
the reporting/chat-retention batch.

## Decision boundary

The owner asked us to proceed in the recommended sequence and asked for provider
and spending-limit recommendations. The proposed $15/day global ceiling was
questioned as an annual cost estimate. It is **not an approved setting**. The
checked-in example therefore disables every route and chooses no endpoint,
price, amount or retention period. The owner's separate choice of an operator-only
chat log with a retention window does not select a window length and is not
implemented by this accounting ledger.

[ADR-039](../decisions/ADR-039-controlled-model-spend.md) records the bounded
architecture. [The control guide](../development/model-policy.md) describes the
configuration, limits and remaining live gates. S2/E2 remain Partial; L4,
destination approval, numeric limits, retention and live evidence remain open.

## Audit and resulting implementation

| Observed gap on the base | Result |
| --- | --- |
| Call-count budgets do not price concurrent requests or survive credential rotation as a USD ceiling. | Additive migration 0032 (provisional until merge) supplies independent reservation and anomaly-stop tables. One SQLite write transaction rechecks the live invite, resolves stable participant identity and admits against both daily totals across all routes/policies. |
| A provider setting can change after a preliminary check. | The built-in Chat Completions adapter captures exact URL, request bytes, key, options and timeout once, then validates immediately before reserving/sending. No retries, redirects, environment proxies or fallback destination. |
| Direct adapter probes and eval wrappers bypass the ordinary runtime. | Controlled mode refuses those paths, unsupported adapters and keyless calls. Single-use scopes close on exit, including copied contexts. The first controlled slice supports only exact built-in Chat Completions instances. |
| Images have a separate provider and counter. | Controlled image generation answers the authored quiet line before cache/quota/provider access. No image route can be enabled in this schema. |
| Crash/error/missing usage could appear free. | Full input-context plus bounded-output microUSD reservations precede transmission. Missing usage, network failure and abandoned calls keep their reservation; consistent telemetry permits exact or conservative settlement in the original day. |
| Model drift or usage overrun could silently spend again. | An acknowledged anomaly retains at least the reservation and commits a persistent global stop. Settlement storage failure also stops the current process; the original reservation remains, but unavailable storage cannot promise a committed anomaly stop. |
| Retention tied only to calls would stall on an idle/closed world. | Per-row operator-selected deadlines are pruned on reservation attempts and by a controlled-server worker every 60 seconds, independent of heartbeat/traffic and preserved through an all-off restart. Current-day rows and the independent incident stop cannot be pruned. |
| Sentry can include stack locals even with default PII disabled. | Explicitly disable local-variable capture; prepared request state never belongs in the ledger or diagnostic messages. |

The startup check runs before migrations, listener, workers and observability.
Disabled routes need no provider SDK or model configuration. Runtime model lookup
and configured checks also recognize a disabled route before resolving a provider,
so a later key/invalid selector cannot turn all-off staging into a dropped request.
The offline `model-policy --check --policy PATH` command shares the loader and
configuration validator without activating permission, touching the DB or probing
the provider. Fly commits the requirement and both external kill switches.

## Conservative admission is not an annual-cost forecast

`input_bound_kind` must be `provider_context_maximum`; a six-thousand-token prompt
estimate or characters divided by four cannot serve as a hard reservation bound.
The operator must substantiate the exact model's full billable input maximum and
worst applicable prices. Those declarations are trusted external-contract inputs;
an offline parser cannot certify either. No tokenizer estimate is presented as
proof. A small daily allowance can fail to fit the full reserve even when usual
calls are cheap. A tighter input bound needs separate authoritative verification.

The ledger covers this installation under its reviewed contract/prices, not every
charge in a provider account. Other tools, price changes, unexpected remote billing
and restored older balances require reconciliation. Disable external calls before
a restore and reconcile current-day provider spend before enabling them again.
No automatic unlatch/refund tool is supplied. Backup retention and removal while
the process is stopped remain operator responsibilities.

## Verification

Focused composed checks: **268 passed** across policy, final dispatch, activation,
ledger and wheel inventory. Separate affected moderation and legacy adapter checks
passed. The new behaviors use authored transports and loopback HTTP; no provider
host or paid call was used. They cover simultaneous admissions, cold-process
accounting, credential rotation/revocation/sanctions, UTC rollover, abandoned calls,
settlement/insert faults, exact request binding, copied-context attempts, all task
overrides, images, Sentry privacy and all-off authored HTTP 200 behavior.

The final `ENFOLDED_E2E=1 ./scripts/check.sh` gate ran **19:51:06–20:09:10 UTC**
on 2026-11-11 and exited **0** on Python 3.11.14 / Node 20.19.0: Ruff clean,
**3,886 Python passed / 1 optional historical-tag skip**, **189 Vitest passed**,
production bundle byte-fresh, installed `enfolded-0.1.2rc1` wheel verified schema
**32**, and **181 Playwright passed** in 5.4 minutes. This adds **275 backend test
cases** to the merged base. Log: `/tmp/model-controls-final-check.log` (local
session artifact, not a portable repository dependency).
The initial run was interrupted after **1,367 passed / 1 skipped**, when review
found contradictory upstream usage could reduce a reservation. It also exposed
two documentation regressions: E2's checklist status needed matching summary
counts, and the runbook replay needed to exercise the default quiet probe and
the separate live probe. Those checks now pass; the actual runbook commands are
replayed against loopback HTTP (**96 passed / 1 optional historical-tag skip**).

Internal review corrected strict-parser control-character and boolean lookalikes,
safe normalization of malformed usage before persisting an anomaly, Decimal
precision at the microUSD ceiling boundary, invalid selector `SystemExit`
normalization, disabled-route lookup before legacy defaults, and timeout preflight
parity. Missing cache-write splits are accounted at the highest applicable input
rate rather than assuming the absent price/category is free.

Independent final review reproduced prompt 10 / completion 32 / total 10 as an
unsafe refund. The adapter now leaves output unknown when a present completion
count is invalid or exceeds total minus prompt; the real ledger regression keeps
the entire reservation. Extra derived reasoning output remains supported.
**314 affected tests passed** after that correction. The current official
[Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
(read 2026-11-11) defines total as prompt plus completion and the output maximum
as including reasoning; no new remote request field or provider call was added.
The independent reviewer rechecked the corrected counters and durable
`uncertain` reservation and found the P2 resolved, with no remaining material
concern under the documented provider-contract assumptions.
Changed Markdown relative-file links: **57 checked, 0 broken** before this
record's final evidence update; the final added-link check found **13 relative
file links, 0 broken**.

## Continuity and release handling

**Irreversibility check:** one additive migration, `0032_model_spend.sql`
(number provisional until merge), introduces private operational accounting and
the incident stop under the authorized staging-control implementation. No new
`world_mutations` writer, birth/golden re-pin, world-meta pin or era-bank edit.
The tables cannot rewrite fictional history. The PR remains the concrete human
review gate for this schema step; no live database is migrated here. Back up before
deployment and retain a schema-32 fallback image. A schema-31 image is not an
ordinary rollback after applying 0032; a matched older restore is the disaster
procedure and also needs spend reconciliation. Runbook §8's backup/restore and
in-fiction budget-degradation rehearsals apply. No tag or deployment is authorized
by the tests, and this implementation leaves external calls off.
