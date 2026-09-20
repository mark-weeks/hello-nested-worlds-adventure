# Expressive world: review boundary and next work

**September 20, 2026.** The owner asked to package the session's changes for review
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

## Dedicated UI/UX effort

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

1. **Commit, then discover:** the runtime still requires previews and reveals
   property deltas and future routes. Replace this behavior in a separately
   reviewable change. Clear actions commit directly; ambiguity may clarify only
   the attempted action, target or scope. Delayed outcomes must meet current
   conditions and independent players' actions. Preserve old receipts and pending
   work; hiding the existing forecast is insufficient.
2. **Intention and recognition:** configured-model interpretation exists but its
   live quality has not been evaluated. Intervention alignment/contribution scoring
   is not implemented. Agent and CLI access still uses the original verb path;
   the expanded browser vocabulary does not establish capability parity.
3. **Art and sound quality:** use blinded listening and repeated visits to evaluate
   recognizable scales and node correspondence. The recorded audio checks prove
   finite, non-clipping output, not cinematic excellence. Four curated images do
   not establish a world-wide production art pipeline or generation quality parity.
   The [beta artwork strategy](../design/beta-scene-art.md) remains a proposal.

Keep UI cleanup and changes to action acceptance independently reviewable. If a
new effort starts before this checkpoint merges, base it on this branch and make
the dependency explicit; after merge, start from refreshed main. Preserve the
existing local playtest world's history across preview restarts. No new session,
merge, deployment or production operation is implied by this handoff.
