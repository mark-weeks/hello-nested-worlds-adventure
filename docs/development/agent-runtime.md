# Provider, model and prompt guidance

Read when changing voice quality, provider/model selection, prompt bibles, caching,
or the four text-model call paths. [ADR-034](../decisions/ADR-034-provider-and-model-optionality.md)
defines the optionality policy. Product behavior is the contract; vendors, models
and versions are replaceable choices that require evidence.

## Current implementation and its limits

Text generation uses one registered adapter. `NESTED_WORLDS_PROVIDER` selects
it by name. Unset means `anthropic`, so an existing deployment does not
change. Built-in adapters are `anthropic` and `openai_compatible`. The second
is an OpenAI-compatible Chat Completions client for evaluation. No
destination is approved for production, and no provider other than the
current default has been evaluated or approved (ADR-034). ADR-035 (Proposed)
records the dialect choice and does not enable a destination. The value is
stripped and lowercased. An empty value, or a name that is not registered,
fails startup with one line that names `NESTED_WORLDS_PROVIDER` and the
valid names. The first successful
selection is kept for the process. A later change to that variable does not
reselect the adapter and does not raise from a request.
`reset_provider_selection()` clears the cache; tests use it. There is no
failover onto another provider. A per-task provider is not a setting: every
text task uses the selected adapter. Per-task settings still choose only the
model id.

The Anthropic SDK is the optional extra `enfolded[anthropic]`
(`anthropic>=0.40.0`). Importing Enfolded does not import it. An adapter that
does not declare an SDK, including a fixture registered in tests and the
`openai_compatible` adapter, runs without one. That adapter uses the
standard library.
`python main.py serve` and `python main.py models` exit before a port opens
when the selected adapter's own SDK module is missing. The line names the
extra. Only a `ModuleNotFoundError` whose name is that module, or the root
package when the module name is dotted, becomes the line. A missing
dependency of the SDK, or any other import error, keeps its own
message. The production image still installs `requirements.lock`, which pins
that SDK. A bare `pip install enfolded` does not.

Each text task resolves its own model id through
`consciousness.runtime.model_for(task)`. Call sites pass a task name; they do
not read environment variables.

| Task name | Setting | When unset |
|---|---|---|
| `node` (node voice) | `NESTED_WORLDS_NODE_MODEL` | `NESTED_WORLDS_MODEL`, then the selected adapter's own default |
| `inhabitant` (inhabitant voice) | `NESTED_WORLDS_INHABITANT_MODEL` | `NESTED_WORLDS_MODEL`, then the selected adapter's own default |
| `intent` (intention interpretation) | `NESTED_WORLDS_INTENT_MODEL` | `NESTED_WORLDS_MODEL`, then the selected adapter's own default |
| `moderation` | `NESTED_WORLDS_MODERATION_MODEL` | the selected adapter's own moderation default |

An unset value uses the fallback in the table. `model_for` also treats a
whitespace-only value as unset, so a call still falls back. The startup check
does not: a variable set to empty or whitespace is a misconfiguration and
`python main.py serve` refuses to boot. A blank setting used to fall through
at boot. It now fails startup. Moderation does not inherit the shared voice
model, and its id is checked even when `NESTED_WORLDS_DISABLE_MODERATION=1`.
Each adapter supplies those defaults with an optional `default_model(task)`.
The method is not part of `TextProvider`. `model_for` asks `get_provider()`
for them, the same adapter `generate` calls. The anthropic adapter returns
`claude-opus-4-8` for node voice, inhabitant voice, and intention, and
`claude-haiku-4-5` for moderation. Another adapter does not inherit those
ids. The `openai_compatible` adapter supplies no `default_model`, so all
four tasks must be set or `python main.py serve` refuses to boot. If a task
would use `source=default` and the adapter does not supply a non-blank id,
`model_for` returns an empty id, `python main.py models` reports a hard
problem, and `python main.py serve` exits before it opens a port. A call that still asks for that empty id raises `UnusableModelId`
before the model-action cap and before the voice budget, and the provider
is not called. Shared text is held. The first selection builds its adapter
once; a factory that calls back into selection raises rather than waiting
on the lock it already holds. A task setting, or `NESTED_WORLDS_MODEL` for
every task except moderation, still overrides the adapter default. With no per-task settings
on the anthropic adapter, node voice, inhabitant voice, and intention keep
using `NESTED_WORLDS_MODEL`, then `claude-opus-4-8`, so an existing
deployment that leaves those variables unset does not change. Run
`python main.py models` with the release environment before a release or
`scripts/deploy.sh`. The anthropic code defaults are configuration, not a
verified recommendation or a guarantee of availability. Confirm the
effective environment before a live run.

