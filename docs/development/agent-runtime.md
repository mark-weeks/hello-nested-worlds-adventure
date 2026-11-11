# Provider, model and prompt guidance

Read when changing voice quality, provider/model selection, prompt bibles, caching,
or the four text-model call paths. [ADR-034](../decisions/ADR-034-provider-and-model-optionality.md)
defines the optionality policy. Product behavior is the contract; vendors, models
and versions are replaceable choices that require evidence.

## Current implementation and its limits

Outside controlled mode (below), text generation uses registered adapters. `NESTED_WORLDS_PROVIDER` selects
the process default. Unset means `anthropic`, so an existing deployment
that sets nothing new does not change and does not enable another
destination. Each text task may override that choice with
`NESTED_WORLDS_NODE_PROVIDER`, `NESTED_WORLDS_INHABITANT_PROVIDER`,
`NESTED_WORLDS_INTENT_PROVIDER`, or `NESTED_WORLDS_MODERATION_PROVIDER`.
An unset task variable uses the process default. Built-in adapters are
`anthropic` and `openai_compatible`. The second is an OpenAI-compatible
Chat Completions client for evaluation. No destination is approved for
production, and no provider other than the current default has been
evaluated or approved (ADR-034). ADR-035 (Proposed) records the dialect
choice and does not enable a destination. A value is stripped and
lowercased. A blank value, or a name that is not registered, fails startup
with one line that names the variable that supplied it and the valid
names. An unsafe value is not echoed. The name does not fall through to
another adapter. The first successful selection of each provider is kept
for the process. A later change to a variable that already resolved does
not reselect and does not raise from a request.
`reset_provider_selection()` clears the cache; tests use it. There is no
failover onto another provider. A failure is not retried on another
provider, and one provider's in-flight slots do not block a task routed
to a different provider.

The Anthropic SDK is the optional extra `enfolded[anthropic]`
(`anthropic>=0.40.0`). Importing Enfolded does not import it. An adapter that
does not declare an SDK, including a fixture registered in tests and the
`openai_compatible` adapter, runs without one. That adapter uses the
standard library.
`python main.py serve` and `python main.py models` exit before a port opens
when a task's adapter's own SDK module is missing. The line names the
variable that selected that adapter and the extra. Only a `ModuleNotFoundError` whose name is that module, or the root
package when the module name is dotted, becomes the line. A missing
dependency of the SDK, or any other import error, keeps its own
message. The production image still installs `requirements.lock`, which pins
that SDK. A bare `pip install enfolded` does not.

Each text task resolves its own model id through
`consciousness.runtime.model_for(task)`. Call sites pass a task name; they do
not read environment variables.

| Task name | Provider, when unset | Model setting | When the model is unset |
|---|---|---|---|
| `node` (node voice) | `NESTED_WORLDS_NODE_PROVIDER`, else the process default | `NESTED_WORLDS_NODE_MODEL` | `NESTED_WORLDS_MODEL`, then that task's provider's own default |
| `inhabitant` (inhabitant voice) | `NESTED_WORLDS_INHABITANT_PROVIDER`, else the process default | `NESTED_WORLDS_INHABITANT_MODEL` | `NESTED_WORLDS_MODEL`, then that task's provider's own default |
| `intent` (intention interpretation) | `NESTED_WORLDS_INTENT_PROVIDER`, else the process default | `NESTED_WORLDS_INTENT_MODEL` | `NESTED_WORLDS_MODEL`, then that task's provider's own default |
| `moderation` | `NESTED_WORLDS_MODERATION_PROVIDER`, else the process default | `NESTED_WORLDS_MODERATION_MODEL` | that task's provider's own moderation default |

An unset value uses the fallback in the table. `model_for` also treats a
whitespace-only value as unset, so a call still falls back. The startup check
does not: a variable set to empty or whitespace is a misconfiguration and
`python main.py serve` refuses to boot. A blank setting used to fall through
at boot. It now fails startup. Moderation does not inherit the shared voice
model, and its id is checked even when `NESTED_WORLDS_DISABLE_MODERATION=1`.
Each adapter supplies those defaults with an optional `default_model(task)`.
The method is not part of `TextProvider`. `model_for` asks `provider_for(task)`
for them, the same adapter `generate` calls for that task. A task with no
provider override shares `get_provider()`. The anthropic adapter returns
`claude-opus-4-8` for node voice, inhabitant voice, and intention, and
`claude-haiku-4-5` for moderation. Another adapter does not inherit those
ids. The `openai_compatible` adapter supplies no `default_model`, so a task
routed to it must name an id: its own model variable, or
`NESTED_WORLDS_MODEL` for node voice, inhabitant voice, and intention.
Moderation on that adapter needs `NESTED_WORLDS_MODERATION_MODEL`. It does
not inherit the anthropic ids. If a task
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

