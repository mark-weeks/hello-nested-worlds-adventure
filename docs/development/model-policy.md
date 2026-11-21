# Controlled staging model calls

This guide describes a closed-by-default control boundary, not live activation.
No provider, endpoint, numeric spending limit, token price or ledger-retention
period is approved by a checked-in file. The
[watch example](../../config/model-policy.watch.example.json) is the enabled
shape with every owner value left as a placeholder the offline check refuses.
The amounts written inside those placeholders ($15 a day global, $3 a day per
participant, a retention draft of 35 days) are unconfirmed. They are not
settings. The provider console limit of $150 is not a field in the file.

The code supports only the built-in `openai_compatible` Chat Completions path.
ADR-035 stays Proposed until the owner records acceptance for one named
endpoint. A desk check of the two candidate endpoints is in the
[endpoint-check record](../evaluation/2026-11-20-chat-completions-endpoint-check.md).
That record recommends one candidate. It does not sign a data-use note, fill
the example, or accept the ADR. The disposable twin may run the first live
probe once the owner has signed that note, filled the private policy, passed
`model-policy --check`, and set the $150 spend limit on the provider account.
That probe is the live evidence for the acceptance record and does not wait
for it. Production, and any session a participant joins, also wait until the
owner records the acceptance. This guide does not implement chat retention.

`NESTED_WORLDS_REQUIRE_MODEL_POLICY=1` requires controlled mode. A declared
temporary test world also requires it (including a misspelled test-world flag,
which fails closed). Every app using the committed Fly configuration, production
included, gets the requirement and both external kill switches set to `1`.
An explicit `NESTED_WORLDS_MODEL_POLICY` path enables controlled mode locally.
Without any of these, existing local development and fixture behavior remains.

With both `NESTED_WORLDS_DISABLE_AI=1` and
`NESTED_WORLDS_DISABLE_IMAGES=1`, required mode can start without a policy file;
it freezes all routes disabled. Alternatively use
[the all-off file](../../config/model-policy.disabled.json). Once initialized,
unsetting the requirement, changing the file/environment or adding a key cannot
grant permission. Restart to review and apply a new policy. Kill switches can
still deny calls immediately.

`NESTED_WORLDS_DISABLE_AI` remains the voice/intention switch; it does not disable
moderation. In controlled mode the frozen policy also closes every unapproved
route, so a classifier cannot send merely because a key appeared. Images are
unsupported in this controlled slice and return the authored quiet line with
`images: false` before cache, quota or provider access.

Run the offline check in the intended process environment:

```sh
python main.py model-policy --check --policy config/model-policy.disabled.json
```

It parses and checks enabled routes against effective task/provider/model/options
without API calls or a database. It does not prove provider availability, token
bounds, current prices, account settings, retention terms or owner approval.
No credentials belong in the policy. Use the existing separate credential env var.

The all-off file above is a valid quiet policy. The watch example is not:

```sh
python main.py model-policy --check --policy config/model-policy.watch.example.json
```

That command exits 1 until every `<OWNER: ...>` value is replaced. The message
is the generic invalid-configuration line; it does not echo the file. A passing
check prints, per enabled route, the full-context reservation in microUSD and
at least how many such reservations fit under the participant ceiling and under
the global ceiling. Dispatch can admit more when the call's output bound is
shorter than the route maximum. A remainder smaller than one reservation does not count. The
owner confirms the dollar amounts against that report before the file is
approved. The report names tasks only. It does not print endpoints, model ids,
prices or approval text.

The $150 provider-account limit is a separate owner step, set on the provider
console before any paid probe or rubric run. The strict parse refuses an
unknown key, so the file has nowhere to put it and the server does not enforce
it. If the account offers only an alert, stop and record a replacement decision
before any paid call.

