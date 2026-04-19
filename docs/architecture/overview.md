# Architecture Overview

## Vision

A shared persistent multiverse inhabited simultaneously by human players and AI agents. The world is always running, always causal, always inhabited. The distinction between player, agent, and world node is deliberately porous.

---

## System Map

```
┌─────────────────────────────────────────────────────┐
│                     interface/                       │
│         visual layer · conversation · ambient        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                      server/                         │
│          WebSocket · REST API · event stream         │
└────┬──────────────┬──────────────┬───────────────────┘
     │              │              │
┌────▼────┐  ┌──────▼──────┐  ┌───▼──────────┐
│ agents/ │  │consciousness│  │  causality/  │
│ FSM     │  │ node voice  │  │ propagation  │
│ personas│  │ Claude layer│  │ engine       │
└────┬────┘  └──────┬──────┘  └───┬──────────┘
     │              │              │
┌────▼──────────────▼──────────────▼──────────┐
│                 multiverse/                  │
│        SpatialNode tree · world model        │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│                 persistence/                  │
│       world state · history · agent memory   │
└───────────────────────────────────────────────┘
```

---

## Components

### `multiverse/` — World Model
- **`node.py`** — `SpatialNode`: recursive data structure with name, level, children, properties, and interaction history
- **`generator.py`** — deterministic PCG with named locations, variable branching, and level-specific property templates

### `consciousness/` — Node Voice Layer
Claude-powered persona system. Each node's voice is seeded by its properties and interaction history. Nodes respond in character, reference past visitors, and hold perspective. Planned components:
- `persona.py` — maps node properties to Claude system prompts
- `memory.py` — per-node interaction history
- `voice.py` — conversation handler (Claude API integration)

### `causality/` — Causal Engine
Propagation system for cross-scale effects. Actions register as events; consequences travel up and down the hierarchy with dampening and delay. Planned components:
- `event.py` — causal event data model
- `propagation.py` — hierarchy traversal with dampening
- `registry.py` — event log and state tracking

### `agents/` — AI Agent System
- **`agent.py`** — `Agent` dataclass with FSM traversal, self-preservation logic, interaction logging
- **`behaviors.py`** — `State` enum, `transition()` function, behavioral predicates
- Planned: `persona.py` for Claude-powered agent personalities with goals and memory

### `persistence/` — World State
Planned: database layer for persistent world state, node history, agent memory, and causal event log. Enables the world to exist between sessions and across multiple simultaneous participants.

### `server/` — API Layer
Planned: real-time API for multi-participant synchronization. WebSocket event stream for causal propagation and presence. REST endpoints for world state queries.

### `interface/` — Visual & Interaction Layer
Planned: generative visual art responsive to world state. Multi-modal interaction (conversational, spatial, ambient). Distinct aesthetic vocabulary per scale level.

### `puzzles/` — Embedded Challenges
- **`types.py`** — `Puzzle` dataclass (kind, attempts, hints, result)
- **`engine.py`** — `PuzzleEngine`: attach, collect, run puzzles interactively
- Planned: causal integration — puzzle resolution propagates as causal events

---

## Interaction Patterns

All four patterns occur naturally within the same world model:

| Pattern | Mechanism |
|---------|-----------|
| Human → Human | Shared world state, cross-scale causality |
| Human → Agent | Direct conversation, shared traversal space |
| Agent → Human | Causal effects, node voice encounters |
| Agent → Agent | Shared traversal, goal conflict/cooperation |

---

## Data Flow

```
Participant (human or agent) enters world
        │
        ▼
Navigate hierarchy (spatial / conversational / ambient)
        │
        ├──► Interact with node ──► consciousness/ ──► Claude response in character
        │
        ├──► Trigger action ──► causality/ ──► propagate effects across scales
        │
        ├──► Encounter agent ──► agents/ ──► Claude-powered exchange
        │
        └──► All state changes ──► persistence/ ──► world evolves for all participants
```