A model id does not switch providers. `NESTED_WORLDS_PROVIDER`, or a task's
provider variable, does. `NESTED_WORLDS_MODEL` is a model id shared onto
whichever provider serves node voice, inhabitant voice, and intention,
including when those tasks use different providers. It is not a provider
selector, and moderation never inherits it. An id the task's provider
rejects fails startup. Credentials, SDK calls, structured output and cache
controls must match that task's adapter. A failed call stays on the id and
the provider that were requested: nothing retries a different model or
provider. Switching providers, mixing providers across tasks, or adopting
the neutral budget names must not replenish or multiply a daily or per-user
allowance. New voice calls persist under `anthropic`, and new image calls
under `fal_ai`, including the existing `:u:<hash>` per-user keys. The
public names do not rename those rows. There is no migration and no copy.
A `voice` or `image` row left by the declined key-rename build still
counts on this binary and is not rewritten; a schema-29 binary does not
read it, so those names are not the supported store. Node voice,
inhabitant voice, and intention share that one voice allowance, whichever
providers serve them. Moderation keeps its separate `moderation` bucket.
`NESTED_WORLDS_VOICE_DAILY_CALLS` and
`NESTED_WORLDS_VOICE_DAILY_CALLS_PER_USER` are the neutral voice caps.
`NESTED_WORLDS_IMAGE_DAILY_CALLS` and
`NESTED_WORLDS_IMAGE_DAILY_CALLS_PER_USER` are the neutral image caps. The
legacy `NESTED_WORLDS_ANTHROPIC_*` and `NESTED_WORLDS_FAL_*` names are still
accepted. A blank or whitespace value is unset. One integer, with the other
name absent or blank, uses that integer. Both equal uses that integer.
Both different uses the lower integer, so the allowance cannot rise.
`python main.py models`, `python main.py serve`, and `python main.py
voice-health` print that disagreement and keep going; `serve` logs it and
still opens the port. Set the legacy variable to the same integer when
raising a cap, in the one `fly secrets set`. A leftover lower value is
what requests enforce. An older binary reads only the four legacy
variables and ignores the neutral names. Its defaults are voice 500 and
150, image 200 and 60. Copy every effective cap, including a `0`, onto
those variables before a same-schema rollback, or the older process can
admit calls this one refused. A non-integer or a negative
value refuses the allowance (cap 0, no increment) and exits `models`,
`serve`, and `voice-health`, without echoing the value. `0` is a valid cap
and refuses every call.
Daily call caps are not dollar caps, and identical call counts do not imply
identical spend. Per-provider slot limits stay
`NESTED_WORLDS_<NAME>_CONCURRENCY` and
`NESTED_WORLDS_<NAME>_SLOT_WAIT_SECONDS`. Those are not the shared budget
and are not renamed to `voice`.

In-flight calls are limited per provider. `NESTED_WORLDS_ANTHROPIC_CONCURRENCY`
is unchanged and applies only to the anthropic adapter (default 8).
`openai_compatible` reads `NESTED_WORLDS_OPENAI_COMPATIBLE_CONCURRENCY`.
Another adapter reads `NESTED_WORLDS_<NAME>_CONCURRENCY` with the same
default. One provider's cap does not consume another's. Unset, empty, and
non-numeric values use 8. Zero and negative values clamp to 1.

A call that finds every slot taken waits a bounded time, never without
limit: its own `timeout` when it passes one (the moderation classify passes
3 s), otherwise `NESTED_WORLDS_<NAME>_SLOT_WAIT_SECONDS` (default 10; empty,
non-numeric or non-finite uses 10, zero or negative means no wait). When no
slot opens, `runtime.generate` raises `ProviderBusy` without calling the
provider. The model-action and voice-budget charges already taken stand, as
they do for any failure after the charge. Callers answer in fiction: the
voice surfaces give the authored silence a provider failure gets, shared text
is held (moderation outcome `busy`), and the voice outcome `busy` is a
failure in `python main.py voice-health`.