`python main.py models` and `python main.py voice-health` report controlled policy
state when controlled mode is required or active, rather than presenting the
legacy default provider as ready. Their `--probe` option is refused in controlled
mode: it is a direct, keyless adapter call with no participant reservation. Use
ordinary authenticated gameplay endpoints only after all live gates pass. The
[Fly runbook](../infrastructure/fly-deployment.md#approved-live-controlled-text)
describes the explicit `NESTED_WORLDS_DISABLE_AI=0` override and verification;
unsetting that secret restores the committed `1`, not live voice.

These commands freeze their own process's policy and environment; they do not
query a running server's in-memory snapshot. If a file or environment changed,
match the command result to the selected deployment and server restart evidence.
The output includes all five route states, ledger availability, durable stop,
unresolved reservations and process fault. Intentionally disabled routes are not
an unconfigured-provider failure. A stopped or invalid control state exits
nonzero, and `voice-health` also reports recorded control-stop failures.

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
Retention also needs a storage estimate for the shared SQLite volume and its
backups; a valid long duration is not evidence that the volume can hold it.

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

Enabled routes require positive input and output prices; cache prices may be
zero when that is the reviewed rate. Policy validation rejects a zero-priced
admission rather than allowing a typo to bypass the dollar ceiling.

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

The offline check's `reservations` rows report that full-context figure at each
route's maximum output, and how many whole reservations fit under each ceiling.
That count is a floor. Dispatch reserves the per-call output bound, which is
no larger, so a shorter call can be admitted more times than the report shows.
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
Controlled dispatch assumes one server process per SQLite database. Before its
first new call after startup, it checks unfinished prior reservations and, if
any remain, records a durable reconciliation stop and abandoned markers. It
does not infer those calls were free or resume merely because the process restarted.

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

Ledger rows contain opaque participant ids, route metadata, usage counts and
money, and reference shared frozen policy snapshots by digest. They contain no
player text, replies, keys, credential digests or IPs. Each row retains its
selected deadline, so changing policy cannot shorten existing retention.
Terminal rows expire normally after their original spending window has ended.
Unresolved reserved rows remain protected past nominal retention until startup
reconciliation or `mark_settlement_fault` records a durable stop and an abandoned
marker. Housekeeping must not delete an in-flight call or crash evidence, so
`retain_until` is not a promise that every pending row physically disappears.
Shared policy snapshots are collected when their last reservation expires.
Pruning runs on reservation attempts and through an independent controlled-server
worker every 60 seconds; the idle worker first reads without taking a writer
lock and writes only when cleanup is needed. The incident stop persists. While
the server is stopped, removal and backup expiry remain operator responsibilities.
Whole-database backups retain ledger rows after live expiry. Backup retention is
a separate decision, and the newest validated backup is protected from the
ordinary prune even after that retention period. If no newer valid backup
replaces it, the exception can last indefinitely; local and downloaded copies
also require deletion. There is no finite erasure guarantee for all copies from
`retain_until` alone. Sentry local-variable capture is explicitly off.

This ledger bounds this installation's admitted calls under its declared prices
and provider contract. It does not reconcile unrelated scripts/provider-console
activity, remote billing changes or an older database restore. Disable AI and
images before restore and reconcile the current UTC day's external spend before
re-enabling them. Do not describe the ledger as a provider-account-wide cap or an
estimate of annual player cost.

## Watch call caps

These are deploy secrets, not policy fields. Each value below is an unconfirmed
placeholder. The owner sets the integer. A neutral name and its legacy name are
set to that same integer in one `fly secrets set`, which restarts once
([runbook](../infrastructure/fly-deployment.md), "Adjust a runtime cap"). A
leftover lower legacy value is what a request enforces.

| Secret | Placeholder |
| --- | --- |
| `NESTED_WORLDS_VOICE_DAILY_CALLS` and `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` | `<OWNER: integer, unconfirmed draft 1000>` |
| `NESTED_WORLDS_VOICE_DAILY_CALLS_PER_USER` and `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` | `<OWNER: integer, unconfirmed draft 150>` |
| `NESTED_WORLDS_MODERATION_DAILY_CALLS` | `<OWNER: integer, unconfirmed draft 2000>` |
| `NESTED_WORLDS_MODERATION_DAILY_CALLS_PER_USER` | `<OWNER: integer, unconfirmed draft 120>` |
| `NESTED_WORLDS_MODEL_ACTIONS_PER_USER` | `<OWNER: integer, unconfirmed draft 200>` |

`server/guard.py` is where those names are read. Moderation and model-actions
have no legacy alias. One further legacy pair exists and stays unset for this
watch, because images stay off and no image provider key is set:
`NESTED_WORLDS_IMAGE_DAILY_CALLS` with `NESTED_WORLDS_FAL_DAILY_CALLS`, and
`NESTED_WORLDS_IMAGE_DAILY_CALLS_PER_USER` with
`NESTED_WORLDS_FAL_DAILY_CALLS_PER_USER`.
`NESTED_WORLDS_MODERATION_ACTIONS_PER_USER` is a separate cap, not a legacy
alias of the names above, and no integer is adopted for it. Leaving it unset
does not remove the cap: `server/guard.py` then applies its default of 600
per user per day.

## Single-grader live rubric run

This is the operator brief for one live rubric run. It was not run to write
this page. Do not point it at the twin.

Controlled mode refuses live eval wrappers. The run is therefore a separate
process on an operator workstation: no `NESTED_WORLDS_MODEL_POLICY`, and no
copy of the twin's database. Use the same endpoint and the same pinned model
ids the owner confirmed in the policy file. The policy ledger does not count
this spend. Reconcile it against the $150 provider console limit, which is
itself an owner step and not a policy field.

The run is one grader. That is a recorded deviation from the two-grader rule.
The owner sets the call ceiling and the dollar ceiling. Both are placeholders:

```sh
python scripts/model_eval.py run \
  --live \
  --candidate <OWNER: candidate file for the pinned ids> \
  --output <OWNER: private output directory> \
  --brief <OWNER: private copy of evals/selection-brief.template.json> \
  --max-usd <OWNER: USD for this run> \
  --max-calls <OWNER: integer> \
  --allow-destination <OWNER: exact host, no wildcard>
```

A live run without `--brief` exits 2 with `live comparison requires a frozen
selection brief`, before any provider call. Copy
`evals/selection-brief.template.json` to a private path, replace its
`REPLACE` strings and nulls, including `frozen_on` and every selected task's
gates, and pass that path. The checked-in template is not a filled brief.

`--allow-destination` is the hostname only, exactly the host of the base URL
the candidate's adapter will call. No scheme, no path, and no wildcard. There
is no default host for this adapter. `--max-usd` and `--max-calls` are both
required; omitting either refuses the live run. They stop the run at those
ceilings.
Leave the twin's kill switches and policy file untouched while this process
runs. Do not pass a twin URL, a check key, or a database path.
