# Controlled staging model calls

This batch implements a closed-by-default control boundary, not live activation.
No provider, endpoint, numeric spending limit, token price or ledger-retention
period is selected by the checked-in configuration. The owner's earlier ceiling
proposals remain proposals; they are not forecasts or approved settings.

`NESTED_WORLDS_REQUIRE_MODEL_POLICY=1` requires controlled mode. A declared
temporary test world also requires it (including a misspelled test-world flag,
which fails closed). Fly commits the requirement and both external kill switches.
An explicit `NESTED_WORLDS_MODEL_POLICY` path enables controlled mode locally.
Without any of these, existing local development and fixture behavior remains.

With both `NESTED_WORLDS_DISABLE_AI=1` and
`NESTED_WORLDS_DISABLE_IMAGES=1`, required mode can start without a policy file;
it freezes all routes disabled. Alternatively use
[the all-off file](../../config/model-policy.disabled.json). Once initialized,
unsetting the requirement, changing the file/environment or adding a key cannot
grant permission. Restart to review and apply a new policy. Kill switches can
still deny calls immediately.

Run the offline check in the intended process environment:

```sh
python main.py model-policy --check --policy config/model-policy.disabled.json
```

It parses and checks enabled routes against effective task/provider/model/options
without API calls or a database. It does not prove provider availability, token
bounds, current prices, account settings, retention terms or owner approval.
No credentials belong in the policy. Use the existing separate credential env var.

## Enabled policy shape

The file is strict JSON: duplicate/unknown fields, floating-point numbers where
decimal strings are required, missing prices and non-finite/negative values are
refused. It has `schema_version: 1`, a bounded `policy_id`, `currency: "USD"`,
`reset: "UTC"`, and exactly five `routes`: `node`, `inhabitant`, `intent`,
`moderation`, `images`. A disabled route is exactly `{"enabled": false}`.

Any enabled route requires `limits` with decimal-string `global_daily_usd` and
`participant_daily_usd` (at most six fractional places), and integer
`ledger_retention_days` of at least two. Choose these deliberately. The global
ceiling includes every participant and task in this database, across policy
changes. Per-participant means stable participant identity, not display name or
the current credential. There is no implicit allowance for keyless calls.

Each enabled text route has all of these fields:

| Field | Required declaration |
| --- | --- |
| `enabled` | `true` |
| `adapter` | `"openai_compatible"`, the first controlled transport |
| `endpoint` | Exact effective HTTPS URL ending in `/chat/completions`; no user info, query or fragment |
| `model` | Exact requested model id, explicitly selected by task/shared env; no adapter default |
| `resolved_models` | Nonempty list of reviewed ids the response may report; aliases do not authorize arbitrary drift |
| `max_input_tokens` | Verified maximum possible billable input for that exact model/request protocol |
| `input_bound_kind` | Exactly `"provider_context_maximum"`; smaller prompt estimates are unsupported |
| `input_bound_evidence` | Reference substantiating that maximum; an average prompt estimate is insufficient |
| `max_output_tokens` | Maximum request output limit, including billed reasoning where applicable |
| `timeout_seconds` | Positive decimal string, at most one hour |
| `options` | Exactly `max_tokens_param`, `structured_outputs`, `send_store_false`, `reasoning_effort`, matching adapter env |
| `prices` | Decimal-string USD per million for `input_per_million_usd`, `output_per_million_usd`, `cache_read_per_million_usd`, `cache_write_per_million_usd` |
| `data_use_note` | Reference to the destination/account data-use assessment |
| `approval_reference` | Reference to the owner's scoped approval; a string here does not manufacture that approval |

`max_tokens_param` is `max_tokens` or `max_completion_tokens`.
`structured_outputs` is a boolean and must be true for intention/moderation.
`send_store_false` must be true. `reasoning_effort` is null or one of the adapter's
supported values. Prices must cover every applicable tier and cache/reasoning
category for the reviewed request; use conservative maxima when a category has
multiple possible rates. Unsupported billing features require another audited
adapter contract. Files may disable individual tasks; a disabled moderation task
holds text that needs classification.

The offline check also requires the standard task timeout to fit the route:
the adapter's configured/default timeout for voices and intention, and the
caller's three-second timeout for moderation. Set the adapter timeout explicitly
when using a smaller route bound. Output bounds are refusals, not automatic
truncation settings: the current ordinary requests are node 256, inhabitant 200,
intention 500 and moderation 32 tokens. A policy below a request's bound denies
that call; it does not silently rewrite it.

Only the exact built-in Chat Completions adapter can dispatch in controlled mode.
Anthropic, registered custom providers, wrappers, direct probes, live eval wrappers,
keyless/background calls and image generation refuse. This is limited controlled
adapter coverage, not a claim that either evaluation candidate has passed. Local
offline fixtures still run outside controlled mode. Do not remove the hosted
requirement to work around a refusal.

## Reservations and usage

Admission reserves the **full verified provider context maximum** at the highest input/cache
price plus the requested output bound, rounded up to integer microUSD. A smaller
daily allowance may refuse a typical short prompt because that full reservation
does not fit. Before activation, measure this against the intended cohort limits;
do not replace it with characters divided by four. A tighter reservation needs an
authoritative, enforced input bound and its own verification. This first slice
trusts the reviewed operator declaration of the provider's context maximum just
as it trusts the declared prices; offline validation cannot certify either fact.
An understated context maximum is unsafe and must not be approved or activated.

One atomic SQLite transaction rechecks the live invite (including sanctions),
resolves participant identity, and checks both ceilings. The transaction ends
before the one network attempt. The adapter captures URL, options, encoded body,
key and timeout once; a later env change cannot redirect the approved request.
There are no retries, redirects, environment proxies or alternate-provider fallback.

Consistent reported token counts can reduce the reservation. If cache writes are
not split out, all known input is charged at the highest input/cache rate as a
conservative upper bound. Other missing counts keep the full reservation. Network
errors and process death keep it too, without guessing that the provider charged
nothing. Settlement belongs to the original UTC day even after midnight.
Unexpected resolved models, exceeded token bounds or a priced overrun hold at
least the reservation and persistently stop subsequent controlled calls. Never
automatically refund an abandoned reservation. This batch intentionally supplies
no unlatch command; reconciliation and an audited recovery path must precede
resuming after such an anomaly.
If accounting cannot commit a settlement, that process also stops further calls;
the original full reservation remains durable. A database failure can prevent an
anomaly latch from being persisted. Resolve the storage failure and reconcile
before restarting; a restart is not an incident recovery procedure.

Ledger rows contain opaque participant ids, route and frozen policy metadata,
usage counts and money. They contain no player text, replies, keys, credential
digests or IPs. Each row retains its selected deadline, so changing policy cannot
shorten existing retention. Expired rows are pruned on reservation attempts and
by an independent controlled-server worker every 60 seconds, after their original
spending window has ended, including while the world is idle or dispatch is
closed. The incident stop persists. While the server is stopped, removal and
backup expiry remain operator responsibilities.
Backup retention remains a separate decision; pruning the live ledger cannot
delete its backup copies. Sentry local-variable capture is explicitly off.

This ledger bounds this installation's admitted calls under its declared prices
and provider contract. It does not reconcile unrelated scripts/provider-console
activity, remote billing changes or an older database restore. Disable AI and
images before restore and reconcile the current UTC day's external spend before
re-enabling them. Do not describe the ledger as a provider-account-wide cap or an
estimate of annual player cost.
