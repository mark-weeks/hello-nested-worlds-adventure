# Chat Completions endpoint check (item 24)

Desk check read on 2026-11-20. No API key was used, no request was sent, and
no provider account was changed. Anything that needs a live response is marked
unverified. This record does not fill
[the watch example](../../config/model-policy.watch.example.json), sign a
data-use note, or change ADR-035's Status. The ids and dollar figures below
are desk candidates. They are not checked-in policy values.

The two candidates are the ones in owner decision O3: the incumbent provider's
Chat Completions-compatible endpoint, and OpenAI's own Chat Completions
endpoint. Both are judged against the request and usage contract in
`consciousness/openai_compat_provider.py`, which is the only transport
controlled mode will dispatch.

## What the adapter requires

`build_request` posts JSON with `model`, `messages`, and one output-limit
field. The output-limit name is `max_completion_tokens` unless
`NESTED_WORLDS_OPENAI_COMPATIBLE_MAX_OUTPUT_PARAM` is `max_tokens`. When
structured outputs are on and the caller passes a schema, the body sets
`response_format` to `{ "type": "json_schema", "json_schema": { "name",
"schema", "strict": true } }`. Intention and moderation always pass a schema.
When `send_store_false` is on, the body sets `store` to false. The policy
refuses a route unless that option is true. `reasoning_effort` is sent only
when the operator sets it.

`_usage_and_evidence` prices a call only when `prompt_tokens`, a derivable
output count, and `prompt_tokens_details.cached_tokens` are all present.
`cached_tokens` may be zero. If `prompt_tokens_details` is missing or empty,
`cached_tokens` is absent, ordinary input stays unknown, and
`consciousness/model_policy.py` `settlement` returns no cost. The reservation
is then kept and the row does not become `settled`. That is requirement 4
below. A smaller model does not change it.

The response `model` string is kept only when it is one of the route's
`resolved_models`. The headers this adapter sends are `Content-Type`,
`Accept`, and `Authorization: Bearer`. It does not send a workspace header.

The five requirements, from O3:

1. Structured outputs for intention and moderation, as the `response_format`
   shape above.
2. `store: false` honored, not merely accepted.
3. The max-tokens parameter the adapter sends.
4. Usage that includes prompt, completion, and cached-token counts, so a call
   can settle.
5. A reported `model` string that can be listed in `resolved_models`.

## Candidate A — incumbent compatibility endpoint

Pages read:

- [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk),
  which documents base URL `https://api.anthropic.com/v1/`. The adapter joins
  `/chat/completions`, so the policy endpoint would be
  `https://api.anthropic.com/v1/chat/completions`.
