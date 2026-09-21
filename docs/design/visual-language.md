# Enfolded visual language

**2026-09-20 · first style guide.** The interaction principles below reflect the
owner's explicit direction. Palette, typography and composition are proposed
restyling targets; they are not a claim that both clients already implement them.
Artwork production is covered in [the beta art strategy](beta-scene-art.md).

## Experience

Make the interface as simple as possible while giving players room to act
imaginatively. Guide through possibilities, present conditions and discoverable
consequences as they occur.
A player should feel invited to explore, not assigned a sequence to complete.

The scene carries wonder; the interface makes participation easy and expresses
the place's evolving character. Its initial appearance derives from the node's
starting conditions and evolves with current conditions and lasting material
traces. Keep interaction structure dependable as appearance changes; controls
must remain easy to find and read.

- Give the current place one identity block containing scale, readable name,
  position identifier and its evolving description. Keep that block in the
  interaction panel; do not repeat it over the scene or inside interaction tabs.
  Reference the same description for accessible scene content. The description
  reflects current conditions and persistent material traces; the born aspect
  and historical state remain intact.
- Preserve Speak | Puzzle | Act as the primary interaction structure.
- Present four useful, scale-native actions as invitations into possibility.
  Four visible suggestions are not a permanent limit on the world's vocabulary.
- Keep **Describe an intention** in Act. It is an equally valid way to begin,
  visually easy to discover without a second composer or persistent extra panel.
- Reveal combinations, observable conditions and the history of actual consequences
  when requested. Do not reveal an unobserved future causal route.
- Let players commit to an action and discover what follows. A clearly labeled
  action is itself a commitment; it does not need a mandatory preview/confirm step.
  Clarify an intention only when ambiguity would materially change the action,
  target, scope or order. Clarification establishes what the player attempts, not what
  the world will do in response.
- Every human and AI player chooses their own actions. Invitations never imply
  another player's agreement. Extend or replace existing UX; do not duplicate it.

## Visual direction

Cinematic, tactile worlds with restrained editorial typography. The approved
orchard/gallery/instrument/chain images establish a reference for material detail,
light, depth and continuity across scales. Their copper light and dark teal shadows
belong to that family of places; they must not become a mandatory color grade for
an ice world, a coral landscape or every atom.

Use persistent motifs across connected scales: a branching form, a characteristic
material, a recurring light pattern. Let composition and physical properties make
scale legible. Avoid a universal glowing sphere, schematic, orbital sketch or
particle field as the finished representation of unrelated places.

Let the scene image stand on its own, without a title or description overlay.
Compose for meaningful focal points and readable navigation at the edges. Artwork
contains no interface text. Navigation must remain legible over bright and dark
images; the identity block must remain readable independently of the artwork.

## Interface foundations

Use shared semantic token roles, including inside the Act component's shadow
root. Their values come from the current node's visual interpretation rather
than one universal palette. The same material and atmospheric evidence should
inform scene and interface; contrast requirements may change the interface's
exact shades. Do not add another layer of hard-coded component colors.

| Token | Derivation | Role |
|---|---|---|
| Canvas | Current material and atmosphere, with controlled luminance | Background |
| Surface | Related to Canvas, separated enough to read | Panels and secondary controls |
| Text | Legible against the resolved surface | Main text |
| Secondary text | Legible supporting tone within the local palette | Supporting copy |
| Accent | Salient local property or combination, with sufficient contrast | Focus and selection |
| Link | Distinct, readable interactive treatment in the local palette | Navigation and references |
| Attention | Distinct local treatment paired with an explicit cue | Recoverable problems or caution |

Color should carry learnable meaning, including associations with properties and
their combinations. The owner's card-color analogy is a vocabulary reference,
not a requirement to import another game's categories. Enfolded's associations
must remain responsive to a changing world. Avoid assigning every node a fixed
color class or treating restoration as morally good and disruption as morally bad.
Meaningful distinctions also need a non-color cue for accessibility. Selected,
unavailable, pending and failed states need text or shape as well as color;
reduced opacity alone is insufficient.

Scale, material, atmosphere and relevant state establish a node's initial palette,
type treatment, contours, texture and motion. Two nodes at one scale can differ.
Present conditions govern their evolution; retained physical traces can carry
history into that appearance. A preserved birth record is not an appearance lock.
Combine properties through accents, patterns and layering without reducing every
place to one category. Minor changes should be subtle; profound transformations
may substantially alter the expression. Only observed state should be signaled,
without revealing hidden information or forecasting an action's outcome.

The values below are reference ranges and usability constraints for the first
implementation, not universal node styling. Exact semantic mappings still need
design and comparative playtesting. **Current gap:** scene qualities already use
some property mappings; the interface remains largely fixed. This section records
the owner's direction and does not claim that adaptive interface styling exists.

- **Type:** a restrained serif for place names and short atmospheric lines; a
  readable sans serif for controls, explanations and history. Reserve monospace
  for addresses and technical identifiers, shown only when useful. Start with
  Georgia and the system sans stack to avoid a new font-loading dependency.
