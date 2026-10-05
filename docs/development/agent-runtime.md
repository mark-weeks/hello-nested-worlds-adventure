# Provider, model and prompt guidance

Read when changing voice quality, provider/model selection, prompt bibles, caching,
or the four text-model call paths. [ADR-034](../decisions/ADR-034-provider-and-model-optionality.md)
defines the optionality policy. Product behavior is the contract; vendors, models
and versions are replaceable choices that require evidence.

## Current implementation and its limits

Text generation currently uses Anthropic. `NESTED_WORLDS_MODEL` selects the model
for node voice, inhabitant voice and intention interpretation; its code default
is `claude-opus-4-8`. `NESTED_WORLDS_MODERATION_MODEL` independently selects the
classifier, defaulting to `claude-haiku-4-5`. Both use the SDK's resolved
credentials: `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` (bearer token), or its
local profile/federation credential provider. The availability check uses the
same SDK client as generation; it checks configuration without making a model
request, not credential validity. This behavior is verified against the
[pinned SDK source](https://github.com/anthropics/anthropic-sdk-python/blob/v0.120.2/src/anthropic/_client.py).
These identifiers describe configuration, not a verified recommendation or a
guarantee of availability. Confirm the effective environment before a live run.

Changing a model ID does not switch providers. Credentials, SDK calls, structured
output and cache controls must match the implemented adapter. Provider-named
budget settings and persisted buckets are current compatibility details; do not
rename/reset them to make the interface look neutral or let a provider switch
replenish a user's allowance. Daily call caps are not dollar caps, and identical
call counts do not imply identical spend.

The optional image path has a separate fal.ai integration. Future image or speech
adapters follow the same selection principle, with their own capability and data
requirements. This policy does not claim those adapters already exist.

## Compare before selecting

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
| Moderation | Clear and ambiguous examples, false blocks and misses, timeout behavior, and the existing fail-open/local-filter contract |
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
and `TokenUsage`, shares the concurrency limit and logs provider/model usage.
`consciousness/anthropic_provider.py` implements the sole current adapter. All four
tasks use the boundary; the node voice, inhabitant voice and intention endpoints
ask the selected adapter whether it is configured before charging their existing
voice budgets. Missing credentials serve authored fallbacks without a voice call,
budget charge or speech chronicle row. Adding another provider still requires an
adapter and explicit selection wiring in `get_provider()`; there is no multi-provider environment
selector or automatic failover in this batch.


Keep task prompts, transcripts and deterministic validation in application code.
Put SDK/client construction, credential checks, provider payloads, response and
usage normalization, and provider-specific cache/schema features behind a small
adapter boundary. Unsupported required capabilities must produce the existing
safe task behavior, not a silent weaker request or a hidden provider fallback.

Test the boundary without paid calls: request construction, history ordering,
text extraction, completion/refusal/truncation handling, schema behavior, timeout,
usage fields, missing credentials and provider failures. Exercise the existing
HTTP fallback and budget tests too. A replacement must preserve application-owned
state and receipts; provider I/O must stay outside SQLite transactions. A second
adapter is a separate implementation until the candidate and scope are selected.

## Voice and caching

For flat voices, inspect which world-state the dynamic prompt omits before changing the
model. This is a diagnostic starting point, not a conclusion that model capability can
never be the bottleneck. Compare representative voices when evaluating a model change.

When changing models or cache structure, verify the selected provider/model's
current cache semantics and minimum against official documentation. The existing
`cached_prefix_meets_minimum()` and startup `warn_if_cache_ineffective()` guard
use a rough character-based estimate and adapter-owned reference metadata
([Claude API reference verified 2026-10-05](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#cache-limitations):
Opus 4.5/4.6 and Haiku 4.5: 4096 tokens; Opus 4.7: 2048;
Opus 4.8 and Sonnet 4.5/4.6: 1024). The adapter recognizes those exact versions
and their dated snapshot suffixes; it does not extrapolate to future versions.
Unrecognized IDs report unknown eligibility and the estimated smaller prefix
size. These estimates do not establish actual tokenization, model availability,
a cache hit or a universal minimum. Keep the warning useful when
replacing that integration; a provider without explicit cache controls needs its
own usage evidence, not an Anthropic-shaped request.

Retain useful lore and behavioral guidance. Do not pad prompts merely to cross a
cache threshold or forbid a worthwhile prompt reduction: compare task quality
and total cost under the selected model's actual cache behavior.

Complete a voice/caching change with relevant prompt behavior tests and observed evidence
for the claimed improvement. Report any unavailable live-model verification; avoid claiming
a cache hit from the presence of `cache_control` alone.

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
