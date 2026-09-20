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

The scene carries wonder; the interface makes participation easy. Keep a stable,
quiet visual language around a world that can become strange, turbulent or calm.
Changes in the world's mood should not make controls harder to find or read.

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
  target or scope. Clarification establishes what the player attempts, not what
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

**Current implementation gap:** the browser still requires a preview and exposes
material deltas and a future route. The owner's September 20 correction rejects
that behavior; the design above replaces that requirement, but removing it from
the runtime remains implementation work. Some delayed actions already resolve
against live conditions, which must be retained and extended rather than replaced
with promised outcomes. Intention-to-action proposal exists with a configured
model; explicit supported action sequences work without one. Alignment and
contribution scoring are not implemented by the current intervention path. This
guide introduces no scoring rules or retroactive classification of past players.

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
steps, competing controls or less room for imagination. Separately verify the
commit-and-discover behavior: a direct action has no mandatory preview, an ambiguous
intention clarifies only the attempted action, another player's intervening action
can affect a delayed result, and no pre-commit surface exposes future outcomes.
