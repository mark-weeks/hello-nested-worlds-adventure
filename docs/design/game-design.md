# Game Design Document — Enfolded: Nested World Adventure

---

## Core Interaction Model

Point-and-click adventure. Players see an AI-generated scene of the current node. Clickable hotspots within the scene navigate to connected nodes (objects, doors, portals, passages). No character movement within a node. Optional left/right pan for wide-format scenes.

---

## Node Hierarchy

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

> **Implementation status.** Wired in `server/imageprompt.py`. All seven matrix rows are live (heavy AI agent activity, conflict history, cooperation, pristine, corrupted, puzzle, high ripple weight). The high-ripple row currently uses total `world_mutations` count as a proxy for the in-memory `ripple_score`, since ripple_score isn't persisted across requests yet; the matrix delivers the same visual behaviour either way. Per-level baselines (`HIERARCHY_STYLES`) cover all 11 scales, and the cache key folds in a style signature so visuals refresh whenever the modifier set flips — not only when raw history count crosses a 5-event bucket.

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
- The multiverse is conceptually infinite but rendered lazily — only discovered or reachable nodes are loaded
- Players can return to previously visited nodes; those nodes may look different

---

## Solving the Myst Problem (Discoverability)

The original Myst suffered from unclear navigation and opaque objectives. Four design responses:

1. **Presence trails** — recent player and agent paths are subtly visible in scenes. *Implemented (in-scene v1)*: each player at the current node renders as a colored marker with a name tag (palette is hashed from the name so the same person looks the same across sessions). Agent activity surfaces as causal ripples in the scene the moment an event fires there.
2. **Agent visibility** — AI agents appear as visible presences in scenes, signaling activity worth investigating. *Implemented (in-scene v1)*: when two agents meet at the current node, the scene briefly shows a converging-glyph encounter mark. Persistent in-scene agent figures (between events) remain Phase 2.
3. **Node memory** — fragments of prior player interactions surface in the text panel and create narrative pull. *Implemented* — the broader `record_mutation` coverage feeds `consciousness.speak()` via `get_node_history`.
4. **Hotspot affordance** — interactive elements have a consistent subtle visual treatment (parallax depth, material quality) that players learn to read over time. *Implemented (in-scene v1)*: each hotspot in `frontend/src/components/SceneView.jsx` renders as a layered plate — soft cast shadow underneath, dark surface, single-pixel top-edge highlight (suggesting light from above), and an outlined border that brightens on hover while the shadow tightens, reading as a gentle press. The treatment is shared across every child level so the affordance generalizes.
