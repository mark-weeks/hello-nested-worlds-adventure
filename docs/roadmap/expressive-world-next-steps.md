# Expressive world: review boundary and next work

**Updated September 20, 2026 after the Commit, then discover batch.** The owner asked to package the session's changes for review
and undertake further UI/UX, navigation and placement work as a dedicated effort.
This checkpoint is not a claim that the production-quality milestone is complete.

## What the current change delivers

- One Act surface in each browser client, four suggested actions at each of eleven
  scales, optional combinations, and an intention entry point. All 44 actions
  change scale-specific properties; unrestricted invention is not implemented.
- Server enforcement that a player acts for themselves. New forced delegation and
  the gallery choice controller are closed; historical receipts and work survive.
- Recoverable commitments and delayed consequences, current-state sensory
  descriptions, four curated scene images, and eleven sampled musical forms.
- One place identity block containing scale, name, position and evolving
  description. The scene no longer repeats this text.

See [ADR-027](../decisions/ADR-027-expressive-world.md),
[ADR-028](../decisions/ADR-028-scale-native-autonomy.md), the
[implementation evaluation](../evaluation/2026-09-20-expressive-world.md), and
[correction evidence](../evaluation/2026-09-20-scale-native-correction.md).
The evaluations describe successive builds; the CHANGELOG holds the final local
verification counts and the corrections that supersede the initial design.

## Batch 1: Commit, then discover — implemented for review

- Four scale-native suggestions commit directly in both clients. Optional
  combinations and discoverable intention entry remain in the existing Act surface.
- Intention submission authorizes the attempt. Only material action/target/scope/
  order ambiguity clarifies; unsupported purposes remain unsupported. The forecast
  endpoint and pre-commit deltas, signals and route listings are removed.
- Version 3 accepts attempts and settles against current conditions. Ordered steps
  can become moot independently. Only observed material effects produce further
  work; receivers pass on their observed remainder. Other players act independently.
- Acceptance, pending consequences and observed outcomes are distinct in feedback
  and append-only history. Recaps reveal observed destinations only. Browser recovery
  retains the payload and request ID across lost replies, retries and reloads.
- Accepted v1/v2 work, historical actors and receipts remain recoverable under their
  original semantics. No schema migration or world reset. The existing local playtest
  world was preserved; inspection used a separate database copy.

Evidence and limitations: [batch verification](../evaluation/2026-09-20-commit-discover.md).
Intention interpretation is provider-fixture tested, not live-model validated.
Model absence remains an authored quiet reply; explicit action sequences work offline.
This batch does not implement scoring, agent/CLI vocabulary parity or styling.

## Subsequent UX batch — handoff only, not started

Start with the owner's next concrete feedback on navigation paths, placements and
visual hierarchy. Inspect the current browser before proposing a layout. Preserve
Speak | Puzzle | Act, four discoverable suggestions, open intention entry, a single
identity block and independent player agency. Extend or replace each experience;
do not introduce a second control for the same purpose.

The [visual-language guide](../design/visual-language.md) now records the latest
decision: starting values derive from each node's initial conditions and evolve
with current conditions and lasting traces. Color carries learnable meaning.
The interface shares the world's visual vocabulary while retaining readable text,
recognizable controls and stable interaction targets. It must not be themed with
one universal set of colors across all nodes. This is a design requirement; the
current interface is still largely fixed.

Before implementing global mappings, compare several contrasting scales, two
different places at the same scale, and their states before and after meaningful
actions. Judge semantic correspondence and expressive quality, then verify narrow
and wide layouts, keyboard use, text zoom, reduced motion and missing artwork.
Automated checks support this review; they do not establish aesthetic acceptance.

## Separate behavioral and production gaps

1. **Adaptive interface styling:** the behavioral contract above is implemented;
   preserve it while addressing the visual-language guide's still-unimplemented
   node-derived interface styling. Do not add previews, extra confirmation steps,
   competing composers or another identity block. Keep recovery and clarification
   visible at narrow widths and through keyboard use.
2. **Intention and recognition:** configured-model interpretation exists but its
   live quality has not been evaluated. Intervention alignment/contribution scoring
   is not implemented. Agent and CLI access still uses the original verb path;
   the expanded browser vocabulary does not establish capability parity.
3. **Art and sound quality:** use blinded listening and repeated visits to evaluate
   recognizable scales and node correspondence. The recorded audio checks prove
   finite, non-clipping output, not cinematic excellence. Four curated images do
   not establish a world-wide production art pipeline or generation quality parity.
   The [beta artwork strategy](../design/beta-scene-art.md) remains a proposal.

Keep subsequent UI cleanup independently reviewable. Start only with a new owner
instruction. After this behavioral PR merges, start from refreshed main; if a UX
effort is explicitly requested before then, make its dependency on this PR clear. Preserve the
existing local playtest world's history across preview restarts. No new session,
merge, deployment or production operation is implied by this handoff.
