# ADR-018: Collectibles, Assembly, and Earned Capabilities

**Status:** Proposed, 2026-09-07; no implementation or final product decision.
The owner raised collection from visited nodes, inventory combinations that open
passages, hyperleaping, and assembling parts into something useful. The design
below is a recommendation for discussion, not an endorsement of every mechanic.

## Context

Collection could connect exploration, personal identity, and unfinished goals.
Its value depends on what a discovery lets a player understand or do. An inventory
full of interchangeable rewards would add chores without making the world more
interesting. Enfolded's distinctive opportunity is to combine discoveries from
different scales into a meaningful intervention in the same persistent world.

The existing scene client can jump to another traveler's location
(`frontend/src/App.jsx`, `jumpTo`). WebSocket moves and saved positions validate
the target and seals without requiring adjacent movement (`server/websocket.py`,
`server/handlers.py`). An item-gated hyperleap is therefore not yet an enforceable
exclusive ability. Its added value and any change to ordinary movement need an
explicit cross-client contract before implementation.

## Decision

### Recommended collection model

| Kind | Purpose | Recommended first rule |
|---|---|---|
| Keepsake or imprint | Carries a place's story into the player's collection and optional public identity. | Earn through a meaningful observation or interaction; record source and context. No mechanical power or reward for every visit. |
| Component or pattern | Connects clues from different nodes and scales toward a legible project. | A small authored set with understandable roles. Show discovered clues and missing functions without revealing unvisited answers or requiring random combination attempts. |
| Assembled artifact | Creates a durable way to investigate, intervene, or eventually travel. | One useful capability with understandable limits. Prefer reusable tools over escalating stats or routine fuel grinding. |

These are roles, not three independent inventory systems. Use a small collection
with provenance. Distinguish a journal's account of a discovery from the server's
record of a usable item; writing a note must not mint a component or grant access.

### First candidate: one instrument, three discoveries

Consider a **resonance instrument** within ADR-012's first situation: recover a
resonant fragment at an object, capture a tuning pattern in its room, and obtain
a reference signal at a regional node. The three discoveries explain different
parts of the disturbance. Assembly reveals its causal trail and supports the
existing choice to quiet or redirect the signal. The earlier visitor's trace
can supply a clue without removing the next player's opportunity to investigate.

This is an illustrative story, not approved node content or a mandatory new gate.
Make an unfinished instrument legible within the first session and give each
part an immediate clue; do not require completing a fetch list before anything
interesting happens. Preserve meaningful observation and conversation without
requiring everyone to become a collector. Later situations can give a familiar
artifact a new application while preserving what it already does.

Review this variation in M0. Include it in M5 only if it strengthens the mystery
enough to justify the added persistent state; otherwise test it after M7. Start
with three components, one recipe, and one artifact as scope hypotheses. Shared
construction projects and additional recipes follow evidence of useful play.

### Openings, travel, and shared projects

- **Openings:** a combination may enable an explicitly authored route or action
  at existing nodes. State whether the resulting access is personal or communal.
  Prefer communal consequences for a shared intervention, with personal keepsakes
  and contribution credit. Inventory must not fabricate a puzzle solve or silently
  bypass existing LOCK seals; any alternative seal condition needs separate review.
  New geography remains outside ADR-013's first scope.
- **Hyperleaping:** defer until travel friction is observed. A candidate is a
  reusable artifact that returns its owner to previously visited, deliberately
  attuned anchors without needing another traveler there. Compare that benefit
  with existing navigation before building it; do not silently withdraw existing
  jumps. Define and enforce eligibility across all movement/resume surfaces if
  it becomes a game rule. Respect current seals, free exit, canonical ancestry,
  and the pinned wrap hinge. A profile's home bookmark grants no travel ability.
- **Shared assembly:** later, a group might build an observatory or stabilize a
  passage. Show what each contribution does and distribute credit for complementary
  work, with a bounded outcome budget. A completed project stays completed; late
  arrivals can investigate, use, or extend it under a new explicit objective.
  Avoid repeatedly breaking projects merely to create maintenance chores.

### Ownership and continuity boundaries

- Collect samples, patterns, or separately modeled portable items linked to a
  source. Never move, delete, or reparent a born spatial node into an inventory.
  A shared world can support personal holdings without creating private worlds.
- First-situation essentials should be independently earnable by later visitors.
  Continuous agents or early players must not exhaust core components for everyone
  else. Defer scarce transferable resources, trading, auctions, and theft. Agents
  need explicit authorized acquisition/action rules; simulated puzzle success is
  not an entitlement to human-gated components or indirect achievement credit.
- Default to reusable patterns/tools. If a recipe consumes components, explain it
  before committing, preserve their acquisition/assembly lineage, and provide a
  defined recovery path where they remain needed. Do not strand a participant
  through an irreversible recipe choice or a subsequent content update.
- Persist holdings and capability grants under stable authenticated owners, with
  server-validated acquisition evidence and versioned item/recipe definitions.
  Acquisition, consumption, assembly, and shared unlocks need atomic, idempotent
  transitions under ADR-013. Test retries, simultaneous claims/crafts, restart,
  restore, and recipe updates with existing holdings before any live release.
- Inventory is owner-visible by default; selected keepsakes/artifacts may be
  displayed through ADR-014. A public world contribution retains the existing
  history policy. ADR-017 recognizes verified outcomes, not inventory size,
  rarity, repeated harvesting, or collect/craft loops. Basic discovery must remain
  possible without joining a leaderboard or disclosing private holdings.

## Trade-offs accepted

- Authored combinations offer clearer meaning but cost more to design than random
  loot. Generalize only after several examples justify a crafting system.
- Personal access to essential components reduces scarcity and a potential trading
  economy, while preserving discovery for late entrants and intermittent humans.
- Durable capabilities support attachment but can trivialize later content. Use
  contextual applications and new questions before adding power inflation.
- Assembly adds goal clarity but can turn curiosity into checklist completion.
  Pilot evidence must show players understand the relationships between the parts.

## Revisit when…

- **Owner/team accepts or changes the proposal** → record the ratification date,
  adopted scope, and any remaining proposals before implementation.
- **M0 walkthrough shows assembly strengthens the mystery** → consider the bounded
  recipe for M5, comparing it with the simpler situation. Check whether players
  explain why parts fit, use the artifact meaningfully, and have a reason to return
  beyond filling slots; defer until after M7 if the benefit is not demonstrated.
- **Pilot participants identify travel friction** → evaluate attuned-anchor travel
  against existing jumps and define the movement contract before adding hyperleaps.
- **Collection becomes clutter or repetitive work** → simplify acquisition, recipes,
  and display before expanding the inventory.
- **Recurring demand for shared projects emerges** → define one bounded project,
  contribution rules, and late-arrival opportunities. Test an empty-handed entrant
  after humans or agents finish the project before broadening shared assembly.

## Rejected alternatives

- A collectible at every node, random rarity tiers, or a universal inventory score.
- Exhaustible core keys that let early players or agents lock everyone else out.
- A broad crafting economy or mandatory assembly system before a compelling scene.
- Calling existing unrestricted movement an earned exclusive power without changing
  its actual authority, or introducing a travel restriction without product review.
