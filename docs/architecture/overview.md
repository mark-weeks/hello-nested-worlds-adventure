# Architecture Overview

## Vision

A shared persistent multiverse inhabited simultaneously by human players and AI agents. The world is always running, always causal, always inhabited. The distinction between player, agent, and world node is deliberately porous.

---

## System Map

```
┌──────────────────────────┐  ┌──────────────────────────┐
│        interface/        │  │        frontend/         │
│  terminal REPL · spatial │  │  React + PixiJS browser  │
│  conversation · ambient  │  │  scenes · presence       │
└────────────┬─────────────┘  └────────────┬─────────────┘
             │                             │
             └──────────────┬──────────────┘
                            │
┌──────────────────────────▼──────────────────────────┐
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
- **`node.py`** — `SpatialNode`: recursive data structure with id, name, level, children, properties; per-node interaction history is stored in `persistence/` (`world_mutations` table) and accessed via `persistence.get_node_history`
- **`generator.py`** — deterministic PCG with named locations, variable branching, and level-specific property templates
- **`utils.py`** — tree helpers: `count_nodes`, `find_node`, `build_depth_map`

### `consciousness/` — Node Voice Layer
Claude-powered persona system. Each node's voice is seeded by its level, properties, and accumulated interaction history. Nodes respond in character, reference past visitors, and hold perspective on their place in the hierarchy.
- `LEVEL_VOICES` — per-scale character notes covering all 11 levels (Multiverse → SubatomicParticle); pronouns, time-sense, and sensory vocabulary all shift by scale
- `speak(node, message, history)` — three system blocks (universal preamble + per-level voice + per-node context) with two prompt-cache breakpoints, so calls within the same level share the longer cached prefix
- `voice_agent(persona, agent_name, node, message)` — speaks AS an agent visiting a node, framed by the persona's voice preamble (distinct system prompt from `speak()`)
- Thread-safe lazy `Anthropic` client init; sanitises inbound message text

### `causality/` — Causal Engine
Propagation system for cross-scale effects. Actions register as events; consequences travel up and down the hierarchy with depth-based dampening.
- `EventKind`, `CausalEvent` — event taxonomy and data model
- `CausalityBus` — handler registry and event log
- `emit(...)` — fire at one node, no cascade
- `propagate(origin, kind, dampening, direction="both")` — origin fires once, then cascades up the parent chain and/or down the child subtree depending on `direction`. Strength attenuates by `dampening` per hop and the cascade halts at `MIN_STRENGTH`
- Each fire bumps `node.ripple_score` proportional to the event's (already-dampened) strength, clamped to 1.0
- Wired into the WebSocket server: emitted events fan out to all connected clients

### `agents/` — AI Agent System
- **`agent.py`** — `Agent` dataclass with FSM traversal, self-preservation logic, interaction logging, persistent memory across runs, and agent-to-agent encounter handling
- **`behaviors.py`** — `State` enum, `transition()` function, behavioral predicates
- **`personas.py`** — four archetypes (*tender, destabilizer, scholar, wanderer*) plus `for_name()` (deterministic sha1-keyed pick) and `by_name()` (explicit lookup). Each carries a voice preamble used by `consciousness.voice_agent`. Personas are surfaced in log entries, causal-event payloads, encounter broadcasts, and `world_mutations`

### `persistence/` — World State
SQLite-backed store. Enables the world to exist between sessions and across multiple simultaneous participants.
- `save_world` / `list_worlds` — generation parameters and node counts
- `save_agent_run` / `get_agent_runs` — per-run traversal events
- `save_agent_memory` / `load_agent_memory` / `list_agent_memories` — persistent agent knowledge of visited nodes
- `record_mutation` / `get_mutations` — world-state changes from interaction
- `get_node_history` — interaction transcript per node, fed back into consciousness prompts
- `cache_image` / `get_cached_image` — scene-image cache keyed by node signature
- `save_puzzle_result` — server-side puzzle outcome record

### `server/` — API Layer
Threaded `http.server` with REST + WebSocket support, security headers (CSP, X-Frame-Options, etc.), and POST/frame size caps.
- **REST**: `/health`, `/worlds`, `/world`, `/players`, `/history`, `/agent`, `/observe`, `/puzzle`, `/image`, plus `POST /speak`, `POST /puzzle/attempt`, and `POST /agent/voice`
- **WebSocket** (`/ws`): presence, player-to-player chat, broadcast of causal events, ping/keepalive
- **Static**: bundled D3 browser UI mounted at `/app`; easter-egg routes under `/easter-egg/`
- Module split: `handlers.py` (HTTP/WebSocket dispatch), `protocol.py` (frame parsing), `rooms.py` (presence + co-op `PuzzleSession` state), `imageprompt.py` (per-level prompt assembly + style-signature cache key)

### `interface/` — Terminal Interaction Layer
Interactive terminal session (`run_session`) with three modes — spatial (`go`/`up`/`map`), conversational (`speak`), and ambient (`observe`) — plus inline puzzles. Each scale level renders in a distinct ANSI colour.

### `frontend/` — Browser Client
React + PixiJS + Vite app that talks to the WebSocket server. Renders fal.ai-generated scene backgrounds, hotspot interactions, multiplayer presence, and live causal-event ripples. A complementary vanilla D3 tree explorer is served from `static/app/`.

### `puzzles/` — Embedded Challenges
- **`types.py`** — `Puzzle` dataclass (kind, attempts, hints, result)
- **`engine.py`** — `PuzzleEngine` (attach, collect, run) plus an `_LEVEL_DYNAMIC` dispatch with property-driven generators for all 11 levels: Multiverse anagram, Universe dark-matter logic, Galaxy shape riddle, Planetary System halved-orbit logic, Planet biome riddle, Region danger lock, Room navigation, Object weight logic, Molecule bond logic, Atom proton logic, SubatomicParticle riddle
- **`data.py`** — static fallback pools, plus poetic clue maps (`BIOME_CLUES`, `GALAXY_SHAPE_CLUES`, `PARTICLE_TYPE_CLUES`) used by the riddle generators
- Server validates attempts so the answer never leaves the server

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
