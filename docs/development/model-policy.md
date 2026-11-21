# Controlled staging model calls

This batch implements a closed-by-default control boundary, not live activation.
No provider, endpoint, numeric spending limit, token price or ledger-retention
period is selected by the checked-in configuration. The owner's earlier ceiling
proposals remain proposals; they are not forecasts or approved settings.

The first controlled adapter/vendor remains an open owner decision. The code
currently supports only the built-in `openai_compatible` Chat Completions path;
ADR-035 is still Proposed. Live voice on Fly, production included, is blocked
until ADR-035 is accepted or a controlled Anthropic path exists, and the
destination/account terms, models, prices, dollar amounts and retention have
scoped approval. An implementation request in the working session is not
independent ratification of ADR-039 or approval of those values. This batch does
not implement chat retention.

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

## Clearing the stop

There is still no unlatch command, no audit table, and no migration. The only
application write to `model_spend_latch` is an insert that does nothing when
the row is already there (`persistence/model_spend.py`, `_latch`). Nothing in
application code deletes that row. [ADR-039](../decisions/ADR-039-controlled-model-spend.md)
stays Proposed. Its decision text still stands: no automatic refund or unlatch,
and an explicit tool is a "Revisit when" trigger, not this section.

[Owner decision O9](../roadmap/owner-decisions-2026-11-20.md#o9-clearing-the-latched-spend-stop-items-3-28)
(2026-11-20) adopts a hand-SQL clear for the disposable watch twin only. The
machine commands and the guarded script are in
[Clearing the stop](../infrastructure/incident-response.md#clearing-the-stop).
This section is the accounting contract those steps implement.

### What is true on this revision

The stop is one row in `model_spend_latch`. The table's primary key allows
only `singleton = 1`, and `reason` is one of `billing_anomaly`,
`accounting_fault`, or `unsettled_startup`
(`persistence/migrations/0032_model_spend.sql`). The migration states the
consequence: a restart, a new UTC day, a policy replacement, or expired-row
cleanup never clears the circuit, and there is no application reset operation.

`check_unsettled_on_startup` runs inside the server's boot when controlled
mode has a policy, including when the kill switches are on
(`server/__init__.py` calls `initialize_accounting`). If any
`model_spend_reservations` row still has `status = 'reserved'`, that function
inserts `unsettled_startup` (leaving an existing reason in place) and sets
`abandoned_at` on those rows. It does not change `accounted_microusd`. The
same scan runs once per process and database (`_initialized_databases` in
`consciousness/model_dispatch.py`). A later call in that process does not
scan again.

An `unsettled_startup` latch therefore leaves `status = 'reserved'` rows.
Those rows latch again at the next start until they leave that status.
`settle` refuses a row whose `abandoned_at` is set, so the application cannot
finish them. Hand SQL is the resolution on the twin.

`_settlement_fault` (`consciousness/model_dispatch.py`) is an event in the
server process. A database clear does not reset it. The process keeps
refusing controlled dispatch until the machine is restarted and a new process
takes its place.

### Where this procedure applies

Run it on the disposable watch twin, and rehearse it first on a separate
throwaway Fly app. Both need a fresh backup immediately before the write.

A kept world that will serve any live model route needs an audited clear
command first. That command is an ADR-039 revision and its own migration.
Hand SQL on a kept world's volume is not acceptable. This section does not
add the command. It waits until ADR-041 naming's migration has merged,
because one migration pull request is open at a time, and until the owner
has accepted the ADR-039 revision.

### What a clear requires

Record every item below before the write, in a dated private operator entry
kept outside the world database and outside player-visible history. The entry
names the Fly app, the backup path, and the UTC time. It is not a chronicle
row and not a chat line. Items 1 to 4 are O9's evidence. Item 5 is required
when the reason is `billing_anomaly`.

1. The provider console's spend for every UTC day the read-only listing
   prints under `reconcile days`. That set is the UTC day of `latched_at`,
   every day that still has a `reserved` row, and every day that has an
   `anomaly` row. An anomalous settlement after midnight keeps the charge
   on the reservation's original day, so `latched_at` alone can miss it.
   Beside each figure, the ledger's summed `accounted_microusd` for that
   day. One USD is 1,000,000 microUSD. The console total and the ledger
   total are both evidence. A lower console total is the usual case,
   because admission reserves the full context bound. Do not write the
   console's number into the ledger.
2. The latch reason and `latched_at`.
3. Every `reserved` row, listed before the write and resolved by the write.
4. The dated entry itself, completed with the backup path before the write.
5. When the reason is `billing_anomaly`, each `anomaly` row's
   `resolved_model`, `usage_json`, `reserved_microusd`, and
   `accounted_microusd`, and the cause. Settlement flags an anomaly when
   the resolved model is outside the route, the provider is not the route's
   adapter, the billing evidence is inconsistent, or a token count exceeds
   the route's bound. A priceable count above that bound can account more
   than the reservation. That is the case where the ceiling does not hold.
   Leave the latch until the owner corrects the route's resolved-model
   list, token bounds, or prices. Those amounts are the owner's under O4
   and O5. This procedure does not change them. With the same policy, the
   next confirming call latches again, or charges above the reservation
   again.

If the console total is higher than this installation's ledger in a way the
recorded calls do not explain, leave the latch in place and keep external
routes off. The gap is a separate reconciliation. ADR-039 already treats
other tools, console activity, and a restored older database as outside this
ledger.

A clear never refunds the day's spend. The write does not lower
`accounted_microusd`, does not change `day`, and does not delete a
reservation. Those columns are what the daily ceilings sum.

A clear never shortens retention. The write does not change
`retention_days` or `retain_until`, and it does not delete a row to make
the latch disappear.

A restart is not a clear. `fly machine restart`, `fly secrets set`, and a
crash start a new process. That process runs the startup scan. An existing
latch row stays. `reserved` rows are marked abandoned and, when no latch
existed yet, become `unsettled_startup`. The old process's
`_settlement_fault` dies with the process; the database latch remains.

A new app, a new volume, or a re-created twin is not a clear. The provider
has already billed the UTC day. Replacing the database leaves that bill in
place and throws away the ledger that recorded it.

### The five steps

1. **Quiesce dispatch.** Record the current `NESTED_WORLDS_DISABLE_AI` and
   `NESTED_WORLDS_DISABLE_MODERATION` values, including a name that is
   unset. Then set both to `1` on that app, and confirm
   `NESTED_WORLDS_DISABLE_IMAGES=1`. One `fly secrets set` restarts the
   machine. That restart is not a clear. Wait until `/health` is ok and
   `python main.py models`, run on the machine, shows every route
   `disabled (intentional)`. The switches stay on until the post-write
   restart has been confirmed. Between the commit and that restart, a
   running process whose in-memory fault is clear would admit a new
   reservation the moment the latch row is gone, and the next boot would
   latch `unsettled_startup` again.
2. **Reconcile outstanding reservations.** Take the fresh backup, copy it
   off the machine, and record its path. Then resolve every `reserved` row
   inside the same immediate transaction as the latch delete. Resolution
   keeps the money and the retention columns, and moves the row to the
   status the application already uses when usage is unknown:

   ```sql
   UPDATE model_spend_reservations
   SET status = 'uncertain',
       settled_at = :utc,
       abandoned_at = NULL
   WHERE status = 'reserved';
   ```

   `:utc` is a UTC stamp in the ledger's own form,
   `2026-11-20T23:40:00.000000Z`. `settled_at` has to be set because a
   non-reserved row must have it. `abandoned_at` has to become NULL because
   the table allows that column only while `status = 'reserved'`.
   `accounted_microusd` is already equal to `reserved_microusd` on a
   reserved row; leaving it untouched satisfies the `uncertain` check and
   does not refund the ceiling. Rows already `settled`, `uncertain`, or
   `anomaly` stay as they are, including a `billing_anomaly` row that has
   already been settled at or above its reservation.
3. **Clear the latch row,** in that same transaction, only after a count of
   `status = 'reserved'` is zero and every row's `accounted_microusd`,
   `day`, `retention_days`, and `retain_until` still match the pre-write
   snapshot:

   ```sql
   DELETE FROM model_spend_latch WHERE singleton = 1;
   ```

   If any check fails, roll the transaction back. The latch stays. Do not
   delete reservations, do not vacuum, and do not edit any other table.
4. **Restart the machine.** The new process runs the startup scan. With no
   reserved row and no latch row, the scan does not stop dispatch. The new
   process's `_settlement_fault` starts clear.
5. **Confirm, then one settled call.** On the machine, `python main.py models`
   and `python main.py voice-health` must report `model accounting durable
   stop: no`, `model accounting unresolved reservations: 0`, and
   `model controls: no recorded stop`, and must not report `STOPPED`.
   Those commands read the database and their own process, not the server's
   memory. The restart is what drops the server's event. Restore the voice
   and moderation values recorded in step 1, or unset a name that was unset.
   Do not write `0` unless that was the recorded value. A `0` secret
   overrides `fly.toml`, whose `NESTED_WORLDS_DISABLE_AI` is `1`. Unsetting
   that name restores the committed `1`. If the restored voice value does
   not admit a call, leave it. The clear stays incomplete until the owner
   records the live value to restore. That set restarts the machine again
   and is not a clear. Re-read the same lines.
   Then make one ordinary authenticated gameplay call that is expected to
   dispatch: a place line, an agent line, or an Act free-text intention.
   Do not use an identity question, and do not use `--probe` (controlled
   mode refuses it). Every reservation that call creates is `settled`, with
   `accounted_microusd` less than or equal to `reserved_microusd`, and the
   latch table is still empty. The clear is complete only then.

   Those reservations count against the current UTC day's ceiling at their
   full admission bound. Rows resolved onto an earlier `day` do not consume
   today's ceiling. Rows whose `day` is today still do, at the full
   `accounted_microusd` the clear refused to lower. The clear is complete
   only when every row that call creates is `settled`. If any created row
   is not `settled`, if no row was created, or if a latch row exists, set
   both kill switches back to 1 before another paid call. That includes an
   allowance refusal and a usable reply that settled as `uncertain` because
   usage was missing: the full reservation stays, no latch is written, and
   paid routes would still accept another call. Leave the latch deleted if
   the clear already committed. Reconcile the rows, and make the confirming
   call only once the current UTC day can admit one reservation and the
   recorded switch values are restored again. Do not substitute `0`. Until
   that call's rows are all `settled`,
   the clear is not complete and the switches stay at 1.

The guarded script that performs steps 2 and 3, and the read-only listing
for the evidence entry, are in the incident procedure. Before it opens the
database writable, Fly's `FLY_APP_NAME` must equal the app name the operator
passes, that name must not be `enfolded-beta`, and
`NESTED_WORLDS_TEST_WORLD` must be on. The operator does not assign
`FLY_APP_NAME`. The write also refuses unless `ENFOLDED_CLEAR_DAYS` names
every reconcile day, including an anomaly row's original day. It opens only
`/data/.nested-worlds/worlds.db`, read-write without creating the file. A
`billing_anomaly` latch stays until the owner has corrected the route. The
off-machine backup goes into a fresh `0700` directory, and the downloaded
file is mode `0600`.

### Rehearsal

By Friday 4 December 2026, before the first watch session, rehearse this
procedure on a separate throwaway Fly app with
`NESTED_WORLDS_TEST_WORLD=1` set before first boot. The gameplay calls use
a credential that has accepted the current participation notice. The
rehearsal covers one settled reservation, one stop produced by the
application (a reserved row left by process death, then a restart that
records the latch), the evidence items, the hand-SQL clear, the restart,
and one settled call after it.
Inserting a latch row by hand does not count as that stop. The steps are
written in the incident procedure and are not run from this repository.
ADR-039 is accepted only after that rehearsal passes, and only in the
records or status pull request the owner names.