- [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)
  and [pricing](https://platform.claude.com/docs/en/about-claude/pricing).
- [Claude Haiku 4.5](https://platform.claude.com/docs/en/models/haiku-4-5/overview).
- [API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention).

The compatibility page says the layer is primarily for testing and comparing
model capabilities and is not considered a long-term or production-ready
solution. That sentence is on the page. It is not a live measurement.

| Requirement | Desk result |
| --- | --- |
| 1. Structured outputs | The page says `response_format` accepts only `json_schema` with `strict: true`, and that the structured-outputs JSON Schema limitations apply. That is the shape `build_request` sends. Function-calling `strict` is a different field, and the page says that one is ignored. Intention and moderation do not use function tools. **Documented request shape: passes. Live conformance: unverified.** |
| 2. `store: false` | The request-field table says `store` is **Ignored**. The adapter can send the field. The page does not say the server honors it. **Fails as a control the server honors. Unverified what a live account stores.** |
| 3. Max-tokens parameter | Both `max_tokens` and `max_completion_tokens` are listed as fully supported. The adapter's unset default is `max_completion_tokens`. **Documented: passes. Live: unverified.** |
| 4. Usage counts | `usage.prompt_tokens`, `usage.completion_tokens`, and `usage.total_tokens` are fully supported. `usage.prompt_tokens_details` is **Always empty**. With an empty object, `cached_tokens` is absent, and `settlement` cannot price the call. **Fails on the published page. A live body was not read, so the page could differ from a response. Unverified live.** |
| 5. Reported model | The response field `model` is fully supported. **The field exists on the page. Which string comes back for an alias is unverified.** |

The same page says prompt caching is not supported on this layer, and that an
API key which is not scoped to a workspace must also send
`anthropic-workspace-id`. This adapter does not send that header. Whether a
watch key is scoped, and whether an unscoped key is rejected, is unverified.

Requirement 4 fails for every model on this endpoint. O3 says a smaller model
does not cure a missing `cached_tokens` count. This candidate does not pass
the desk checks.

### Models this endpoint would pin, if it could settle

These names are what the pages and the `anthropic` adapter list. They are not
written into the policy file. Whether the compatibility endpoint serves each
id unchanged is unverified. No models list was called.

The reservation below is `reserve_microusd` at the published context figure
used as `max_input_tokens` and the published maximum output. Input price is
the highest input-side rate named for that case. Cache prices on this layer
may be zero because the page says caching is not supported; both rates are
shown. Exact billable input, when the context window and the max output share
one window, is unverified without the Models API.

| Task | Id the desk would name | Reservation at published maxima | Against a third of $3 ($1.00) or $5 ($1.67) |
| --- | --- | --- | --- |
| Voice and intention, tried first | `claude-opus-4-8` (the `anthropic` adapter's voice id; the models overview lists Claude Opus 4.8 at 1M context, 128K output, $5 / $25 per million) | $8.20 at the $5 input rate; $13.20 if the $10 one-hour cache-write rate is declared | Neither fits. |
| Voice and intention, if a smaller id were eligible | `claude-haiku-4-5`, alias of `claude-haiku-4-5-20251001` (200K context, 64K output, $1 / $5) | $0.52 at the $1 input rate; $0.72 at the $2 one-hour cache-write rate | Fits at $3. Not used, because requirement 4 already fails. |
| Moderation | `claude-haiku-4-5` | The reservation rule does not choose moderation. The page's `response_format` row is what makes this the structured-output id to name. The dated snapshot the alias resolves to may be the string a response reports. **Unverified.** | Not chosen by the dollar rule. |

`claude-haiku-5-5` is the current Haiku id on the models overview (1M context,
128K output, from $0.10 / $0.50, and $1 / $2.50 on prompts over 100K tokens,
with a $1 one-hour cache write on that long tier). A full 1M input at that $1
cache-write rate plus 128K output at $2.50 is $1.32. That fits a third of $5
and not a third of $3. It does not repair requirement 4.

## Candidate B — OpenAI Chat Completions

Pages read:

- [Create chat completion](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
  The documented path is `/v1/chat/completions`. The adapter joins that path
  onto a base URL, so the policy endpoint would be
  `https://api.openai.com/v1/chat/completions` when the base is
  `https://api.openai.com/v1`.
- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
  [GPT-6.2 Sol](https://developers.openai.com/api/docs/models/gpt-6.2-sol),
  and [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna).
- [Data controls](https://developers.openai.com/api/docs/guides/your-data).

| Requirement | Desk result |
| --- | --- |
| 1. Structured outputs | The create reference documents `response_format` of type `json_schema` with `strict: true`. The Luna, Sol, and GPT-5.6 Luna pages list `structured_outputs` and Chat Completions as supported. **Documented: passes for those three ids. Live conformance of this adapter's schema: unverified.** |
| 2. `store: false` | `store` is an optional boolean, default false. The adapter sends false. The data-controls page says Zero Data Retention, once approved, forces `store` false even if a request sets true. Sending `store: false` is not itself that approval. **The field is documented as real, not ignored. Whether this account has reduced retention is unverified.** |
| 3. Max-tokens parameter | `max_completion_tokens` is the documented bound, including reasoning tokens. `max_tokens` is deprecated and is not compatible with o-series models. The adapter's unset default is `max_completion_tokens`. The three model pages above are not described as o-series. **Documented: passes for that parameter name. Live: unverified.** |
| 4. Usage counts | The create reference's usage object includes `prompt_tokens`, `completion_tokens`, `total_tokens`, and `prompt_tokens_details.cached_tokens` (default 0). An example body on that page includes `cached_tokens: 0`. **Documented: the fields the settler needs are in the schema. A live body was not read. Unverified that every response includes the object rather than omitting it.** |
| 5. Reported model | The example completion includes a `model` string. GPT-6 Luna's page lists one snapshot, `gpt-6-luna`, the same as the model id. **Which string a response reports is unverified.** |

GPT-6 Luna's page says Chat Completions supports function calling only with
`reasoning_effort` set to `none`, and that the model's own default effort is
`medium`. This adapter sends `reasoning_effort` only when the operator sets
the env var. Intention and moderation use `response_format`, not function
tools. Whether an unset effort is accepted on Chat Completions for a plain
completion is unverified. GPT-6.2 Sol's page says the API rejects
`reasoning_effort` of `none`, so one option block cannot be copied across
ids. The watch example leaves `reasoning_effort` null until the owner sets it
after the live probe.

### Reservation rule on the published maxima

O4 qualifies a voice or intention model when one full-context reservation is
at most a third of the per-participant ceiling: $1.00 at the unconfirmed $3
draft, or $1.67 at the unconfirmed $5 draft. The figure here is
`reserve_microusd` with `max_input_tokens` set to the page's maximum input
(922,000 on each of these three) and `max_output_tokens` set to the page's
maximum output (128,000). A prompt over 272,000 tokens is priced at the long
rate for the whole request, so the full maximum uses the long rate. The
highest input-side price is the long cache-write rate, because the code
reserves at the maximum of the input, cache-read, and cache-write prices.

The model pages state cache writes at 1.25 times the uncached input rate.
GPT-6 Luna's long rates on that reading are $0.25 per million input-side and
$0.75 per million output. A pricing index also lists a higher 12-hour write
rate. Whether a request that sets no cache TTL, which is what this adapter
sends, is billed at the 12-hour rate is unverified. Both are shown. These
numbers are page arithmetic. They are not a filled policy, and they are not
a live bill.

| Id | 1.25× long cache write | 12-hour long write, if it applies | At $3 | At $5 |
| --- | --- | --- | --- | --- |
| `gpt-6-luna` | $0.3265 (326,500 microUSD). 9 reservations fit in $3 and 45 in $15. | $0.557. Still within $1.00. | Qualifies | Qualifies |
| `gpt-5.6-luna` | $0.6914. Within $1.00. | $1.1524. Within $1.67, not within $1.00. | Qualifies on the 1.25× rate only | Qualifies |
| `gpt-6.2-sol` | Long input alone is $4 per million, so 922,000 tokens are $3.688 before output or cache write. With the long 30-minute cache write ($5) and long output ($15) the reservation is $6.53. | Higher still. | Does not qualify | Does not qualify |

`input_bound_kind` has to be the provider context maximum. A shorter input
bound is not a way to qualify `gpt-6.2-sol`. Ordinary requests ask for at
most 256, 200, 500, and 32 output tokens (node, inhabitant, intention,
moderation). A policy may set `max_output_tokens` to those request bounds,
which lowers the output term. It does not lower the input term, and the
input term is what excludes `gpt-6.2-sol`.

No larger id checked here qualifies at $5. Between `gpt-6-luna` and
`gpt-5.6-luna`, both qualify at $3 on the 1.25× rate, and this desk check
has no capability ranking that makes one the larger model. `gpt-6-luna`
still qualifies at $3 if the unverified 12-hour rate applies. `gpt-5.6-luna`
does not. The id named below is therefore `gpt-6-luna`.

### Models this candidate would pin

| Task | Id | Why |
| --- | --- | --- |
| Voice | `gpt-6-luna` | Qualifies at the unconfirmed $3 draft under both cache-write readings above. The larger everyday id checked, `gpt-6.2-sol`, does not qualify at $5. |
| Intention | `gpt-6-luna` | Same reservation. Voice and intention share this result, so the per-participant draft stays $3 rather than rising to $5. |
| Moderation | `gpt-6-luna` | O4 does not choose moderation by the reservation rule. This page lists structured outputs and Chat Completions. The calls are short and capped. |

`resolved_models` has to be an id the checker accepts before the first probe.
The checked-in example's `<OWNER: resolved model id>` contains spaces, and
`check_file` refuses it, so leaving that marker in place means the twin never
starts the call that would show the reported id. For this candidate the
owner-reviewed starting allowlist is the documented snapshot `gpt-6-luna`:
the model page lists that one snapshot and no second one. It is still an
unconfirmed desk name. The owner writes it into the private policy file, not
into the checked-in example.

If the first response's `model` field is a different string, add that string
to `resolved_models`, keep the reviewed snapshot as well when both should be
allowed, run `model-policy --check` again, and only then retry the probe. Do
not retry on an allowlist the response has already missed. Do not treat this
table as the filled file.

These ids are a desk result for this watch. They are not a standing model
preference. Another endpoint that passes the same five checks can replace
them when the owner signs a new note.

## Recommendation

Use candidate B, OpenAI's Chat Completions endpoint
`https://api.openai.com/v1/chat/completions`, for the watch desk check.
Candidate A fails published requirements 2 and 4: `store` is ignored, and
`usage.prompt_tokens_details` is always empty, so this adapter would keep
every call unsettled at its full reservation. The vendor page also says that
compatibility layer is not a production-ready solution.

The owner signs the data-use note for that one OpenAI account at that exact
endpoint, then G3's first live run on the twin is what accepts or rejects
ADR-035 for that endpoint. Signing does not wait for the live run, because
the live run needs the signed note. A later switch of account or endpoint
needs a new note. This record does not accept ADR-035.

What the note has to cover, from O3, still unsigned:

- Speak and agent-voice exchanges, free-text intentions, every shared Speak,
  Ideas, and published-profile line sent for classification, chat lines and
  puzzle free text that the local screen marks ambiguous, and world content
  in prompts (node names, properties, and history).
- Never sent: report text, private journal notes, and unpublished profile text.
- No Enfolded data trains a model.

The OpenAI data-controls page says that, as of 1 March 2023, API data is not
used to train OpenAI models unless the customer opts in, and that
`/v1/chat/completions` is marked "No" for training. It also says abuse-monitoring
logs are kept up to 30 days unless the account is approved for Zero Data
Retention or Modified Abuse Monitoring, and that `store: false` does not by
itself grant that approval. Prompt-cache tensors may sit on a GPU for up to
24 hours. The Anthropic retention page says retained customer data is not used
for training without express permission, and that Zero Data Retention is
requested per organization. **Neither page was confirmed against an account.
Reduced retention for the watch account is unverified. The owner requests it
where the account offers it, and records the answer in the note.**

`max_completion_tokens` includes reasoning tokens. GPT-6 Luna's page says the
model's default effort is medium, and the watch example leaves
`reasoning_effort` null, which means this adapter sends no effort and the
provider default applies. Moderation asks for 32 output tokens and intention
for 500. At medium effort a strict-schema answer can come back empty or cut
off, and a probe can fail for that reason rather than for the endpoint.
The adapter has one reasoning effort for the whole process, so every enabled
route has to name the same value or the startup check refuses the file.
Before the first probe, set `reasoning_effort` to `none` on every enabled
route in the private file, and set
`NESTED_WORLDS_OPENAI_COMPATIBLE_REASONING_EFFORT` to that same token, unless
the owner records a different effort. The Luna page lists `none` as a
supported effort. The G3 probe should use the real per-task output bounds,
32 and 500 included, not only a short sample.

## Still unverified

- Whether a default or medium reasoning effort consumes the 32-token
  moderation bound or the 500-token intention bound on this endpoint. No live
  call was made.
- Every live response body: usage, `model`, schema conformance, and whether
  `store: false` changes what the account retains.
- Whether an unscoped incumbent key is rejected for lack of
  `anthropic-workspace-id`.
- The exact billable input maximum when a page gives both a context window
  and a max output.
- Whether a 12-hour cache-write price applies to a request this adapter sends.
- That the owner's account is allowed to call `gpt-6-luna`, and that the
  response `model` string is `gpt-6-luna`.
- That `claude-opus-4-8` and `claude-haiku-4-5` are accepted unchanged on the
  compatibility endpoint.
- Account-level training opt-out and reduced retention, for either candidate.
