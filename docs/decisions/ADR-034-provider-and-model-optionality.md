# ADR-034: Provider and model optionality

**Status:** Accepted policy direction, 2026-10-04, at the owner's instruction.
This accepts optionality and evidence-based selection. It does not select a new
provider, endorse an existing default, authorize deployment, or ratify other ADRs.

## Context

At the start of this change, Enfolded's product language described nodes as
animated by Claude. Its four text call paths used Anthropic's SDK,
request/response format and credentials directly.
Voice and intention interpretation share `NESTED_WORLDS_MODEL`; moderation has its
own model setting. These permit model changes within the current integration,
not arbitrary provider substitution. Optional generated images use fal.ai.

ADR-005 §4 favored Opus for launch and a later Sonnet comparison. The owner now
requires vendors, providers, models and versions to earn their place: a more
capable or cost-effective choice should remain practical to adopt. World identity,
continuity and player autonomy must not depend on a vendor's continued availability.

## Decision

1. **Describe the product by its behavior.** Nodes and inhabitants have
   model-backed voices; their identities come from world state, memory and authored
   guidance. Use vendor/model names where they convey an implementation fact,
   configuration, evidence or provenance. Preserve historical records and accurate
   setup instructions rather than erasing every vendor name.
2. **Choose by task and evidence.** Compare the incumbent with credible alternatives,
   including another provider or a local/deterministic approach where suitable.
   Evaluate capability, quality, latency, reliability, total cost and relevant data
   terms. No vendor, model family, premium tier, or latest version is preferred by
   default. Different tasks may justify different selections; shared routing today
   does not require shared routing forever.
3. **Keep replacement practical.** Separate prompts and world rules from provider
   transport, credentials, request/response formats and usage accounting. Use a
   narrow task-facing boundary when changing the integration, not a universal model
   framework. Keep task configuration explicit; unsupported combinations must not
   silently route to an incumbent or another external service.
4. **Use capabilities deliberately.** Caching, structured output, tool use and media
   features may be valuable. Isolate their implementation and validate each adapter's
   equivalent behavior; do not assume that another API or model offers the same
   semantics. Preserve application validators even when a provider enforces a schema.
   Missing required capabilities disqualify a candidate for that task; optional
   optimizations need not constrain every provider.
5. **Own the durable state.** Prompts, world records, transcripts and accepted actions
   remain application-owned. A provider switch must not require rewriting world
   identity or the chronicle. Preserve existing budget, moderation, fallback,
   autonomy and continuity rules. New data destinations and changes to retention,
   access or persistent authorship require their own scoped decisions.
6. **Record the choice and the way back.** Selection evidence names the provider,
   exact model/version or alias, evaluation date, task, configuration and limits.
   Pin a version where practical; where only an alias exists, record that drift risk
   and re-evaluate observed changes. Retain a tested rollback configuration while
   available; otherwise use the existing authored fallback. Never silently fail over
   to a different provider or treat historical outputs as having come from the new one.

This supersedes ADR-005 §4's standing model-family preference and its restriction
of comparison to a post-launch Sonnet A/B. Current identifiers stay explicit in
configuration until an evidence-backed replacement is chosen. The same principle
applies to images, future speech and other vendor services in proportion to actual
switching costs. It does not demand adapters for every service today.

## Trade-offs accepted

- A focused adapter has a maintenance cost, but makes provider assumptions visible
  and gives replacements a bounded integration surface.
- Optionality does not mean feature parity or zero-cost switching. Provider-specific
  strengths remain usable when their benefit exceeds their integration and exit cost.
- Local contract tests establish mechanics. Only representative live evaluation can
  establish quality, actual caching, latency, reliability or cost for a candidate.
- Keeping current defaults avoids an unevaluated behavior change; it is not evidence
  that those defaults have earned continued selection. The live-model gate remains open.

## Revisit when

- A credible alternative improves a task's quality, capability, successful-interaction
  cost or reliability enough to justify migration and ongoing maintenance.
- A provider changes availability, versions, pricing, limits or data terms; an alias
  changes behavior; or observed quality, latency or failure rates regress.
- A new task requires different capabilities, or existing routing prevents a worthwhile
  comparison. Add the smallest necessary adapter or task setting then.

## Rejected alternatives

- **Neutral wording alone as portability.** It corrects positioning but leaves SDK,
  credential, schema, cache and budget dependencies in place. State the remaining limits.
- **Replace the incumbent because another model is newer or cheaper per token.**
  Neither establishes useful quality or lower cost per successful interaction.
- **Build a universal router and many adapters immediately.** Maintenance and untested
  behavior would grow before a second provider has demonstrated value.
- **Restrict all providers to their common features.** This discards capabilities that
  can earn their integration cost. Use explicit requirements and bounded adapters.