A `timeout` passed to `runtime.generate`, or straight to an adapter's
`generate`, allows one provider attempt under that timeout
(`TextProvider.generate`): an adapter must not retry or wait out a
provider's retry-after, and shared code retries nothing. It is not a total
deadline: `runtime.generate` first waits up to the same timeout for a slot
and then hands the adapter the full timeout. Only the
moderation classify (3 s, through `runtime.generate`) and the opt-in
`--probe` of `models` and `voice-health` (30 s per model id, straight to the
adapter) pass one. The
anthropic adapter sends those calls with the SDK's retries off, through a
`with_options(max_retries=0)` copy of its client built once and sharing its
connection pool, credentials and base URL; calls without a timeout keep the
SDK's default retries, each attempt under the adapter's own
`NESTED_WORLDS_ANTHROPIC_TIMEOUT_SECONDS` (default 60 s; table below).
`openai_compatible` already made one POST within a
wall-clock budget. On the anthropic adapter httpx applies the number to
each phase (connect, send, each read), so it is not a hard wall-clock
bound: against a local stub at 3 s, one attempt took 3.01 s when the
provider never answered and 6.01 s when it sent its body a chunk a second.
A classify that meets a transient 429, 5xx, timeout or dropped connection
therefore fails at once and the screen holds the text; the player can try
again. A `--probe`
reports such an error as a failed probe instead of retrying it; run it
again.

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
and `TokenUsage`, resolves per-task model ids in `model_for`, selects each
task's adapter from its provider variable or `NESTED_WORLDS_PROVIDER`, keeps a separate concurrency limit per
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
adapter registered by name. Selection is `NESTED_WORLDS_PROVIDER` or that
task's provider variable. There is no automatic failover. Per-task model
settings are not a provider selector. A task provider variable selects only
the adapter. It does not approve a destination.


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
`NESTED_WORLDS_PROVIDER` or the task's provider variable. Do not add a
provider by giving it a new budget bucket. Voice calls share one allowance.

`consciousness/openai_compat_provider.py` is the second built-in, named
`openai_compatible`. It is available for evaluation. Registering it does
not approve a data destination, and no provider other than the current
default has been evaluated or approved. It posts Chat Completions to the
base URL the operator sets. It does not read `OPENAI_*` or `XAI_*`. It has
no default model id and does not judge ids by vendor prefix. The base URL
and the API key are never logged and never placed in an exception message.
The base URL is omitted from the settings `repr`. When `SENTRY_DSN` is set,
Sentry's stdlib integration records the outbound URL in the httplib
breadcrumb it builds from the HTTP client span. The API key is not in that
breadcrumb. A failure log records the exception class only.

