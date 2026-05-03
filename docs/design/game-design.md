# Game Design Document — Nested World Adventure

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

---

## Multiplayer Model

- Players explore independently — the experience does not depend on other players being online
- Optional cooperation when players share goals (puzzle solving, node exploration)
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

1. **Presence trails** — recent player and agent paths are subtly visible in scenes
2. **Agent visibility** — AI agents appear as visible presences in scenes, signaling activity worth investigating
3. **Node memory** — fragments of prior player interactions surface in the text panel and create narrative pull
4. **Hotspot affordance** — interactive elements have a consistent subtle visual treatment (parallax depth, material quality) that players learn to read over time
