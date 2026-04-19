# Nested Worlds Adventure

**A shared persistent multiverse inhabited simultaneously by human players and AI agents.**

---

## Concept

Nested Worlds Adventure is an environment where the boundary between player, agent, and world is deliberately blurred.

The multiverse is always running. You enter and find it already in motion — other humans and AI agents traversing different scales, each leaving traces the world carries forward. You may never encounter another player directly, but you will feel the consequences of their presence through cross-scale causality: a destabilized atom cascading into a volatile region, a solved puzzle stabilizing a galaxy, an agent's curiosity reshaping a planet's danger over time.

Every node in the hierarchy is a perspective, not just a data structure. The Vault speaks from its history. The Mire remembers who passed through. Nodes are animated by Claude and respond in character — their voice seeded by accumulated properties and interaction history. Talking to a node is a way of learning what it *is*. Whether you're speaking to a world node or an AI agent who has settled into one is a question the system leaves deliberately open.

Interaction is multi-modal: natural language for depth, visual navigation for movement, ambient observation for those who want to watch the world evolve without directing it. The visual layer is a piece of generative art that responds to world state — causal events visible as ripples, other presences as signatures in the field.

---

## Architecture

### The Hierarchy

Ten nested scales, each with its own aesthetic register and causal weight:

```
Multiverse → Universe → Galaxy → Planetary System → Planet → Region → Room → Object → Molecule → Atom → SubatomicParticle
```

### Core Systems

**World Model** (`multiverse/`)
The persistent spatial hierarchy. Nodes carry level-specific properties, accumulated interaction history, and causal state. The generator seeds the world deterministically; everything after that is live.

**Node Consciousness** (`consciousness/`)
The Claude-powered voice layer. Each node has a persona derived from its properties and history. Nodes respond in character to direct interaction, reference past visitors, and hold perspective on their place in the hierarchy. The line between animated world and inhabiting agent is intentionally porous.

**Causality Engine** (`causality/`)
A propagation system that carries effects up and down the hierarchy with dampening and delay. Actions register as causal events; the engine resolves their consequences across scales over time. Players and agents shape each other's experiences without necessarily meeting.

**Agents** (`agents/`)
Claude-powered entities with distinct personalities, goals, and relationships to specific nodes and scales. Agents traverse the world, interact with nodes and each other, accumulate memory, and can be engaged in conversation. Some destabilize; some tend. Their behavior is driven by goals and shaped by world state.

**Persistence** (`persistence/`)
World state lives in a database. The multiverse exists between sessions. Interaction history, causal state, and agent memory persist. Multiple participants can be present simultaneously.

**Server** (`server/`)
Real-time API layer. WebSocket-based synchronization for multi-participant presence. Event stream for causal propagation. REST endpoints for world state queries.

**Interface** (`interface/`)
The visual and interaction layer. Generative art that reflects world state at each scale. Multi-modal interaction: conversational, spatial, ambient. Each scale has a distinct aesthetic vocabulary.

**Puzzles** (`puzzles/`)
Embedded challenges that interact with the causal system. Solving a puzzle isn't just a local event — its resolution propagates. Puzzles are voiced by their containing nodes.

---

## Interaction Modes

| Mode | Description |
|------|-------------|
| Conversational | Natural language exchange with nodes and agents |
| Spatial | Visual navigation through the hierarchy |
| Causal | Observing and triggering cross-scale effects |
| Ambient | Passive presence — watching the world evolve |

---

## What Makes This Different

Most games separate human players from AI. Most simulations exclude humans or treat them as inputs. Most interactive fiction is single-player and deterministic.

This is a **shared consciousness space** — always inhabited, always causal, where the distinction between player, agent, and world is part of the experience rather than a technical boundary to manage.

Human-to-human, human-to-agent, agent-to-human, agent-to-agent: all four interaction patterns occur naturally within the same environment, governed by the same world model and causal rules.

---

## Current State

| System | Status |
|--------|--------|
| World model (`multiverse/`) | Functional — named locations, variable branching, rich per-level properties |
| Agent traversal (`agents/`) | Functional — FSM traversal, self-preservation, interaction logging, causal event emission |
| Puzzle engine (`puzzles/`) | Functional — four puzzle kinds, hints, attempt tracking |
| Causality engine (`causality/`) | Functional — event propagation with configurable dampening |
| Persistence (`persistence/`) | Functional — SQLite world state, agent runs, puzzle results |
| REST server (`server/`) | Functional — `/health` `/worlds` `/world` `/agent` endpoints |
| CLI (`main.py`) | Functional — `world`, `agent`, `puzzles`, `serve`, `speak`, `history` |
| Node consciousness (`consciousness/`) | Functional — Claude-powered node voices (requires `ANTHROPIC_API_KEY`) |
| Tests | 55+ tests across generator, agents, puzzles, persistence, causality |
| Interface (`interface/`) | Scaffolded |

---

## Setup

```bash
# Install runtime dependencies
pip install anthropic

# Install with dev dependencies (for tests)
pip install -e ".[dev]"

# Set your Anthropic API key (only required for the `speak` command)
export ANTHROPIC_API_KEY=sk-ant-...

# Override the Claude model (optional, defaults to claude-opus-4-7)
export NESTED_WORLDS_MODEL=claude-sonnet-4-6
```

## Running Locally

```bash
# Generate and explore the world hierarchy
python main.py world

# Run an agent traversal
python main.py agent --name Scout --danger-threshold 4

# Find and play puzzles
python main.py puzzles

# Start the REST API server (http://127.0.0.1:8080)
python main.py serve

# Speak to a node using Claude
python main.py speak --node "Vault-3" --message "What secrets do you hold?"

# View saved worlds and agent run history
python main.py history

# All commands accept --seed INT for reproducible runs
python main.py --seed 7 world --depth 6
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT

## Author

**Mark Weeks** — [markweeks.dev](https://markweeks.dev) · [multilogue.io](https://multilogue.io)
