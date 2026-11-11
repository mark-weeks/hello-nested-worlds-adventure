# ADR-039: Controlled staging model dispatch and dollar reservations

**Status:** Proposed for this implementation's review, 2026-11-11. The owner
authorized proceeding with the remaining staging controls. This record prepares
the machinery; it approves no provider destination, account terms, dollar amount,
retention period, or live deployment. Those values remain explicit operator
decisions. ADR-034 and the existing world covenants still govern.

## Context

Daily call counts do not bound dollars. Provider SDK retries, a changed endpoint,
unreported usage, concurrent calls, process restarts, and credential rotation can
all defeat a counter or an estimate based on average prompt length. Provider
probes and image generation also bypass the task-facing text runtime.

The owner's proposed spending ceilings are not usage forecasts or approved
settings. A useful control must be reviewable without choosing those values or
sending data to any provider.

## Decision

Use an immutable, strictly validated operator JSON policy in controlled mode.
Hosted Fly configuration and declared temporary test worlds require this mode.
The checked-in example disables every external route and contains no destination,
price, limit, or retention default. Both external kill switches permit booting
without a live policy and freeze an all-off snapshot. An environment change or a
newly appearing key cannot grant a disabled route permission.

An enabled text route names its exact HTTPS Chat Completions URL, adapter,
requested and permitted resolved model ids, request options, output and timeout
bounds, verified maximum billable input bound and its evidence, all applicable
token prices, and references to its data-use decision and approval. Active
policies also supply global and per-participant daily USD ceilings and operational
ledger retention. These declarations require review; a valid file does not prove
remote behavior, pricing, account terms, or owner approval.

The first controlled transport is the built-in OpenAI-compatible adapter, making
one POST without retries, redirects or environment proxies. Validate the captured
settings and request before transmission. Bind a single-use task/credential scope
to the ordinary runtime; direct adapters, wrappers, probes and keyless calls
cannot acquire permission. Anthropic, custom adapters and images refuse in
controlled mode until they have an equivalent audited boundary. Local legacy and
offline fixture behavior remains available outside controlled mode.

Reserve integer microdollars in a separate operational SQLite ledger immediately
before network I/O. One `BEGIN IMMEDIATE` resolves a live credential to its stable
participant, checks both daily totals across all policies/routes, and inserts the
reservation. Credential rotation cannot create a fresh allowance. Transactions
must close before provider I/O. Reservations use the full verified maximum
billable input at the highest applicable input/cache rate plus bounded output;
average token estimates are not hard admission bounds.

Complete, consistent usage can reduce the reservation to its priced amount or a
conservative upper bound when a cache split is missing. Unknown usage, failures
and abandoned calls retain the reservation in the original UTC day. Model drift,
usage outside the declared bounds or a priced overrun retains at least the
reservation and persistently stops further controlled dispatch. Changing policy
or restarting cannot clear that stop. Reconciliation is an operator procedure;
this batch supplies no automatic refund or unlatch.

The ledger stores opaque participant ids, dispatch metadata, frozen policy/prices,
usage counts and money only, never prompts, completions, credentials, credential
digests or IPs. Each row carries its chosen retention deadline; a later policy
cannot shorten it. Expired rows can be pruned only after their spending day has
ended; an independent controlled-server worker applies their deadlines while
idle or closed. An accounting write failure stops that process's later calls and
retains its reservation, but cannot guarantee a stored anomaly latch while the
database cannot commit. Sentry local-variable capture is disabled to keep prepared request state
out of crash reports. This is separate from the owner's chat-log choice; chat
retention is not implemented or decided here.

## Trade-offs accepted

- Full-context reservations can deny a small daily allowance even when a typical
  call would cost much less. Lower reservations require a verified tighter bound,
  not a characters-per-token guess. This must be assessed before live activation.
- This initial controlled adapter coverage is deliberately limited. It is not
  evidence that either provider candidate has passed evaluation.
- The ceiling covers this installation and ledger. Other tools, provider-console
  activity, price changes, remote billing anomalies and restoration of an older
  database require separate reconciliation. Disable external calls before restore
  and reconcile the day's provider spend before re-enabling them.
- Additive operational tables are a forward schema step. No world identity,
  chronicle, birth, historical authorship or puzzle fact changes.

## Revisit when

- A reviewed destination/model needs a second controlled transport or billing type.
- An authoritative tighter input bound permits useful smaller reservations.
- Operator/evaluation scopes or incident reconciliation need an explicit tool.
- Live evidence supports actual cohort budget sizing or different retention.

## Rejected alternatives

- Call counts or average token estimates as dollar ceilings: neither bounds cost.
- Reserve after the response: concurrency and crashes can spend unreserved money.
- Refund missing usage: absence of telemetry does not mean a free request.
- Follow redirects, retry automatically or fall back to another provider: each
  changes the destination or billable attempt without a new reservation.
- Treat an example policy as approval: configuration is evidence to review, not
  consent to send player data or incur charges.
