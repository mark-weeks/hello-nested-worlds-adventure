# ADR-035: Second text adapter — OpenAI-compatible Chat Completions

**Status:** Proposed, 2026-11-01. Written from the second-text-adapter plan
that Mark Weeks, the sole maintainer, approved the same day. **Not ratified.** This
document introduces no runtime behavior, no registered adapter, no migration,
and no write path. The open decisions below stay with the owner. Citing this
record authorizes nothing: no destination for player text, no spend, no
budget rename, and no production enablement.

---

## Context

[ADR-034](ADR-034-provider-and-model-optionality.md) makes provider and model
choice evidence-based. World identity, continuity, and player autonomy stay
independent of any vendor. The four text tasks — node voice, inhabitant
voice, intention interpretation, and moderation — already share one
task-facing boundary, `TextProvider` in `consciousness/runtime.py`. Prompts
and world rules stay in application code. The adapter owns transport,
credentials, request and response shape, and usage accounting.

At `38fbe6e` the registry's `_BUILTINS` contains one name, `anthropic`.
`NESTED_WORLDS_PROVIDER` selects it; unset means that name. There is no
failover and no per-task provider. ADR-034's revisit clause says to add the
smallest necessary adapter when a comparison needs one. Choosing the dialect,
the transport, the configuration, and the accounting posture is the decision
this record proposes. It does so before any code, so review can reject the
shape while the tree is still unchanged.

The coverage the plan asked for is one client that an operator can point at
xAI, OpenAI, OpenRouter, vLLM, Ollama, and Gemini's OpenAI-compatibility
endpoint, for evaluation. A Gemini-native adapter waits until an evaluation
says the native surface is worth a second client.

