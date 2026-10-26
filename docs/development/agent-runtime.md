# Provider, model and prompt guidance

Read when changing voice quality, provider/model selection, prompt bibles, caching,
or the four text-model call paths. [ADR-034](../decisions/ADR-034-provider-and-model-optionality.md)
defines the optionality policy. Product behavior is the contract; vendors, models
and versions are replaceable choices that require evidence.

## Current implementation and its limits

Text generation uses the configured provider (currently Anthropic). Each text
task resolves its own model id through `consciousness.runtime.model_for(task)`.
Call sites pass a task name; they do not read environment variables.

| Task name | Setting | When unset |
|---|---|---|
| `node` (node voice) | `NESTED_WORLDS_NODE_MODEL` | `NESTED_WORLDS_MODEL`, then `claude-opus-4-8` |
| `inhabitant` (inhabitant voice) | `NESTED_WORLDS_INHABITANT_MODEL` | `NESTED_WORLDS_MODEL`, then `claude-opus-4-8` |
| `intent` (intention interpretation) | `NESTED_WORLDS_INTENT_MODEL` | `NESTED_WORLDS_MODEL`, then `claude-opus-4-8` |
| `moderation` | `NESTED_WORLDS_MODERATION_MODEL` | `claude-haiku-4-5` |

An unset value uses the fallback in the table. `model_for` also treats a
whitespace-only value as unset, so a call still falls back. The startup check
does not: a variable set to empty or whitespace is a misconfiguration and
`python main.py serve` refuses to boot. Moderation does not inherit the shared
voice model. With no per-task settings, node voice, inhabitant voice, and
intention keep using `NESTED_WORLDS_MODEL`, so an existing deployment that
leaves those variables unset does not change.
The code defaults above are configuration, not a verified recommendation or a
guarantee of availability. Confirm the effective environment before a live run.

The current adapter uses the SDK's resolved credentials: `ANTHROPIC_API_KEY`,
`ANTHROPIC_AUTH_TOKEN` (bearer token), or its local profile/federation
credential provider. The availability check uses the same SDK client as
generation; it checks configuration without making a model request, not
credential validity. This behavior is verified against the
[pinned SDK source](https://github.com/anthropics/anthropic-sdk-python/blob/v0.120.2/src/anthropic/_client.py).

A model id does not switch providers. Credentials, SDK calls, structured
output and cache controls must match the implemented adapter. A failed call
stays on the id that was requested: nothing retries a different model or
provider. Provider-named budget settings and persisted buckets are current
compatibility details; do not rename/reset them to make the interface look
neutral or let a provider switch replenish a user's allowance. Daily call caps
are not dollar caps, and identical call counts do not imply identical spend.

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
and `TokenUsage`, resolves per-task model ids in `model_for`, shares the
concurrency limit and logs provider/model usage. `TextProvider.model_id_validator`
is optional. It returns a function from a model id to `ok`, `warn`, or
`reject`, or nothing when the adapter does not judge ids. `reject` means this
adapter does not serve the id. `warn` means the id is plausible but not a
known release. `consciousness/model_check.py` is the only caller and does not
name a provider. `consciousness/anthropic_provider.py`
implements the sole current adapter. Its validator accepts the known Claude
ids and a dated snapshot of one of them, warns on any other `claude-` shaped
id so a new release does not block boot, and rejects every other id. All four tasks use the boundary; the node voice, inhabitant voice and intention endpoints ask the selected adapter whether
it is configured before charging their existing voice budgets. Missing
credentials serve authored fallbacks without a voice call, budget charge or
speech chronicle row. A model-written chronicle row records the provider name
and the resolved model id from that call's Completion, in
`mutation_model_provenance`. The call was made with `model_for(task)`; the
stored id is the one the provider returned for that call, not a later read of
the setting, and a missing response id stays unknown. Historical rows are not
backfilled. Authored fallback text records none. Player history, the chronicle
page and node voices do not read the side table. Deleting a chronicle row
deletes its provenance row with it. Adding another provider still requires an
adapter and explicit selection wiring in `get_provider()`; there is no
multi-provider environment selector or automatic failover. Per-task model
settings are not that selector.


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

`python main.py models` prints the active provider and, for each task, the
resolved model id, where it came from (`task env`, `NESTED_WORLDS_MODEL`, or
`default`), and any problem. It does not call the provider. Run it with the
model variables the machine will use before `scripts/deploy.sh` or a Fly boot.

A hard problem is one line naming the environment variable: an empty or
whitespace-only setting, an id that is not a usable token, or an id the
active adapter rejects. `python main.py serve` exits with that line before it
opens a port, so the deploy fails instead of holding shared text on the first
moderation call. A soft problem, including surrounding whitespace that was
stripped and an unknown but plausible id, logs one warning and still boots.
Neither line prints a credential. `/health` stays a liveness check and does
not report model ids.

`python main.py models --probe` makes one tiny live call per distinct model
id (`max_tokens` 1). It is off unless that flag is passed. Server startup,
`./scripts/check.sh`, tests, and CI do not pass it, and there is no
environment variable that turns it on. It needs a credential for the active
provider, spends a real call, and does not charge the model-action cap or the
`anthropic` budget bucket. A refused probe exits 1. It confirms the provider
accepts the id. It is not a quality, cost, or cache evaluation.

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