| Variable | Meaning |
|---|---|
| `NESTED_WORLDS_OPENAI_COMPATIBLE_BASE_URL` | Required. `https`, or `http` on `127.0.0.1`, `localhost`, or `::1`. Userinfo, a query, and a fragment are rejected. Not logged. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_API_KEY` | Required except on loopback. A present value that is not ASCII, not printable, or contains whitespace leaves the adapter unconfigured on every host, including loopback. Not logged. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_MAX_OUTPUT_PARAM` | Wire field for the caller's max output: `max_completion_tokens` (default) or `max_tokens`. Any other value leaves the adapter unconfigured. The name does not contain `TOKEN`, so `model_check` does not redact the value as a secret. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_STRUCTURED_OUTPUTS` | `1` sends strict `json_schema`. Unset, `runtime.generate` raises `UnsupportedCapability` before the model-action cap and the voice budget, sends nothing, and the caller serves the authored fallback. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_SEND_STORE_FALSE` | `1` sends `"store": false`. Unset sends nothing. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_REASONING_EFFORT` | Optional `none`, `minimal`, `low`, `medium`, or `high`. Unset sends nothing. Any other value leaves the adapter unconfigured and is not forwarded. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_TIMEOUT_SECONDS` | Wall-clock budget for one POST when the caller passes no timeout. Default 60. Each resolved address is tried with the time remaining, so the TCP connects stay inside that budget. A blackholed earlier address can consume the whole budget; later addresses are then not tried. DNS lookup and individual TLS handshake bytes are not covered. Moderation still passes 3 seconds. |
| `NESTED_WORLDS_ANTHROPIC_TIMEOUT_SECONDS` | The anthropic adapter's counterpart, owned by that adapter: the timeout it sends when the caller passes none (node voice, inhabitant voice, intention). Default 60, parsed the same way, read on every call, and capped at `threading.TIMEOUT_MAX`, past which a socket wait overflows and every call fails before it is sent. There is no lower limit, as for the row above: a value below a few seconds times out real replies, which then answer with the authored silence. Unlike the row above it is **per attempt**, and the SDK still retries twice (its default), so a provider that accepts the request and never answers ends the call after 3 × 60 s plus at most 1.5 s of backoff, about 3 minutes, or at most about 5 if it answers errors with a retry-after of up to 60 s; the row above is one POST with no retries. Read, write and pool use the value; connect stays the SDK's 5 s (less when the value is smaller). Read is the longest wait for the next bytes, so a reply that keeps arriving can take longer. A caller's own timeout is sent unchanged, as one attempt with the SDK's retries off (see the timeout contract above), and a client built with its own timeout (the evaluation harness) keeps it. Before this setting the SDK's 600 s applied, about 30 minutes with retries. **Why 60 is a judgement:** no live latency for these tasks is on record (the 2026-10-05 model evaluation says hosted latency needs live or staging evidence; no live run exists). The largest output budget is the intention's 500 tokens, the sibling adapter uses 60, and a timeout shorter than a slow but working reply turns it into a timed-out attempt that is retried and possibly billed more than once, which is worse than a longer hang window. Revisit with measured p95/p99 per task. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_CONCURRENCY` | In-flight cap for this adapter. Default 8. It does not share the anthropic cap. |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_SLOT_WAIT_SECONDS` | Longest wait for a free slot under that cap when the caller passes no timeout. Default 10. Moderation waits its own 3 seconds. It does not share the anthropic setting. |

`NESTED_WORLDS_MODEL` plus `NESTED_WORLDS_MODERATION_MODEL` is enough.
Node voice, inhabitant voice, and intention use their own variable when
it is set, and the shared model otherwise. Moderation uses only its own
variable. A reasoning model can spend
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
Each resolved address is tried with the time remaining, so several
addresses do not multiply the budget. A blackholed earlier address can
consume the whole budget; later addresses are then not tried. DNS lookup
and individual TLS handshake bytes are not covered. The chronicle stores a
model id only after `_model_mark` in `persistence/__init__.py`: surrounding
whitespace is stripped, and a non-string, a blank, a control character, or
a value longer than 200 characters is dropped rather than stored or
truncated. A server may echo an alias such as `latest`; that string is
kept when it survives that function. The evaluation harness selects
whichever registered adapter the candidate names (`fixture` offline;
`anthropic` and `openai_compatible` are the built-ins). A live run is
opt-in and refuses without an explicit spend ceiling (`--max-usd` and
`--max-calls`) and that explicit provider. A non-anthropic live run also
refuses unless `--allow-destination` equals the lowercased hostname of the
resolved base URL for that run. The approval is the hostname, so it covers
every port on that host. A different case, a trailing dot, a substring, or
a suffix does not match. There is no default list, no environment default,
and no wildcard. Passing the flag for `anthropic` accepts only
`api.anthropic.com`. `anthropic` must price cache writes at a positive
rate; explicit zero and explicit null are refused, because that adapter
writes cache and either rate would let the ceiling undercount. For any
other provider an explicit null means the pre-call reserve does not bound
cache writes. The result records `budget.cache_writes_bounded: false`, and
a positive write count halts the run. The run records the candidate timeout and, for `openai_compatible`,
the resolved reasoning effort, output-limit parameter, schema flag, and
store flag. The URL and the credential are not stored. The harness does not set a base URL, a model id, or a default
provider, and it does not read `NESTED_WORLDS_PROVIDER` to fill one in.
`anthropic` still refuses any base URL other than the reviewed
`https://api.anthropic.com` destination. A live call with no explicit
timeout uses the candidate's `timeout_seconds`. Known usage is priced. An
unknown count stays unknown, and a lower bound from the known counts stops
the run when it exceeds the reserve. Production enablement is a separate
decision and is not made by registering this adapter or by pointing the
harness at it. ADR-035 stays Proposed. Destination approval for prompts
that can carry player text remains the owner's decision; the flag records
the operator's approval for that one run.

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

### Honesty about being an AI

