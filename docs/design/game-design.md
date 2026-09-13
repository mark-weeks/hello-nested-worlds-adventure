# Game Design Document — Enfolded: Nested World Adventure

The September 12 discovery/return slice implements one bounded shared signal
investigation in existing places ([ADR-025](../decisions/ADR-025-first-situation.md)).
Preserving keeper control and releasing the signal have different beneficiaries
and costs. A shared decision window produces lasting consequences; late arrivals
investigate the aftermath. The scene client leads this experience, with journals
and selectively published profiles under [ADR-024](../decisions/ADR-024-participants-and-active-content.md).
This is implemented scope, not evidence of retention or approval of rankings,
guilds, disposition meters, voice input or a general inventory system.

---

## Product direction and implementation status

The next milestone is a compelling discovery-and-return experience in the same
shared world, with a private journal and a separate public identity. The
[delivery plan](../roadmap/discovery-and-return.md) sequences that work and
records the distinction between owner-endorsed direction, proposed contracts, and
candidate extensions. ADR-012 through ADR-018 cover discovery, continuity,
identity, referential puzzles, optional spoken interaction, and multidimensional
contribution leaderboards, plus a proposed collection and assembly direction.

The mechanics below describe the existing implementation unless labeled planned.
The first situation and new identity/speech capabilities are not shipped.

## Core Interaction Model

The scene client (`/app`) presents the current place with local generative art,
optional generated imagery, and clickable passages. The explorer (`/`) remains
the default invite destination under ADR-005. Both access the same world; neither
has character movement within a node.

Planned under [ADR-012](../decisions/ADR-012-discovery-and-return.md): develop the
next experience primarily in the scene client, emphasizing an active situation,
presences, and legible interventions. Promote it to the default only after the
specified device/accessibility checks and an explicit ADR-005 update. Curated
entry must reflect current shared state, preserve per-node difficulty, and leave
players free to explore, converse, or observe.

---

## Scale-Native Verbs

Each of the 11 levels has exactly one verb — an act that only works at that scale (`multiverse/verbs.py`, POST `/act`, CLI `act`):

| Scale | Verb | What it does |
|---|---|---|
| Multiverse | **attune** | repairs stability: collapsing → fraying → stable |
| Universe | **calibrate** | nudges `dark_matter_ratio` toward 0.5 |
| Galaxy | **kindle** | raises `star_density` ~5% |
| Planetary System | **align** | flattens the ecliptic tilt 10% |
| Planet | **seed** | wakes life on a barren world; swells it where it holds |
| Region | **ward** | lowers `danger_level` (floor 1) |
| Room | **inscribe** | increments a permanent `inscriptions` counter |
| Object | **mend** | repairs condition: corrupted → damaged → worn → pristine |
| Molecule | **catalyze** | adds a bond (cap 12) |
| Atom | **excite** | ionizes; shifts resonance blueward |
| SubatomicParticle | **observe** | collapses a superposed spin (deterministic per observer+particle) |

Design intent: every verb is the **restorative counterpart** to the decay events in `multiverse/effects.py` — STRUCTURAL_CHANGE corrodes, `mend` repairs; DANGER_ALERT roughens, `ward` calms. The world drifts toward entropy; players push back one scale at a time. The verb's material change applies exactly once at the origin (the producer owns the flavor line); the act then rides the standard causal rails — chronicle entry, ripple, staged cascade — so a mend is felt, faintly and later, by the room that holds the object and the molecules inside it.

**Planned extension.** ADR-012 retains this scale vocabulary but adds contextual
trade-offs through targets, sequence, and situation commitments. ADR-013 defines
explicit contribution, one-time, and exclusive-action semantics; those changes
are pending implementation and must preserve existing accepted work.
The ADR-017 proposal requires legitimate destabilizing or opposing goals
alongside preservation, with authored stakes and shared conflict rules. The
current restorative verbs alone do not establish those new goals or authorities.

**Implementation status.** Live in all three clients: `/app` gets a per-scale Act tab, the explorer an Act mode panel, the CLI an `act` command (typing the verb itself also works). Acts broadcast to the seed-room (`scale_act`), fold into watching clients' property panels and node art, and land in `/history` backfill.

---

## Node Hierarchy

The full hierarchy has eleven scales; this is an illustrative aesthetic excerpt.

```
Cosmic / Multiverse  →  abstract, luminous, vast
  Galaxy             →  dreamy, soft light, deep color
    Region           →  painterly, atmospheric, grounded
      Room           →  style varies by node properties (see style matrix)
        Object       →  hyper-detailed, intimate, close
```

---

## Adaptive Style System

Node visual style is programmatically determined by a property matrix. Style drifts over time with node state — it does not snap. This drift is a feature, not a bug.

| Property | Style Signal |
|----------|-------------|
| High conflict history | Noir, chiaroscuro, shadow-heavy |
| Heavy AI agent activity | Surreal, geometry-distorted |
| Player cooperation | Warm, impressionist, layered |
| Pristine / undiscovered | Ethereal, minimal, clean |
| Corrupted / destructive | Glitch art, dark expressionist |
| Puzzle node | Escher-like, geometric, op art |
| High ripple weight | Psychedelic, saturated, unstable |