The current adapter uses the SDK's resolved credentials: `ANTHROPIC_API_KEY`,
`ANTHROPIC_AUTH_TOKEN` (bearer token), or its local profile/federation
credential provider. The availability check uses the same SDK client as
generation; it checks configuration without making a model request, not
credential validity. This behavior is verified against the
[pinned SDK source](https://github.com/anthropics/anthropic-sdk-python/blob/v0.120.2/src/anthropic/_client.py).

A model id does not switch providers. `NESTED_WORLDS_PROVIDER` does. Credentials,
SDK calls, structured output and cache controls must match the selected
adapter. A failed call stays on the id that was requested: nothing retries a
different model or provider. Provider-named budget settings and persisted
buckets are current compatibility details; do not rename/reset them to make
the interface look neutral or let a provider switch replenish a user's
allowance. The `anthropic` bucket and `NESTED_WORLDS_ANTHROPIC_*` names stay
as they are. Despite those names, `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` and
`NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` count voice calls on every
text provider. Selecting `openai_compatible` does not replenish that
allowance. Daily call caps are not dollar caps, and identical call counts
do not imply identical spend.

In-flight calls are limited per provider. `NESTED_WORLDS_ANTHROPIC_CONCURRENCY`
is unchanged and applies only to the anthropic adapter (default 8).
`openai_compatible` reads `NESTED_WORLDS_OPENAI_COMPATIBLE_CONCURRENCY`.
Another adapter reads `NESTED_WORLDS_<NAME>_CONCURRENCY` with the same
default. One provider's cap does not consume another's. Unset, empty, and
non-numeric values use 8. Zero and negative values clamp to 1.

The optional image path has a separate fal.ai integration. Future image or speech
adapters follow the same selection principle, with their own capability and data
requirements. This policy does not claim those adapters already exist.

## Compare before selecting

The [evaluation harness](../../evals/README.md) implements the synthetic corpus,
production-task runner, blind human grading, comparison reports and predeclared
selection checks. Start with fixture validation, then a budgeted live baseline.
Fixture success does not qualify a model; human calibration and live evidence
remain separate requirements. The harness does not change runtime defaults.

Use the incumbent as a baseline and include a materially different credible
candidate when practical. Deterministic behavior or no model call is a valid
baseline: ambient traversal and banter already run without paid inference.

Before running a comparison, define the task's pass criteria and the trade-offs
that would justify switching. Use the same representative inputs and world
contexts; permit documented provider-specific prompt tuning, then recheck the
common cases. Do not silently trade required correctness for a lower price.

| Task | Evidence to collect |
|---|---|
| Node and inhabitant voices | Distinct registers across all 11 scales and personas; memory and world-state fidelity; multi-turn continuity; no invented events, hidden mechanics or inappropriate loss of fiction |
| Intention interpretation | Valid bounded steps; clarification only for material ambiguity; refusal of unsupported actions, negations and forced agency; no predicted outcomes; application validation rejects malformed or truncated output |
| Moderation | Clear and ambiguous examples, false blocks and misses, timeout behavior, and the shared-text fail-closed contract: a local clean verdict still publishes, and unjudged shared text is held |
| Operations | End-to-end latency including tail latency, failures and retries, rate/concurrency limits, availability, actual token/cache usage and total cost per successful interaction at expected traffic |

Verify current model IDs, capabilities, prices and relevant retention/training,
region and data-handling terms against official sources when selecting a candidate.
Include cache writes, cache misses, long prompts, retries and integration/operating
costs; compare cold and warm use instead of assuming cache savings. Do not send
private transcripts to another provider just to run an evaluation; use fixtures or
data authorized for that destination.

Record the provider, exact model/version or alias, date, prompt/config revision,
sample sizes, results, limits, selection rationale and rollback configuration in
a dated evaluation. Separate fixture results from live measurements and human
judgment. An unavailable live run is an evidence gap, not a pass. A code-default
change and a deployment remain separate actions under the existing project gates.

## Integration boundary

`consciousness/runtime.py` defines `TextProvider`, `SystemBlock`, `Completion`
and `TokenUsage`, resolves per-task model ids in `model_for`, selects the
adapter from `NESTED_WORLDS_PROVIDER`, keeps a separate concurrency limit per
provider, and logs provider/model usage. `TextProvider` does not
include `model_id_validator`, so an adapter that omits it still satisfies
the protocol for type checkers. `ModelIdJudgingProvider` is the optional
protocol for adapters that can judge ids. Its method returns a function from
a model id to `ok`, `warn`, or `reject`, or nothing when the adapter does
not judge ids. `reject` means this adapter does not serve the id. `warn`
means the id is plausible but not a known release. Omitting the method is
the default. `consciousness/model_check.py` is the only caller, uses
getattr, and does not name a provider. The shared check rejects only empty
text, whitespace, control characters, and an id longer than 256 characters.
Character rules such as `@`, `+`, and `~` stay on the adapter.
`consciousness/anthropic_provider.py` implements the default built-in adapter.
`get_provider()` loads it when `NESTED_WORLDS_PROVIDER` is unset or `anthropic`,
and keeps that adapter for the process.
The module does not import the SDK; the client import stays inside the
adapter, and startup reports a missing extra before it asks for a client.
Only a `ModuleNotFoundError` whose name is the adapter's own SDK module,
or the root package when that name is dotted, becomes that
line. A missing dependency of the SDK, or any other import error, keeps its
own message.
Its validator accepts the known Claude ids and a dated snapshot of one of
them. Any other usable id that names Claude warns, including mixed case,
`anthropic/claude-…`, `….anthropic.claude-…-v1:0`, and a `:beta` suffix, so
a new release or alias does not block boot. With `ANTHROPIC_BASE_URL` set
to a non-blank value, every other usable id warns too, because a gateway
alias is not a Claude id. A blank or whitespace `ANTHROPIC_BASE_URL` is
unset, and the check does not log that URL. An id that neither names Claude
nor sits behind that override is rejected, so `gpt-4o` on the official API
fails startup. All four tasks use the boundary; the node voice, inhabitant
voice and intention endpoints ask the selected adapter whether it is
configured before charging their existing voice budgets. Missing
credentials serve authored fallbacks without a voice call, budget charge or
speech chronicle row. A model-written chronicle row records the provider name
and the resolved model id from that call's Completion, in
`mutation_model_provenance`. The call was made with `model_for(task)`; the
stored id is the one the provider returned for that call, not a later read of
the setting, and a missing response id stays unknown. Historical rows are not
backfilled. Authored fallback text records none. Player history, the chronicle
page and node voices do not read the side table. Deleting a chronicle row
deletes its provenance row with it. Another provider still requires an
adapter registered by name. Selection is `NESTED_WORLDS_PROVIDER`. There is
no automatic failover. Per-task model settings are not a provider selector,
and there is no per-task provider override.


Keep task prompts, transcripts and deterministic validation in application code.
Put SDK/client construction, credential checks, provider payloads, response and
usage normalization, and provider-specific cache/schema features behind a small
adapter boundary. Unsupported required capabilities must produce the existing
safe task behavior, not a silent weaker request or a hidden provider fallback.

Test the boundary without paid calls: request construction, history ordering,
text extraction, completion/refusal/truncation handling, schema behavior, timeout,
usage fields, missing credentials and provider failures. Exercise the existing
HTTP fallback and budget tests too. A replacement must preserve application-owned
state and receipts; provider I/O must stay outside SQLite transactions. The
registry is the selection seam: register the adapter and set
`NESTED_WORLDS_PROVIDER`. Do not add a provider by renaming the anthropic
budget bucket.

`consciousness/openai_compat_provider.py` is the second built-in, named
`openai_compatible`. It is available for evaluation. Registering it does
not approve a data destination, and no provider other than the current
default has been evaluated or approved. It posts Chat Completions to the
base URL the operator sets. It does not read `OPENAI_*` or `XAI_*`. It has
no default model id and does not judge ids by vendor prefix. The base URL
and the API key are never logged and never placed in an exception message.
A failure log records the exception class only.

| Variable | Meaning |
|---|---|
| `NESTED_WORLDS_OPENAI_COMPATIBLE_BASE_URL` | Required. `https`, or `http` on `127.0.0.1`, `localhost`, or `::1`. Userinfo, a query, and a fragment are rejected. Not logged. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_API_KEY` | Required except on loopback. A present value that is not ASCII, not printable, or contains whitespace leaves the adapter unconfigured on every host, including loopback. Not logged. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_MAX_OUTPUT_PARAM` | Wire field for the caller's max output: `max_completion_tokens` (default) or `max_tokens`. Any other value leaves the adapter unconfigured. The name does not contain `TOKEN`, so `model_check` does not redact the value as a secret. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_STRUCTURED_OUTPUTS` | `1` sends strict `json_schema`. Unset, a task that needs a schema raises `UnsupportedCapability` and the caller serves the authored fallback. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_SEND_STORE_FALSE` | `1` sends `"store": false`. Unset sends nothing. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_REASONING_EFFORT` | Optional `none`, `minimal`, `low`, `medium`, or `high`. Unset sends nothing. Any other value leaves the adapter unconfigured and is not forwarded. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_TIMEOUT_SECONDS` | Wall-clock budget for one POST when the caller passes no timeout. Default 60. urllib's own timeout is a limit on one socket operation; this adapter does not pass the caller's number through as that. DNS lookup and individual TLS handshake bytes are not covered. Moderation still passes 3 seconds. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_CONCURRENCY` | In-flight cap for this adapter. Default 8. It does not share the anthropic cap. |

All four task model variables must be set. A reasoning model can spend
`max_completion_tokens` on reasoning, so moderation's 32, the probe's 1,
and the voice caps of 200 and 256 can finish `length`. A length stop is
undecided, and every ambiguous line is then held. Use a non-reasoning
model, or set the reasoning effort to `none` or `minimal` when the
endpoint honors it. On some servers reasoning tokens sit outside
`completion_tokens` and are not capped by that field. Output usage is
`total_tokens - prompt_tokens` when both are present and the difference is
non-negative, so those tokens are still counted. Without both fields,
output usage is unknown. `completion_tokens` is not a fallback. The request
never sends `n` or `stream`. Only `choices[0]` is read. More than one
choice, or content that is present and not a string, is malformed and held.
Empty or whitespace-only content is not complete. A missing `refusal`
counts as null. Any HTTP 3xx raises `ProviderHTTPError` with the status
code only and is not followed, so `Authorization` is not sent to another
host. `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and the lowercase forms are
not read. The caller's timeout is a wall-clock budget for that one POST.
urllib's own timeout is a limit on one socket operation, and this adapter
does not pass the caller's number through as that. DNS lookup and
individual TLS handshake bytes are not covered. The chronicle stores a
model id only after `_model_mark` in `persistence/__init__.py`: surrounding
whitespace is stripped, and a non-string, a blank, a control character, or
a value longer than 200 characters is dropped rather than stored or
truncated. A server may echo an alias such as `latest`; that string is
kept when it survives that function. The evaluation harness is unchanged.
Production enablement is a separate decision and is not made by registering
this adapter.

## Voice and caching

For flat voices, inspect which world-state the dynamic prompt omits before changing the
model. This is a diagnostic starting point, not a conclusion that model capability can
never be the bottleneck. Compare representative voices when evaluating a model change.

When changing models or cache structure, verify the selected provider/model's
current cache semantics and minimum against official documentation. The existing
`cached_prefix_meets_minimum()` and startup `warn_if_cache_ineffective()` guard
use a rough character-based estimate and adapter-owned reference metadata for
the resolved node-voice and inhabitant-voice models (the requests that send
the cached bibles). When those ids match, the advisory is the same single
comparison as before
([Claude API reference verified 2026-10-05](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#cache-limitations):
Opus 4.5/4.6 and Haiku 4.5: 4096 tokens; Opus 4.7: 2048;
Opus 4.8 and Sonnet 4.5/4.6: 1024). The adapter recognizes those exact versions
and their dated snapshot suffixes; it does not extrapolate to future versions.
Unrecognized IDs report unknown eligibility and the estimated smaller prefix
size. These estimates do not establish actual tokenization, model availability,
a cache hit or a universal minimum. Keep the warning useful when
replacing that integration; a provider without explicit cache controls needs its
own usage evidence, not a request shaped for the configured provider (currently Anthropic).

Retain useful lore and behavioral guidance. Do not pad prompts merely to cross a
cache threshold or forbid a worthwhile prompt reduction: compare task quality
and total cost under the selected model's actual cache behavior.

Complete a voice/caching change with relevant prompt behavior tests and observed evidence
for the claimed improvement. Report any unavailable live-model verification; avoid claiming
a cache hit from the presence of `cache_control` alone.

## Startup model check

`python main.py models` prints the provider selected by the registry and, for
each task, that provider, the resolved model id, where it came from
(`task env`, `NESTED_WORLDS_MODEL`, or `default`), and any problem. It does
not call the provider. Run it with the provider and model variables the
machine will use before a release, `scripts/deploy.sh`, or a Fly boot. The
moderation model is included even when `NESTED_WORLDS_DISABLE_MODERATION=1`.
An unknown provider name, or a selected adapter whose SDK is not installed,
exits with one line before the report. The missing-SDK line names the
optional extra.

A hard problem is one line naming the environment variable: an empty or
whitespace-only setting, unusable text (whitespace inside the id, a control
character, or more than 256 characters), or an id the active adapter
rejects. A blank model setting, and on the Anthropic adapter an id that
neither names Claude nor sits behind a non-blank `ANTHROPIC_BASE_URL`, fails
startup instead of falling back. `python main.py serve` exits with that line
before it opens a port, so the deploy fails instead of holding shared text
on the first moderation call. A soft problem, including surrounding
whitespace that was stripped, a Claude-shaped alias, and any usable id while
`ANTHROPIC_BASE_URL` is set, logs one warning and still boots. Neither line
prints a credential or the base URL. `/health` stays a liveness check and
does not report model ids.

`python main.py models --probe` makes one tiny live call per distinct model
id (`max_tokens` 1). It is off unless that flag is passed. Server startup,
`./scripts/check.sh`, tests, and CI do not pass it, and there is no
environment variable that turns it on. It checks `configured()` first. When
that is false, or when it raises, the command prints
`skipped: provider not configured` and exits 1. It does not call the
provider and does not report a `TypeError`. A configured probe needs a
credential, spends a real call, and does not charge the model-action cap or
the `anthropic` budget bucket. A refused probe also exits 1. It confirms the
provider accepts the id. It is not a quality, cost, or cache evaluation.

## Operator diagnostics

Both CLI speech paths log failures to `nested_worlds.cli` at WARNING. By default
a `NullHandler` keeps diagnostics off the player's terminal. Operators can attach
a Python logging `FileHandler` to that logger (or configure a file handler on an
ancestor) before invoking the CLI. Records contain an exception class or a
normalized no-text finish reason, not raw SDK error bodies, credentials or
submitted text. The CLI still prints the authored in-fiction fallback. Providers
normalize completion reasons at the boundary; voice extraction preserves partial
text but raises a shared no-text error for missing output, distinguishing refusal
from an unknown or anomalous finish.