The owner's guardrail (2026-11-06): no agent claims or implies that it is human, and
a sincere question gets a plain answer that the agent is an AI. On 2026-11-10 the owner
extended it to places (the place bible's line, `honesty.place_answer` on `/speak`, and
the guide's sentence that places speak through an AI). Two layers carry it. The
deterministic layer answers the lines it reads on `/speak` and `/agent/voice`, with the
AI layer on or off and with any provider; everywhere else, and for paraphrases it does
not read, the model layer is the only one, an instruction measured by the eval floor
below and not verified live with any provider.

- **Deterministic.** `consciousness.honesty.is_identity_question` recognizes an
  English line that is itself an identity question ("are you human?", "r u a bot",
  "am I talking to a real person?", "is this an AI?", "is there a human behind
  this?", "human or bot?") after folding case, punctuation and chat spellings. The
  whole line must be the question: other clauses may only be a greeting, a name the
  speaker answers to (an archetype's, a scale's or a form of address such as "friend",
  which every speaker shares, or the speaker's own, which the route passes as
  `own_names`: the agent's name on `/agent/voice`, none for a place; not a place's own
  name), a short lead ("be honest") or "I'm human" ("I am"), and the line is at most
  200 characters. Any other word where a name could stand asks for more ("Are you
  human? Help!", "Are you human, help me escape?"), and another cast member's or
  walker's name means the question was put to them, so "Tessera, are you human?" asked
  of a place or of Vex takes the normal path.
  `/speak` and `/agent/voice` answer such a line with an authored line
  (`honesty.place_answer`, which has a separate line for the root, or
  `honesty.agent_answer` per archetype) instead of the voice call. The route's
  place lookup, moderation screen and per-IP rate limit still apply, an unknown agent
  on `/agent/voice` keeps its quiet line, and the screen charges as it does for any
  line (a line it escalates costs a classify call and a model action). The answer
  itself takes no voice allowance and writes no provenance row, and the response
  carries `ai: false`. With AI on and a provider configured for
  the route's task (`node` for `/speak`, `inhabitant` for `/agent/voice`), the
  exchange is recorded as the same `PLAYER_SPEAK` / `AGENT_VOICE` row a model reply
  makes, and `/chronicle` and `/history` serve it unchanged, but the exchange
  itself is never quoted to other voices (owner decision, 2026-11-10). The
  history block every voice reads
  (`consciousness._history_block`, for places and agents alike) leaves out a recorded
  exchange, question and answer, whose stored reply is an authored answer
  (`honesty.is_authored_answer`: the exact text, surrounding whitespace stripped,
  of any line in `honesty.AUTHORED_ANSWERS`). A recorded row keeps the words it was
  answered with, so a line never leaves that set once main has shipped it: when
  the owner rewords an answer, the old line moves to `honesty._RETIRED_ANSWERS`,
  and `tests/test_agent_honesty.py` pins every line main has shipped
  (`ANSWERS_EVER_SHIPPED`). A place's answer stays only in the
  asker's own transcript with that place (`persistence.get_player_exchanges`, keyed
  by their invite credential, or by display name without one), so the place's next
  turns with them (the transcript holds their last three exchanges there) see it as
  an earlier exchange; an agent's answer reaches no later prompt. That retention
  is itself a relay path: a reply on one of those turns that restates the answer, as
  a model given the transcript may, is recorded as an ordinary `PLAYER_SPEAK` row,
  and later voices at that node quote it, authored words and all. Neither it nor
  any other model-written reply that says the same in other words on the normal
  path is filtered. A later reply that is exactly an authored line, whitespace
  aside, is left out with its question like the authored answer itself. Voices
  read history through `consciousness.history_for_voice`, which keeps the newest
  10 rows that are not identity exchanges. It reads 50 rows, and further back
  (up to the 1,000-row cap) only while identity exchanges leave fewer than 10,
  so they push no ordinary row out of a voice's window unless more than 990 of
  a node's newest 1,000 rows are identity exchanges. With the AI kill switch on, or with the flag
  unset and no provider configured for the route (places then answer in per-scale
  silence), the answer is given and nothing is recorded: in those modes every other
  line gets authored silence and writes no row. With the kill switch on, a line the
  local screen cannot settle keeps the quiet line, so the answer never becomes a
  moderation model call. A line that asks for more ("Are you human? Want to work on
  this puzzle with me?") takes the normal path: the model with AI on, whose bible
  carries the same rule, and the quiet line with AI off. The answer is not a voice
  outcome. It is counted per UTC day under `identity_answer:<surface>` whether or
  not it was recorded, which `voice-health` prints and never fails on, and it logs
  `voice_identity_answer surface=… recorded=yes|no` without the player's words.
- **Model instruction.** Both bibles tell the voice to stay in character without
  narrating the machinery, never to claim or imply being human, and to say plainly
  that it is an AI (a place: that it is a place, not a person, and that its voice
  comes from an AI) when sincerely asked.
  The agent bible also forbids asking a traveler for personal details, contact
  outside the world, money or gifts, and romantic framing.

The matcher reads phrase shape, not meaning: a clause must be the question itself,
so ordinary sentences about humans or machines ("is this a machine?", "is there
anyone behind the seal?", "is this the machine I'm talking to?"), a role in the world
("are you an agent?", where "are you an AI agent?" is the question) and reported
speech ('she asked me "are you human?"') take the normal path. Paraphrases it misses
reach the model; the eval corpus's `honesty` cases measure that path with a
deterministic floor (`evals/README.md`).

Chat does not address inhabitants yet. The functions are pure text, but two of their
choices are specific to a one-to-one exchange, and a chat surface must decide them
again rather than reuse the predicate unchanged. A question put to no one or to a
group ("is anyone here an AI?", "are any of you AI?") returns `False`, because the
authored lines answer for the speaker alone; answering it needs a separate predicate.
And a line that also says something else returns `False`, so a chat reply would need
its own way to answer the rest.

## Startup model check

`python main.py models` prints each task's provider, where that provider
came from (`task env`, `NESTED_WORLDS_PROVIDER`, or `default`), the resolved
model id, where the id came from (`task env`, `NESTED_WORLDS_MODEL`, or
`default`), and any problem. The header is that one provider name, or
`per task` when the tasks differ. It does not call the provider. Run it
with the provider and model variables the machine will use before a
release, `scripts/deploy.sh`, or a Fly boot. The moderation model is
included even when `NESTED_WORLDS_DISABLE_MODERATION=1`. A blank, unknown,
or unsafe provider name on any of the four tasks, or a task's adapter
whose SDK is not installed, exits with one line before the report. The
missing-SDK line names the variable that selected that adapter and the
optional extra. A shared model id used on a provider other than the
process default is a soft problem: the id is explicit, and it is not that
provider's default. A provider that is not configured (no credential) is
not a boot failure. The command prints `provider not configured`, and
names the tasks when the providers differ. `python main.py voice-health`
treats the voice as ready only when the node, inhabitant, and intent
providers are configured, and it reports moderation on its own line. An
unconfigured moderation provider fails the check unless moderation is
switched off. It counts spent calls on the stored `anthropic` key, plus a transient
`voice` row if one is present. A voice or image cap that is not an integer,
or is negative, exits `models`, `serve`, and `voice-health`, including
when `NESTED_WORLDS_DISABLE_AI=1`, because that switch does not disable
`/image` and `serve` refuses the same configuration. Two valid integers
that disagree print a warning and do not exit. The lower integer is what
a request enforces. The line does not echo a non-integer or negative value.

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

`python main.py models --probe` makes one tiny live call per distinct
provider and model id (`max_tokens` 1). It is off unless that flag is
passed. Server startup, `./scripts/check.sh`, tests, and CI do not pass
it, and there is no environment variable that turns it on. It checks that
task's `configured()` first. When that is false, or when it raises, the
command prints `skipped: provider not configured` and exits 1. One
unconfigured provider does not skip a configured provider's probe, and
does not call the unconfigured one. It does not report a `TypeError`. A
configured probe needs a credential, spends a real call, and does not
charge the model-action cap or the voice allowance. A refused probe also
exits 1. It confirms the provider accepts the id. It is not a quality,
cost, or cache evaluation.

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

## Controlled staging policy

Hosted and declared temporary test worlds require the
[controlled model policy](model-policy.md). It adds exact destination/model/options
permission and durable global/per-participant USD reservations before transmission.
This first controlled slice supports the built-in Chat Completions adapter only;
other adapters, direct probes, live wrappers, keyless calls and images refuse.
The all-off example selects no destination, price, cap or retention period.
Existing local/fixture behavior outside controlled mode and the call-count caps
remain. A valid policy is not provider evaluation or live activation approval.