> **Implementation status.** Wired in `server/imageprompt.py`. All seven matrix rows are live (heavy AI agent activity, conflict history, cooperation, pristine, corrupted, puzzle, high ripple weight). The high-ripple row reads the PERSISTED `ripple_score` (`node_runtime_state`, incremented atomically on every causal fire and rehydrated onto the tree at each rebuild). Per-level baselines (`HIERARCHY_STYLES`) cover all 11 scales, and the cache key folds in a style signature so visuals refresh whenever the modifier set flips — not only when raw history count crosses a 5-event bucket. Beyond style, causal events now change node substance directly (`multiverse/effects.py`): puzzle solves stabilize and calm danger, danger alerts roughen it, structural change degrades condition — persisted as a property overlay and visible to every participant.

---

## Multiplayer Model

- Players explore independently — the experience does not depend on other players being online
- **Cooperative puzzle solving** is wired in via shared puzzle sessions (`server/rooms.py::PuzzleSession`): every `/puzzle/attempt` against the same `(seed, node)` pools attempts and contributors across all players in the room. The attempt counter advances for the room (not per-player); once any one player guesses correctly, the puzzle is marked solved for everyone present and the broadcast carries the solver plus the full contributor list. Visual presence trails and goal-sharing UI remain Phase 2.
- All four interaction patterns are supported: human:human, human:AI, AI:human, AI:AI
- Player and agent presence is visually represented in scenes (markers, figures, trails)
- Actions by any player or agent ripple through the multiverse with a dampening effect stored in node history

---

## World Persistence

- Nodes persist but evolve over time based on interaction history
- Ripple effects from actions at one node propagate to connected nodes with dampening
- The canonical world is finite and materialized at birth; born identities stay fixed. Ongoing substance uses recorded overlays. The traversal loop closes the hierarchy without creating new geography. Deliberate new situations and active-work versioning are planned under ADR-013.
- Players can return to previously visited nodes; those nodes may look different

---

## Solving the Myst Problem (Discoverability)

The original Myst suffered from unclear navigation and opaque objectives. Four design responses:

1. **Presence trails** — recent player and agent paths are subtly visible in scenes. *Implemented (in-scene v1)*: each player at the current node renders as a colored marker with a name tag (palette is hashed from the name so the same person looks the same across sessions). Agent activity surfaces as causal ripples in the scene the moment an event fires there.
2. **Agent visibility** — AI agents appear as visible presences in scenes, signaling activity worth investigating. *Implemented (in-scene v1)*: when two agents meet at the current node, the scene briefly shows a converging-glyph encounter mark. Persistent in-scene agent figures (between events) remain Phase 2.
3. **Node memory** — fragments of prior player interactions surface in the text panel and create narrative pull. *Implemented* — the broader `record_mutation` coverage feeds `consciousness.speak()` via `get_node_history`.
4. **Hotspot affordance** — interactive elements have a consistent subtle visual treatment (parallax depth, material quality) that players learn to read over time. *Implemented (in-scene v1)*: each hotspot in `frontend/src/components/SceneView.jsx` renders as a layered plate — soft cast shadow underneath, dark surface, single-pixel top-edge highlight (suggesting light from above), and an outlined border that brightens on hover while the shadow tightens, reading as a gentle press. The treatment is shared across every child level so the affordance generalizes.


## Planned capabilities and collection proposal

- [ADR-014](../decisions/ADR-014-player-identity-and-journal.md): private journal
  plus selective public bio/goals, home bookmark, and chosen avatar. Badges,
  dynamic disposition meters, avatar creation/upload, and guilds are staged
  candidates. Proposed opposing tendencies remain separate from achievement;
  mixed evidence and unknown disposition must not be presented as equivalent.
- [ADR-015](../decisions/ADR-015-referential-puzzles.md): occasional relevant
  fictional/nonfictional references, initially optional, with verified sources,
  explicit answers, and preserved puzzle ecology and active-instance identity.
- [ADR-016](../decisions/ADR-016-optional-spoken-interaction.md): optional speech
  input and playback alongside complete text interaction. Current generated
  character text and ambient sound are not yet this speech capability.
- [ADR-017](../decisions/ADR-017-multidimensional-leaderboards.md): separate
  contribution standings with comparable scoring opportunities for humans and
  eligible agents. Stewardship and Disruption are the first proposed
  pair, after meaningful opposing goals and their evidence exist. Cooperation
  can serve either goal; no alignment-extremity score, flat engagement total,
  or credit for simulated agent puzzle solves.
- [ADR-018](../decisions/ADR-018-collectibles-and-inventory.md): proposed keepsakes,
  components from different scales, and assembled artifacts with useful abilities.
  Review one small assembly within the first mystery before adding inventory to
  its scope. Travel abilities need a distinct benefit beyond existing jumps and
  explicit movement rules; a broader crafting economy remains deferred.