Official documentation read on 2026-11-01 (America/Los_Angeles), with no live
call, is the evidence for the wire facts below. "Unverified" means that read
did not confirm the claim on an official page, or that no live call has
measured it. The [Unverified](#unverified) list is binding on how this record
may be quoted.

Documented that day:

- Chat Completions is the one request format every listed target documents.
  xAI's Chat Completions reference (updated 2026-10-20) calls that API legacy
  and says new integrations should use Responses; a comparison page marks it
  Deprecated. OpenAI's migrate-to-Responses guide says Chat Completions remains
  supported and recommends Responses for new projects. Gemini's
  OpenAI-compatibility page documents Chat Completions, documents no
  Responses support, and labels OpenAI-library support beta. vLLM and Ollama
  document Chat Completions. Ollama also documents a non-stateful
  `/v1/responses`. vLLM's Responses support was not verified.
- OpenAI and xAI document `response_format` of type `json_schema`. OpenAI's
  structured-outputs guide requires `strict: true`, every field in
  `required`, and `additionalProperties: false`. xAI's structured-outputs
  page says output is guaranteed to match the schema for supported features.
  OpenRouter documents structured outputs for select models, decided per
  serving endpoint. Gemini's compatibility page documents
  `chat.completions.parse` with `response_format`.
- OpenAI documents that `max_completion_tokens` includes reasoning tokens,
  that `reasoning_effort` defaults to `medium`, and that `max_tokens` is
  deprecated and does not work with o-series. xAI documents that
  `max_completion_tokens` applies to visible output tokens and not to
  reasoning, and its example counts `completion_tokens` apart from
  `reasoning_tokens` (`total_tokens` = prompt + completion + reasoning).
- OpenAI documents `finish_reason` values `stop`, `length`, `tool_calls`,
  `content_filter`, and `function_call`, plus `message.refusal`. xAI
  documents `stop`, `length`, and `end_turn`, plus `message.refusal`.
- Ollama's compatibility page lists `max_tokens`. vLLM's structured-outputs
  page was read; the token-limit parameter name on vLLM was not verified.
- Gemini's image endpoint says unlisted parameters are silently ignored.
  Whether the chat compatibility endpoint does the same is unverified.
  Whether any of these servers reject a `store` field is unverified.

Pricing, which model is best for each task, and xAI's cache-write billing
were not used and are unverified. Model ids that appear in vendor examples
are examples. This record adopts none of them.

What the current code already does, and what this record keeps:

- `TextProvider.generate` honors a requested schema or raises. It never
  silently drops one (`consciousness/runtime.py`, the protocol docstring).
  It does not receive the task name.
- An adapter with no `default_model` supplies no id. `model_for` then
  returns an empty id for `source=default`, `python main.py models` reports
  a hard problem, and `python main.py serve` exits before it opens a port
  (`consciousness/model_check.py`).
- `runtime.generate` calls `guard.consume_anthropic` whenever `voice_budget`
  is set, after the model-action cap and before the provider. The persisted
  bucket is `"anthropic"` (`server/guard.py`, `ANTHROPIC_BUCKET`).
  `docs/development/agent-runtime.md` already says those names stay, and
  that a provider switch must not replenish an allowance. The moderation
  bucket and the model-action cap are already neutral names.
- `moderation_outcome` (`consciousness/__init__.py`) returns allow or block
  only when `complete` is true, `finish_reason` is not `"length"`, and the
  stripped text is exactly one verdict. Anything else is undecided.
  `_MODERATION_MAX_TOKENS` is 32 and `_MODERATION_TIMEOUT_SECONDS` is 3.0.
  The screen holds shared text on undecided and on any exception
  ([ADR-004](ADR-004-day-one-data-policy.md) §2, amended 2026-10-25).
- Intention interpretation (`consciousness/interventions.py`) checks
  `response.complete`, parses JSON, checks exact keys, then
  `normalize_steps`. `server/intervention_api.py` `_propose` catches
  `Exception` and answers the authored unsettled line.

## Decision

The proposed adapter is one stdlib HTTP client for OpenAI-compatible Chat
Completions. The operator sets the base URL. The same client can then be
pointed at the endpoints named in Context, for evaluation. Registration,
tests, and operator docs are a later change. This record is the contract
that change is reviewed against.

### 1. Name, transport, and dialect

- Registry name `openai_compatible`. That string is the provenance value and
  the stem of `NESTED_WORLDS_OPENAI_COMPATIBLE_CONCURRENCY`. The name matches
  `consciousness/runtime.py`'s provider-name pattern.
- No `sdk_module`. Transport is `urllib.request`, the library the fal path
  already uses. `runtime.installation_error` returns None when `sdk_module`
  is unset, so no optional extra is required. The module would live at
  `consciousness/openai_compat_provider.py`. This record does not add it.
- One POST to `<base>/chat/completions`, `Authorization: Bearer <key>`,
  **zero retries**. The number passed to `urlopen` is a socket timeout on
  each blocking operation, not a deadline for the whole call. `http.client`
  says a socket timeout does not fire while data keeps arriving inside
  every window. When the caller passes none, the adapter default in the
  table below is that per-operation timeout. Moderation passes 3.0 seconds,
  so each blocking operation on that call uses 3.0 seconds. That is not a
  3.0 second cap on the classification.
- The wire format is confined to two functions, `build_request` and
  `parse_response`. If the owner later chooses a Responses dialect
  ([open decision](#open-decisions) 4), that is where it would go, without
  a `TextProvider` change. This record does not choose it.
- Chat Completions is the dialect because it is the one format every target
  in Context documents. Responses is the forward path at xAI and OpenAI. It
  is not the intersection.

### 2. No `TextProvider` change

`generate` keeps its current parameters. It does not learn which task it is
serving, so this adapter cannot send a different reasoning effort per task.
That would be a protocol change and is an open decision, not this one.
`model_id_validator` returns None. `model_check`'s structural rules still
apply: empty text, whitespace, control characters, and an id longer than 256
characters fail. The adapter does not judge ids by prefix. A gateway can
serve any id, which is the same reason the anthropic adapter widens its
check when `ANTHROPIC_BASE_URL` is set. `cache_reference_tokens` returns
None, so the existing unknown-cache warning fires. No sampling fields are
sent. The anthropic adapter sends none either.

### 3. No default model ids

The adapter omits `default_model`. Startup refuses until the operator has
set every task: `NESTED_WORLDS_MODEL` plus `NESTED_WORLDS_MODERATION_MODEL`,
or each of `NESTED_WORLDS_NODE_MODEL`, `NESTED_WORLDS_INHABITANT_MODEL`,
`NESTED_WORLDS_INTENT_MODEL`, and `NESTED_WORLDS_MODERATION_MODEL`.
Moderation does not inherit the shared voice id. The refusal is the existing
hard problem, "is unset and provider openai_compatible has no default
model." No id is endorsed before evidence. Vendor documentation examples
are not defaults.

### 4. Configuration

Every name below is new. None renames an existing variable. The adapter
reads none of `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `XAI_API_KEY`, or any
other vendor variable. A key is sent only to the base URL the operator set
for this adapter. The opener is built with `urllib.request.ProxyHandler({})`
and a redirect handler that replaces the default. `ProxyHandler({})` does
not call `getproxies()`, so `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` are
not used unless a later decision adds them. `build_opener` still installs
`HTTPRedirectHandler` when the only extra handler is `ProxyHandler`
(`urllib/request.py`, `build_opener`). A subclass of
`HTTPRedirectHandler` is what skips that default. The default follows a
POST 301, 302, or 303 as GET while copying `req.headers`, including
`Authorization` (`redirect_request`). A POST 307 or 308 raises `HTTPError`
instead. The adapter's opener follows no redirects: any 3xx raises
`ProviderHTTPError` with the status code only, so `Authorization` never
reaches a host other than the base URL's.

| Variable | Meaning | Default |
|---|---|---|
| `NESTED_WORLDS_PROVIDER=openai_compatible` | Existing selector | `anthropic` |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_BASE_URL` | Endpoint the operator chooses. `https://<host>/v1` is a shape, not a destination (Open decision 1) | required |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_API_KEY` | Bearer key. Redacted by `model_check._SECRET_NAME` | required, except on loopback |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_MAX_OUTPUT_PARAM` | Wire field for the caller's `max_tokens`: `max_completion_tokens` or `max_tokens` | `max_completion_tokens` |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_STRUCTURED_OUTPUTS` | `1` when the endpoint enforces `json_schema` | unset (off) |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_SEND_STORE_FALSE` | `1` sends `"store": false` | unset (do not send) |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_REASONING_EFFORT` | Optional pass-through (`none`, `minimal`, `low`, and the other values the operator sets). Unset sends nothing | unset |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_TIMEOUT_SECONDS` | Per-operation socket timeout when the caller passes none. Voice and intention pass none. Moderation passes 3.0, which bounds each blocking operation, not the whole call | 60 |
| `NESTED_WORLDS_OPENAI_COMPATIBLE_CONCURRENCY` | Already derived by the per-provider concurrency rule | 8 |

Base URL policy: `https` only, except `http` on `127.0.0.1`, `localhost`, or
`::1`. Userinfo, query, and fragment are rejected. The URL is never logged
and never echoed. Its name contains neither `KEY` nor `TOKEN`, so
`model_check._secret_values` will not redact it. That is a reason to keep
it out of logs, not a reason to treat it as public. A trailing slash is
joined so a path such as Gemini's `/v1beta/openai/` still ends at
`/chat/completions`. A loopback base URL may omit the key. Any other host
without a key is not configured.

`MAX_OUTPUT_PARAM` defaults to `max_completion_tokens` because OpenAI and
xAI document that name. Ollama's parameter list shows `max_tokens`, so the
operator sets the name for that host. Whether vLLM accepts
`max_completion_tokens` is unverified; the setting exists so the operator
can match the server without a code change. The environment name does not
contain `TOKEN`. `model_check._SECRET_NAME` is
`(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)`, case-insensitive, and
`_secret_values` collects any value of length at least 8 whose variable
name matches. `max_completion_tokens` is 21 characters, so a name containing
`TOKEN` would treat that field name as a secret: the models report would
redact it, and `_embeds_secret` would hard-fail a model id that contains
it. `MAX_OUTPUT_PARAM` does not match the regex. `API_KEY` does, which is
why the bearer key is redacted.

`SEND_STORE_FALSE` defaults off. OpenAI documents `"store": false` on Chat
Completions. Sending it only when the operator opts in avoids a field some
servers might reject. Whether they reject it is unverified.

### 5. Request shape

`build_request` is pure.

- System blocks become one leading `{"role": "system"}` message, in order,
  joined by `\n\n`. The cacheable bible stays first, so the shared prefix
  is stable for implicit caching. Some chat templates reject more than one
  system message; that rejection is unverified per server, and one message
  is the portable form.
- Caller messages pass through in order, roles unchanged.
- The max-token field name is `MAX_OUTPUT_PARAM`. The value is the
  caller's `max_tokens`. The request does not send `n` or `stream`.
- When `json_schema` is not None **and** structured outputs are declared on,
  send `response_format` as
  `{"type": "json_schema", "json_schema": {"name": "enfolded_output", "schema": <schema>, "strict": true}}`.
  When `json_schema` is not None and structured outputs are off, raise
  `UnsupportedCapability` and send nothing. The schema is never dropped.
  Intention's caller already catches `Exception` and answers the authored
  unsettled line (`server/intervention_api.py`), which is the fallback this
  decision means. Application validators in `consciousness/interventions.py`
  still decide a body that parses.
- `"store": false` only when that setting is on. The request never carries
  `user`, `safety_identifier`, or `prompt_cache_key` derived from a player
  key.
- No temperature and no other sampling fields.

### 6. Token accounting

`parse_response` fills `TokenUsage` for the harness and for the existing
usage log. Missing means unknown, which is `None`, never a fabricated `0`.

- `cache_read_tokens` is `prompt_tokens_details.cached_tokens`, or None when
  the field is absent.
- `cache_write_tokens` is `prompt_tokens_details.cache_write_tokens` when
  that field is present, otherwise None. OpenAI's usage object documents
  the field. xAI cache-write billing, and whether xAI reports a write
  field, are unverified. Unknown stays unknown.
- `input_tokens` is `prompt_tokens − cached − (cache_write or 0)`. That is
  ordinary input, the same meaning Anthropic's `input_tokens` has when cache
  reads and writes are reported separately. The result is None when it
  would be negative or when `prompt_tokens` is missing.
- `output_tokens` is `total_tokens − prompt_tokens` when both are present,
  and None otherwise. There is no fallback to `completion_tokens`. OpenAI's
  documented `completion_tokens` includes reasoning. xAI's documented
  example excludes it and puts reasoning in the total. The difference of
  the two totals counts reasoning in both of those published examples, and
  a `completion_tokens` fallback would under-count on the xAI shape.
  Under-counting is the worse error, so a missing total stays unknown.
  It is a reading of the examples, not a live measurement.
- `resolved_model` is the `model` string the body echoes.
  `provider` is `openai_compatible`. Provenance does not store that echo
  verbatim. `_model_mark` (`persistence/__init__.py`) strips the string and
  drops it when it is not a string, is blank after stripping, is longer
  than 200 characters, or contains a character whose code point is below
  32. A dropped value is absence, not a shortened id. `model_check` still
  allows an id of up to 256 characters, so an echo of 201 to 256 characters
  can pass startup and then be omitted from `mutation_model_provenance`.
  An alias such as `"latest"` that passes those checks is stored as the
  stripped text. xAI's Responses example echoes `"model": "latest"`;
  whether Chat Completions does the same was not a separate check. The
  side table is append-only with the chronicle row it describes. This
  record adds no write path.

The adapter does not read a provider-reported money field. Call caps are
counts. Identical counts are not identical spend. Exposing a reported cost
would change `Completion` and is an open decision.

### 7. Fail-closed moderation

Shared text is published only after the existing screen allows it.
`moderation_outcome` allows only a complete reply whose text is exactly one
verdict. The adapter's mapping is therefore the safety contract for this
provider. Only a clean `stop` is complete: `choices` has exactly one
element, that element's `content` is a string containing non-whitespace
text, and `refusal` is null or absent. Empty or whitespace-only content
is incomplete and carries no text. The parser reads `choices[0]` only.
The request never sends `n` or `stream`. More than one choice, or a
`content` that is not a string (including a parts array), raises
`MalformedProviderResponse`. A present, non-null `refusal` is a refusal
before content is read. A missing `refusal` counts as null.

| Wire result | `Completion` | Screen |
|---|---|---|
| `finish_reason` `"stop"`, exactly one choice, `content` a string with non-whitespace text, `refusal` null or absent | `complete=True`, `finish_reason="complete"`, text is that string | verdict text decides |
| `"stop"` with `content` `""` or whitespace only | `complete=False`, text None | undecided, held |
| `"length"` | `complete=False`, `finish_reason="length"` | undecided, held |
| `"content_filter"` | `complete=False`, `finish_reason="filtered"`, text None | held |
| `message.refusal` present and not null, any finish | `complete=False`, `finish_reason="refusal"`, text None | held |
| `"tool_calls"` or `"function_call"` | `complete=False`, `finish_reason="tool"` | held |
| `"end_turn"` | `complete=False`, `finish_reason="unknown"` | held |
| null, missing, or any other finish | `complete=False`, `finish_reason="unknown"` | held |
| `choices` missing or empty, or `content` null, with at most one choice | text None | voice raises `NoTextError`; moderation holds |
| more than one choice, or `content` not a string | raise `MalformedProviderResponse` | screen's `except` holds |
| HTTP non-2xx, HTTP 200 with an `error` object, non-JSON, timeout, connection error, any 3xx | raise an adapter exception, `from None`, fixed message | screen's `except` holds |
| Unconfigured (no key, or no URL) | `configured()` is false; classify still raises at call time | held. `/speak` serves the authored fallback and does not charge the voice budget |

`end_turn` stays incomplete on this adapter. The anthropic adapter treats
its own `stop_reason` `end_turn` as complete. That is a different wire
vocabulary. xAI documents `end_turn` as a Chat Completions finish value
beside `stop` and `length`. Whether a non-streaming xAI chat response
actually returns `end_turn` is unverified. Mapping it to complete would
publish shared text on a finish this screen has not seen live. Hold is the
contract until that live check exists.

Adapter exceptions (`ProviderHTTPError` with the status code only,
`ProviderTimeout`, `MalformedProviderResponse`, `UnsupportedCapability`)
are raised `from None` with a fixed message. The message carries neither
the response body, nor the key, nor the URL, nor the prompt, nor any
upstream text. `from None` matters because a chained urllib error includes
the target URL, and two loggers print the chain: `server/observability.py`
`capture_exception` calls `_log.exception` when Sentry is off, and
`server/heartbeat.py` has several `_log.exception` calls.
`failure_summary` (`consciousness/runtime.py`) returns the class name
only, except `NoTextError`, whose message is the normalized completion
metadata. The dispatch catch-all in `server/handlers.py` `_fail_dispatch`
still logs that traceback when Sentry is off. That is the #132 follow-up
and is not this adapter.

Vendor moderation endpoints, including a `moderation` parameter on Chat
Completions, are a separate decision. The classifier prompt is unchanged.

### 8. Budget bucket unchanged

`runtime.generate` keeps calling `guard.consume_anthropic` for node voice,
inhabitant voice, and intention, whichever provider is selected. The bucket
`"anthropic"` and `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` and
`NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` are the voice-call budget for
every text provider. This record adds no alias and no migration of counters.
The implementation that follows it changes the `generate` docstring from
"reserves an `anthropic` call" to a sentence that names one voice call in
that existing bucket. The docstring change is wording. The bucket stays.

Concurrency is already per provider. `openai_compatible` uses its own cap
and does not consume the anthropic cap. The moderation bucket and the
model-action cap stay as they are.

`docs/infrastructure/fly-deployment.md` stays as written until a production
destination is approved. Merge of this record enables no new data
destination ([ADR-034](ADR-034-provider-and-model-optionality.md) §5).

## Open decisions

These stay with Mark Weeks. This record does not choose them.

1. **Which destinations may receive player text, and in what order.**
   ADR-034 §5 requires a scoped decision for each new data destination. The
   list held for that decision is xAI, OpenAI, Google/Gemini, open-weight
   self-hosted (vLLM or Ollama on the operator's host), and OpenRouter.
   OpenRouter is a broker: the text reaches whichever upstream it selects,
   so it is its own destination. The plan's suggestion, which this record
   does not adopt, is synthetic-only evaluation first — the harness already
   has `data_authorization: "synthetic-only"` — and a separate production
   decision per destination afterwards.
2. **The spend ceiling** for any live evaluation (`--max-usd`, `--max-calls`).
3. **Whether to rename or alias the `anthropic` voice bucket.** Nothing here
   forces a rename. A later change could add `NESTED_WORLDS_VOICE_DAILY_CALLS`
   as a preferred name for the same bucket. That is a separate decision.
4. **Later Responses support, and vendor-named profiles** (`xai`, `openai`)
   so provenance and concurrency name the vendor rather than
   `openai_compatible`. Both stay optional. The wire format is confined to
   two functions. If the owner adds Responses, that is where it would go.
   This record does not schedule that work. A native
   Gemini adapter, a per-task `reasoning_effort` (which needs `TextProvider`
   to learn the task), and a provider-reported cost on `Completion` are the
   same kind of later work, and they are not decided here.
5. **Whether to ratify this record.** Until it is accepted, it is a proposal.
   Acceptance would still leave items 1–4 open, and would still require a
   separate implementation review. Acceptance is not production enablement.

## Trade-offs accepted

These are the consequences of building the adapter this way. They bind only
if the record is ratified and an implementation follows it.

- **Reasoning models can consume moderation's 32-token cap.** On OpenAI,
  `max_completion_tokens` includes reasoning, and `reasoning_effort`
  defaults to `medium` when the request omits it. This adapter omits it
  unless the operator sets `NESTED_WORLDS_OPENAI_COMPATIBLE_REASONING_EFFORT`.
  A reasoning model can spend the 32 tokens, the probe's 1 token, or
  voice's 200–256 tokens on reasoning and stop for length. Length is
  undecided, so every ambiguous line is held. That is fail-closed, and it
  can make the provider unusable for play. The operator's mitigations are a
  non-reasoning model, or an effort value the endpoint honors (`none` or
  `minimal` where that endpoint documents them). Whether a given model does
  this is a live question. Fixtures cannot answer it.
- **xAI reasoning tokens are not capped by the max-token parameter.** xAI's
  Chat Completions documentation says `max_completion_tokens` applies to
  visible output and not to reasoning. A reservation based on the caller's
  `max_tokens` is therefore not an upper bound on tokens, or on spend, for
  that route. The eval harness has to treat that as unbounded or halt. This
  record does not add a dollar cap. The documentation claim was read on
  2026-11-01 and was not confirmed with a live call.
- **Provider safety filters can hold benign fiction.** Gemini documents
  block reasons such as `SAFETY` and `PROHIBITED_CONTENT`. OpenAI documents
  `content_filter`. This mapping turns those into holds. ADR-004 requires
  the hold. A filter that fires on fantasy violence makes holds the common
  case, which is fail-closed and bad for play. Only a live evaluation on an
  approved destination can measure the rate. The classifier prompt already
  says fantasy violence is ALLOW. That prompt is not a provider-side filter.
- **Some servers can ignore `json_schema`.** Strict schema is an explicit
  opt-in (`NESTED_WORLDS_OPENAI_COMPATIBLE_STRUCTURED_OUTPUTS=1`). With the
  flag off, a caller that passes a schema gets `UnsupportedCapability` and
  the player gets the authored unsettled line, rather than a request that
  quietly dropped the constraint. With the flag on, a server that accepts
  the field and ignores it can still return malformed JSON. The application
  validators already reject that body. Gemini-compat's handling of unknown
  fields is unverified, including whether chat silently ignores them the
  way the image endpoint documents.
- **The dialect xAI calls legacy is the one this adapter speaks.** Drift is
  the cost of one client that every listed target documents. The mitigation
  is the two-function boundary and the revisit trigger below, not a second
  dialect in this record.
- **The name `openai_compatible` hides the vendor** in provenance and in the
  concurrency setting. Vendor-named profiles are an open decision. Until
  one exists, the stored provider string is the adapter name, and the
  stored model id is what `_model_mark` keeps of the server's echo.
- **The voice bucket keeps a vendor name.** A provider switch must not
  replenish an allowance. `docs/development/agent-runtime.md` says the
  `anthropic` bucket and `NESTED_WORLDS_ANTHROPIC_*` names stay, and that
  they must not be renamed or reset to make the interface look neutral or
  to replenish an allowance. It does not call that bucket the voice budget
  for every text provider. This record is the place that says the same
  bucket counts those calls on whichever adapter is selected. Renaming it
  is open. Reusing it is the point.
- **`cache_write_tokens` stays None when the server omits it.** A meter that
  treats missing usage as unknown cost cannot pass a max-cost gate on that
  route. Under-counting would be the worse error. xAI cache-write billing
  is unverified.
- **Zero retries and a 60-second per-operation socket timeout** when the
  caller passes none. Moderation passes 3.0, so each blocking operation on
  that call uses 3.0 seconds. Neither number is a deadline for the whole
  response. The Anthropic SDK's default retry count and timeout were not
  re-verified for this record, so no comparison with them is stated.
- **No live quality, latency, or cost evidence is claimed.** Local contract
  tests, when they exist, will show mechanics. ADR-034 already says only a
  representative live evaluation establishes quality, caching, latency,
  reliability, or cost. This record does not run one.

## Revisit when

- The owner approves a destination for synthetic evaluation, or for
  production. Each approval is its own decision. This clause does not grant
  it.
- Chat Completions drift at a destination the owner has actually chosen, or
  Responses becomes the only format that destination still documents. If
  the owner adds Responses (Open decision 4), the isolation point is
  `build_request` and `parse_response`. This clause does not choose that
  addition. Gemini-compat documents no Responses support. vLLM's Responses
  support is unverified.
- An evaluation selects Gemini and the native Interactions API
  (`client.interactions.create`, the surface Google's structured-output page
  documented on 2026-11-01) is stable enough to justify its own adapter.
  Until then Gemini stays reachable, for evaluation only, through the
  compatibility endpoint Google labels beta.
- A live run shows reasoning tokens consuming the 32-token moderation cap,
  or a provider safety filter holding benign fantasy often enough that play
  stops. The mitigation is model choice, the effort setting, or leaving
  that destination.
- A dated official source states a destination's cache-write rule, and None
  is then the wrong accounting for that route.
- The owner decides the bucket rename, vendor-named profiles, per-task
  reasoning effort, or a reported-cost field.

## Rejected alternatives

- **A Gemini-native adapter first.** One vendor, and a native surface that
  on 2026-11-01 was the Interactions API and still moving. Gemini remains
  reachable for evaluation through the beta compatibility endpoint. Native
  waits on an evaluation, which is an open follow-up, not this decision.
- **A separate adapter per vendor** (`xai`, `openai`, and the rest) as the
  first shape. That is the many-adapters cost ADR-034 already rejected,
  spent before any destination has shown value. Vendor-named profiles remain
  an open later option. They are not this adapter.
- **Responses first.** The forward path at xAI and OpenAI. It drops
  Gemini-compat, which documents no Responses support, and it leaves vLLM
  unverified. Chat Completions is the only format every target in this
  record documents. The wire format sits in two functions. If the owner
  adds Responses, that is the isolation point. Adding it is not decided
  here.
- **The `openai` SDK instead of stdlib.** The SDK reads `OPENAI_API_KEY` and
  `OPENAI_BASE_URL` from the environment implicitly, so a key can leave for
  a host the operator did not name on this adapter. It also adds version
  churn and an optional extra. `urllib.request` is already in the process,
  and a test can replace the transport without a socket. The default
  opener is not that boundary by itself: it follows some redirects and
  reads proxy variables. This adapter's opener closes both, as §4 states.
- **A universal router.** Rejected by ADR-034. This record proposes one
  bounded adapter, not a router.
- **Implicit vendor environment variables.** Rejected. Configuration is the
  `NESTED_WORLDS_OPENAI_COMPATIBLE_*` names only.
- **Default model ids taken from vendor examples.** Pricing and the best id
  per task are unverified. An id in a documentation example is not a
  selection. Startup refuses until the operator sets the four tasks.
- **Dropping `json_schema` when support is uncertain.** `TextProvider`
  forbids a silent drop. The adapter raises, and the player reads the
  authored unsettled line.
- **Renaming the `anthropic` budget bucket in the same change.** A provider
  switch would replenish allowances if the old bucket were abandoned. The
  rename stays open.
- **Treating xAI's `end_turn` as complete** because the anthropic adapter
  treats its own `end_turn` as complete. The two strings are not the same
  contract. Shared text stays held.

## Unverified

Quoted from the 2026-11-01 plan. None of these are findings of this record,
and none of them are decided.

- Any pricing.
- Which current model id is best for each task. Documentation examples are
  not endorsements and are not defaults.
- xAI cache-write billing, and whether xAI reports a cache-write field.
- Whether xAI's non-streaming Chat Completions response ever returns
  `end_turn`.
- Whether vLLM accepts `max_completion_tokens`, and whether vLLM accepts
  Responses `text.format`.
- Gemini-compat chat's handling of unknown fields.
- Whether any target rejects a `store` field.
- The Anthropic SDK's default retry count and timeout.
- Anything a live API would show. No live call was made for the plan or for
  this record.
