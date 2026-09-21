# Expressive world: review boundary and next work

**Updated September 21, 2026 after the UX implementation.** The owner asked to package the session's changes for review
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

## Batch 1: Commit, then discover — reviewed and merged

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
  Outcome wording follows actual changed fields, including partial effects at a
  property limit. Empty intentions remain local; suggestions have no predicted
  availability state. Preserve these contracts during subsequent UX changes.
- Accepted v1/v2 work, historical actors and receipts remain recoverable under their
  original semantics. No schema migration or world reset. The existing local playtest
  world was preserved; inspection used a separate database copy.

PR #106 was reviewed and merged into main as `e038d19015a51e6111ee50a2e82441a0f576c6c8`
on September 21 (UTC); all 15 review threads were resolved before UX work began.

Evidence and limitations: [batch verification](../evaluation/2026-09-20-commit-discover.md).
Intention interpretation is provider-fixture tested, not live-model validated.
Model absence remains an authored quiet reply; explicit action sequences work offline.
This batch does not implement scoring, agent/CLI vocabulary parity or styling.

## Batch 2: UX, navigation and evolving visual language — implemented for review

The owner confirmed the starting placement: movement beside the scene, one
identity block, Speak | Puzzle | Act immediately below it, and secondary detail
through disclosure. The initial scene/map inspection found competing utility
links, tiny secondary text, fixed-height mobile scrolling and no coherent return
surface. Both clients now share navigation and semantic interface foundations,
with an eight-place temporary return trail, visible sealed destinations and
keyboard focus carried to the new place. Map Puzzle opens without a separate
Find Puzzle step. Existing action commitment, clarification and recovery remain.

The [visual-language guide](../design/visual-language.md) describes the implemented
mappings. Region, Room, two Objects and Molecule were compared before/after actual
local actions before generalizing. Material/atmosphere, terrain, geometry and
retained traces affect appearance without permanent node categories or a moral
palette. One readable interaction structure stays consistent across those states.

See [the UX evaluation](../evaluation/2026-09-21-ux-visual-language.md) for captures,
measured verification, implementation discoveries and limitations. This is an implementation
review candidate, not a merged or deployed batch. The original playtest database
was not used for writes; interactive exploration used a separate copy and browser
regressions used temporary databases.

## Separate behavioral and production gaps

1. **UX validation:** playtest discovery of movement, returning and intention entry,
   and whether players learn the color/trace meanings. Review the candidate's narrow,
   zoomed and degraded states. Physical mobile devices, Safari and assistive
   technology beyond Chromium keyboard/DOM checks remain unverified. The return
   trail is per client tab, not a saved itinerary. Standalone auxiliary pages still
   need a separate consistency pass if prioritized.
2. **Intention and recognition:** configured-model interpretation exists but its
   live quality has not been evaluated. Intervention alignment/contribution scoring
   is not implemented. Agent and CLI access still uses the original verb path;
   the expanded browser vocabulary does not establish capability parity.
3. **Art and sound quality:** use blinded listening and repeated visits to evaluate
   recognizable scales and node correspondence. The recorded audio checks prove
   finite, non-clipping output, not cinematic excellence. Four curated images do
   not establish a world-wide production art pipeline or generation quality parity.
   The [beta artwork strategy](../design/beta-scene-art.md) remains a proposal.

Next handoff: re-review the 17 fixes on PR #107 against its visual evidence and
the agreed placement; gather player observations before assigning another implementation
batch. Improved fallback art is a discovered production gap, not work silently
absorbed here. Any follow-on implementation requires a new owner instruction and
a refreshed merged base. Preserve the existing playtest history. No merge,
deployment, reset or automatic next batch is authorized.
