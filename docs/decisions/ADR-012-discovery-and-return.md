# ADR-012: Discovery and Return as the Next Product Milestone

**Status:** Accepted as product direction, 2026-09-07; implementation pending.
The owner endorsed the recommendations following PR #92 and requested a formal
plan. The example situation, presentation choice, and pacing remain hypotheses
to test. This records direction, not a completed feature or a new write path.

## Context

The [concept-versus-code assessment](../evaluation/2026-09-07-concept-and-implementation.md)
found a strong continuity foundation but weak reasons to act and return.
More geography, puzzle variants, or retained history alone do not make a
consequence understandable or personally meaningful.

Enfolded's center remains a shared, persistent world inhabited by humans and
agents, with discovery across scales and deliberately porous distinctions
between inhabitants and places. Investigation is an invitation into that world;
conversation, experimentation, and quiet observation remain valid participation.

## Decision

Make **understanding the world and developing relationships with it** the main
form of progress. The next milestone is one compelling first session followed
by one meaningful return to the same continuing world.

| Choice | Direction |
|---|---|
| Initial motivation | A shared investigation with a legible question and freedom to leave; no compulsory quest sequence. |
| Scope | Approximately 8–15 connected existing places across 3–4 scales, with one recurring inhabitant, an earlier visitor's trace, two materially different interventions, one visible delayed consequence, and a further question. |
| Meaningful action | Preserve scale-native verbs; let target, sequence, and explicit commitments create contextual trade-offs. Add a small situation-specific choice only when the experience requires it. |
| Entry | Curate an accessible arrival into a currently relevant shared situation. Honor seals, per-node difficulty, and returning-player resume. Do not present a resolved situation as still awaiting its original solution. |
| Inhabitants | Bounded persistent goals, selective memories, and executable commitments. Rules authorize action; language models interpret and express it. Agents can disagree without becoming omniscient quest dispensers. |
| Time | The shared world continues between sessions. Bound its progression, preserve evidence of missed developments, and avoid turning absence into an endless repair obligation. |
| Renewal | New questions and relationships in familiar places before additional geography. Start with authored situations; generalize only patterns that prove useful in play. |
| Identity and return | A private journal and a separate, player-controlled public identity, as staged in ADR-014. |

### Presentation decision and its boundary

Develop the next experience primarily in `/app`, with the place, its presences,
and available interventions ahead of raw properties. Keep a map for orientation
and usable text/keyboard controls for the full interaction path. Reuse existing
art, sound, and shared domain logic rather than building a new renderer.

ADR-005's explorer-default invite policy remains in force. Promoting `/app` to
the default requires the slice's mobile, navigation, keyboard, and rendering
fallback checks plus an explicit update to ADR-005. Maintain existing explorer
behavior; require correct shared rules without duplicating every new layout.

### Working first-situation brief

An instrument carries a recurring signal through a room into its surrounding
region. The signal disturbs an inhabitant but also carries a fragment of an
earlier visitor's discovery. Investigation reveals the relationship. One
intervention quiets the source; another changes how the signal travels.

Both choices must have understandable benefits and costs, visible material
consequences, and a distinct aftermath. A later visitor can reconstruct what
happened and influence that aftermath. Do not reset the original mystery for
each visitor or imply that everyone was its first solver. This is proposed
content, not a description of the seeded world's existing behavior.

## Trade-offs accepted

- Authored situations cost design time but provide a concrete test of the
  concept. Unrestricted simulation and autonomous content generation remain
  possible later investments, not prerequisites for this milestone.
- Contextual trade-offs extend the uniformly restorative framing of current
  verbs. The affected relationships and acceptance rules must be made legible;
  surprise should come from discovery, not arbitrary rule changes.
- Personal understanding can deepen after a shared puzzle is solved. The game
  must give late arrivals consequential follow-up opportunities, not just an
  archive of content other people completed.
- A scene-focused development cycle has device and accessibility costs. The
  existing default remains available until those costs are validated.

## Revisit when…

- Players cannot identify an investigation or explain its consequences: revise
  the situation and presentation before expanding content or infrastructure.
- Players consistently prefer observation or conversation to the mystery:
  strengthen those paths without making the investigation mandatory.
- Familiar places support meaningful return and show actual spatial exhaustion:
  consider bounded breadth growth under a separate evolution decision.

## Rejected alternatives

- A required linear campaign as the whole game: narrows non-linear participation.
- A general RPG economy, levels, or leaderboard as the first retention fix:
  changes incentives before proving the world's distinctive value.
- More scales, independent player worlds, or parallel client redesigns now:
  increase scope or fragment the shared experience.

Delivery order, owners, and proposed pilot gates live in the
[discovery-and-return plan](../roadmap/discovery-and-return.md).
