# Provider and model optionality — 2026-10-04

Scope: the owner's request to remove vendor/model preference and preserve
practical replacement. Inspected against `main` at `6ead894` (#111). No new
provider, changed model default, paid evaluation, publication or deployment.

## Findings and disposition

| Finding | Evidence and action |
|---|---|
| Confirmed product-language coupling | README and CLI described the experience as Claude-powered. Replaced with behavior-based language; kept provider names in accurate setup and implementation details. |
| Confirmed policy preference | ADR-005 §4 favored Opus and deferred comparison to Sonnet; the Q4 plan and Proposed ADR-031/032 carried model-family preferences forward. ADR-034 supersedes the standing preference and updates those current plans without ratifying their unrelated proposals or rewriting the historical decision. |
| Confirmed integration coupling | Four text paths constructed Anthropic requests; intention availability checked its key directly. Added a narrow `TextProvider` boundary and one Anthropic adapter. A fixture adapter exercises every task without the incumbent SDK payload or credentials. |
| Overstated caching evidence | Prompt-length estimates and request markers cannot prove live cache hits or savings. README/runtime guidance now distinguish them; unknown model IDs get an unknown-eligibility warning instead of the incumbent threshold. |
| Deliberately retained compatibility | Exact default model IDs, credentials, provider-named limits, persisted budget buckets, shared concurrency, prompt content, validators and fallbacks retain their existing contracts. No usage allowance is reset. |
| Remaining implementation limit | Anthropic is still the only text adapter. Selecting a second provider requires an adapter, explicit selection wiring, compatible task capabilities and validation. Image generation still has its own fal.ai integration. |
| Unverified suitability | No live model or provider comparison was run. Current availability, quality, latency, reliability, caching and cost are not established by fixtures; retained defaults are not re-endorsed. |

## Ordered next selection work

1. Define a concrete task and pass criteria, then choose credible candidates across
   providers/model families where practical. Done when a comparison brief names
   required capabilities and the improvement that would justify switching.
2. For a new provider, implement its adapter and selection wiring. Done when task,
   schema/refusal, credential, budget, concurrency and fallback tests pass without
   provider-specific changes in the world logic or durable-state rewrites.
3. Run the representative live comparison described in
   [runtime guidance](../development/agent-runtime.md), using data authorized for
   each destination. Done when a dated record identifies exact model/version,
   configuration, quality results, latency, failures, actual usage/cost and limits.
4. Select and record the winner and rollback configuration; change defaults only
   on that evidence. Deployment remains subject to the existing separate gates.

## Verification

Focused existing suites: 170 passed. Boundary and prompt checks: 49 passed,
including 19 new provider-boundary cases (the counts overlap on voice tests).
The first endpoint run could not bind loopback in the sandbox; the rerun with
local-server access passed. The first full browser run passed 94/96; two intention cases still patched the
removed SDK entry point. Their provider fixture now returns the normalized
completion through the new boundary; the complete browser rerun passed **96/96**
in 2.5 minutes. The canonical run passed Ruff, **1,436 Python** (246.31s),
**131 Vitest**, byte-fresh production bundle and installed-wheel smoke before
that fixture correction. Results are also recorded in the
batch's [CHANGELOG entry](../CHANGELOG.md). Local documentation validation
checked 77 Markdown targets; all resolved. A structural comparison confirmed
13 prompt, memory and authored-fallback definitions unchanged. CLI help uses
the configured-model wording; final interface/boundary checks passed 49 cases.

**Irreversibility check:** none — no migration, golden/birth change, new chronicle
write path, world-meta pin, hinge or era-bank edit. The diff changes selection
policy, documentation and the existing text integration; world ownership,
autonomy, accepted actions and append-only history remain unchanged.
