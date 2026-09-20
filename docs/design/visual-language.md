# Enfolded visual language

**2026-09-20 · first style guide.** The interaction principles below reflect the
owner's explicit direction. Palette, typography and composition are proposed
restyling targets; they are not a claim that both clients already implement them.
Artwork production is covered in [the beta art strategy](beta-scene-art.md).

## Experience

Make the interface as simple as possible while giving players room to act
imaginatively. Guide through possibilities, context and readable consequences.
A player should feel invited to explore, not assigned a sequence to complete.

The scene carries wonder; the interface makes participation easy. Keep a stable,
quiet visual language around a world that can become strange, turbulent or calm.
Changes in the world's mood should not make controls harder to find or read.

- Preserve Speak | Puzzle | Act as the primary interaction structure.
- Present four useful, scale-native actions as invitations into possibility.
  Four visible suggestions are not a permanent limit on the world's vocabulary.
- Keep **Describe an intention** in Act. It is an equally valid way to begin,
  visually easy to discover without a second composer or persistent extra panel.
- Reveal combinations, detailed conditions and causal routes when requested.
- A preview shows the proposed action, material consequences and consequential
  uncertainty. The player can revise or decline it before committing.
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

Preserve negative space for titles and navigation in image composition. Artwork
contains no interface text. Legibility must survive the brightest approved image,
a different crop, a narrow screen and an unavailable image.

## Interface foundations

Use named shared tokens when implementing these values, including inside the Act
component's shadow root. Do not add another layer of hard-coded component colors.
These are interface colors; node-derived scene colors remain independent.

| Token | Starting value | Role |
|---|---|---|
| Canvas | `#081316` | Deep neutral background |
| Surface | `#122622` | Quiet panels and secondary controls |
| Text | `#F3E5CF` | Main text |
| Secondary text | `#B3C9C4` | Supporting copy that remains readable |
| Accent | `#E2C790` | Focus and the current commitment |
| Link | `#81C9D0` | Navigation and interactive references |
| Attention | `#F3B9A3` | Recoverable problems or consequential caution |

Color never carries meaning alone. Avoid coding restoration as virtuous green
and disruption as morally bad red. Selected, unavailable, pending and failed
states need text or shape as well as color. Unavailable actions should explain why;
reduced opacity alone is insufficient.

- **Type:** a restrained serif for place names and short atmospheric lines; a
  readable sans serif for controls, explanations and history. Reserve monospace
  for addresses and technical identifiers, shown only when useful. Start with
  Georgia and the system sans stack to avoid a new font-loading dependency.
- **Size:** 16px body text, 14–16px action labels, 12–13px secondary metadata,
  responsive 30–64px scene titles. Do not use tiny spaced capitals for sentences
  or essential controls. Keep body line height around 1.5.
- **Spacing:** a 4/8/12/16/24/32/48px scale. Group related content with space;
  borders are reserved for useful boundaries rather than every line of data.
- **Controls:** at least 44px interaction height as a design target, a consistent
  4px corner radius, clear keyboard focus, and one visual hierarchy. A primary
  button appears when a specific commitment is ready, not before an intention.
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

Interpretation proposes a supported action or sequence, explains its likely
consequences and leaves commitment with the player. An unclear or unsupported
intention should invite clarification, not silently become an approximate action.
For example, “open this object without destroying its pattern” must not silently
map to Fracture when preserving the pattern has no implemented consequence.

Recognition must distinguish intended purpose, the action actually chosen and
what happened. Alignment can describe demonstrated tendencies across multiple
axes; contribution standings recognize eligible achievements. They are distinct,
as specified by [ADR-017](../decisions/ADR-017-multidimensional-leaderboards.md).
Do not reward eloquent intentions, assign a hidden morality total, or infer another
player's consent. Let a player understand and contest an interpretation. Keep
scoring detail optional so it does not turn every action into score optimization.

**Current limit:** intention-to-action proposal exists with a configured model;
explicit supported action sequences work without one. Alignment and contribution
scoring are not implemented by the current intervention path. This guide does not
introduce scoring rules or retroactively classify past players.

## First restyling pass

Unify typography, spacing, controls, focus states and panel colors in the scene,
map and shared Act component. Preserve the now-approved interaction structure.
Reduce the remaining terminal-like styling, improve secondary text legibility,
and make the intention disclosure feel as considered as the four action choices.
Reuse the same foundations in history and the guide when those surfaces are next
changed; do not block the focused pass on redesigning every auxiliary page.

Review the actual browser at narrow and wide widths, keyboard-only navigation,
text zoom and reduced motion. Review bright and dark scenes, no artwork,
unavailable actions, pending consequences and failed/retried submissions. A
restyling pass succeeds when it is easier to read and explore without adding
steps, competing controls or less room for imagination.