- **Size:** 16px body text, 14–16px action labels, 12–13px secondary metadata,
  responsive 22–30px place names in the identity block. Do not use tiny spaced capitals for sentences
  or essential controls. Keep body line height around 1.5.
- **Spacing:** a 4/8/12/16/24/32/48px scale. Group related content with space;
  borders are reserved for useful boundaries rather than every line of data.
- **Controls:** at least 44px interaction height as a design target, locally
  expressive contours, clear keyboard focus, and a recognizable visual hierarchy. A primary
  action button names what the player will attempt. Keep optional composition in
  the same surface; do not require every action to pass through a confirmation pane.
- **Contrast:** target at least 4.5:1 for ordinary text on its actual background
  and 3:1 for meaningful control boundaries and focus indicators. Put text on a
  reliable surface or scrim rather than assuming artwork will always be dark.
- **Layout:** the scene has priority on wide screens; the interaction panel has
  a comfortable reading width. On narrow screens, scene and interaction stack
  without hiding movement or requiring horizontal scrolling. Text zoom must not
  remove actions. Keep one copy of navigation for each purpose.
- **Motion:** restrained transitions that clarify change. Keep controls still
  while players read or act. Avoid continuous movement behind long text. Respect
  reduced motion; a static world must retain the same information and controls.

## Intention and recognition

Interpret an intention into a supported attempted action or sequence. Players may
understand ordinary mechanics, observe present conditions and develop expectations
through experience. The interface must not supply exact property deltas, guaranteed
success, future arrival routes or predicted alignment awards before commitment.

A clear intention can proceed when the player submits it to act. Ask a concise
clarifying question only when different interpretations would materially change
what they attempt. An unsupported intention must remain unsupported rather than
silently turning into another action. For example, “open this object without
destroying its pattern” must not silently map to Fracture when preserving the
pattern has no implemented expression.

Outcomes emerge from the committed action, the world conditions when it takes
effect, and other players' independent actions. Acceptance confirms an attempt
has entered the world; it does not guarantee the requested result. Delayed actions
may be aided, obstructed, overtaken or made moot as circumstances change. Describe
what actually happens as evidence becomes available, and retain the distinction
between an attempt, an ongoing consequence and a completed outcome in history.

This is a rule for both presentation and simulation. Hiding a preview while
freezing a forecast as the eventual outcome would not satisfy it. Preserve fair,
dependable mechanics and receipt/retry safety; uncertainty comes from the living
world and limited knowledge, not arbitrary changes to the rules after commitment.

Recognition must distinguish intended purpose, the action actually chosen and
what happened. Alignment can describe demonstrated tendencies across multiple
axes; contribution standings recognize eligible achievements. They are distinct,
as specified by [ADR-017](../decisions/ADR-017-multidimensional-leaderboards.md).
Do not reward eloquent intentions, assign a hidden morality total, or infer another
player's consent. Let a player understand and contest an interpretation. Keep
scoring detail optional so it does not turn every action into score optimization.

**Implemented in the Commit, then discover batch:** both clients commit labeled
suggestions directly in Act. Intention submission authorizes the attempted action;
material ambiguity returns a question in the same entry surface. The public preview
route is closed. New version 3 work stores an attempt, then computes material results
against live conditions at settlement. Only observed effects produce subsequent
work. Earlier accepted version 1/2 work and receipts retain their original meaning.

Four suggestions remain available even when a repeat attempt may be moot. A no-op
is an observed outcome, not a forecasted refusal. Combinations are optional and run
in order; a moot step does not cancel the remaining steps. History separates
acceptance, pending consequences and observed changes. Pending destination names
are not disclosed. Ordinary mechanics and present conditions remain available.

Intention parsing, clarification and refusal have deterministic provider-fixture
coverage; live-model interpretation quality remains unvalidated. The vocabulary
still bounds what an intention can attempt. Alignment and contribution scoring,
expanded agent/CLI vocabulary and interface restyling remain outside this batch.
This guide introduces no scoring rules or retroactive classification of players.

## First restyling pass

Define the shared visual vocabulary and demonstrate its changes across several
contrasting nodes before fixing token mappings. Connect typography, spacing,
controls, focus states and panel colors in the scene, map and shared Act component
through that vocabulary. Preserve the now-approved interaction structure.
Reduce the remaining terminal-like styling, improve secondary text legibility,
and make the intention disclosure feel as considered as the four action choices.
Reuse the same foundations in history and the guide when those surfaces are next
changed; do not block the focused pass on redesigning every auxiliary page.

Review the actual browser at narrow and wide widths, keyboard-only navigation,
text zoom and reduced motion. Review bright and dark scenes, no artwork,
unavailable actions, pending consequences and failed/retried submissions. A
restyling pass succeeds when it is easier to read and explore without adding
steps, competing controls or less room for imagination. Separately verify the
commit-and-discover behavior: a direct action has no mandatory preview, an ambiguous
intention clarifies only the attempted action, another player's intervening action
can affect a delayed result, and no pre-commit surface exposes future outcomes.

The next dedicated effort is scoped in [the session handoff](../roadmap/expressive-world-next-steps.md).
