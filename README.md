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

Eleven nested scales, each with its own aesthetic register and causal weight:

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
Real-time API layer. WebSocket-based synchronization for multi-participant presence and player chat, broadcasting causal events to all connected clients. REST endpoints for world state, observation, puzzles, and node speech. Serves the bundled browser UI from `/app`.

**Interface** (`interface/`)
The terminal interaction layer. Spatial navigation, conversational `speak`, ambient observation, and embedded puzzles in a single REPL.

**Frontend** (`frontend/`, `static/app/`)
Browser clients. `frontend/` is a React + PixiJS + Vite app for scene rendering, hotspot interaction, and live multiplayer presence. `static/app/` is a vanilla D3 tree explorer served directly by the Python server. AI-generated scene backgrounds are produced via fal.ai (Flux Schnell) and cached in persistence.

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
| World model (`multiverse/`) | Functional — named locations, variable branching, rich per-level properties across 11 scales |
| Agent traversal (`agents/`) | Functional — FSM traversal, self-preservation, interaction logging, causal event emission, persistent memory across runs, agent-to-agent encounters, four persona archetypes (*tender · destabilizer · scholar · wanderer*) auto-picked by name and surfaced in events / encounters / voicing |
| Puzzle engine (`puzzles/`) | Functional — property-driven dynamic generators for every one of the 11 levels (ANAGRAM, RIDDLE, LOGIC, LOCK, NAVIGATION); static pools retained as graceful fallback; server-validated attempts (no client-side leak) |
| Causality engine (`causality/`) | Functional — bidirectional event propagation (up + down) from any origin with configurable per-hop dampening; events broadcast to all WebSocket clients; in-memory `ripple_score` accumulates as nodes fire |
| Persistence (`persistence/`) | Functional — SQLite store for world state, agent runs, puzzle results, agent memory, node interaction history, world mutations, and scene-image cache |
| Server (`server/`) | Functional — REST (`/health` `/worlds` `/world` `/agent` `/observe` `/puzzle` `/players` `/history` `/image` `/speak` `/puzzle/attempt` `/agent/voice`), WebSocket multiplayer at `/ws` (chat + presence + causal events), co-op puzzle sessions (attempts pooled per room; solver + contributors broadcast on solve), bundled browser UI at `/app`, security headers + CSP, body/frame size caps |
| CLI (`main.py`) | Functional — `world`, `agent`, `puzzles`, `play`, `serve`, `speak`, `history` |
| Node consciousness (`consciousness/`) | Functional — Claude-powered node voices, per-scale character registers (`LEVEL_VOICES`) for all 11 levels, fed by per-node interaction history; agent voicing via `voice_agent()` (requires `ANTHROPIC_API_KEY`) |
| Interface (`interface/`) | Functional — interactive terminal session (spatial, conversational, ambient) |
| Frontend (`frontend/`) | Functional — React + PixiJS + Vite client wired to the WebSocket server; fal.ai-generated scene backgrounds; named player markers (color hashed by name); animated causal ripples / encounter glyphs / puzzle-solve sparkles overlaid on the current scene |
| Beta hardening (`server/guard.py`, `server/observability.py`) | Functional — shared invite key OR per-user invite keys (`invite_keys` table; mint/list/revoke via `python main.py invite ...`), per-IP rate limiter, Anthropic concurrency semaphore (env-tunable), daily Anthropic + fal.ai cost caps (persisted), kill switches for AI / images, world-gen parameter bounds, optional Sentry, JSON access log, online SQLite backup CLI |
| Tests | 316 tests across generator, agents, puzzles, persistence (incl. invite keys), causality, interface, consciousness, HTTP/WebSocket server, beta guards (incl. per-user keys), and observability |

---

## Setup

```bash
# Install runtime dependencies
pip install anthropic

# Install with dev dependencies (for tests)
pip install -e ".[dev]"

# Copy the environment template and fill in keys you need
cp .env.example .env
```

Environment variables (see `.env.example`):

| Variable | Required for | Default |
|----------|--------------|---------|
| `ANTHROPIC_API_KEY` | Node consciousness (`speak`, browser chat with nodes) | — |
| `NESTED_WORLDS_MODEL` | Override the Claude model | `claude-opus-4-7` |
| `FAL_KEY` | AI-generated scene backgrounds (`fal-ai/fast-sdxl`) | optional |
| `NESTED_WORLDS_BETA_KEY` | Hosted beta: shared invite gate. When set, every HTTP and WebSocket request needs `?key=...` or `X-Beta-Key`. Coexists with the per-user `invite_keys` table — either credential authorizes. Leave unset (and mint no per-user keys) for local dev. | unset |
| `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` | Hosted beta: cap Anthropic calls per UTC day; once exceeded, `/speak` and `/agent/voice` return a fallback string instead of calling the API. | `500` |
| `NESTED_WORLDS_ANTHROPIC_CONCURRENCY` | Hosted beta: max in-flight Anthropic calls per process. Bounds instantaneous concurrency so a synchronized burst can't trip the org-level RPM. | `8` |
| `NESTED_WORLDS_FAL_DAILY_CALLS` | Hosted beta: cap fal.ai image calls per UTC day. | `200` |
| `NESTED_WORLDS_RATE_LIMIT_PER_MIN` | Hosted beta: per-IP requests/minute on `/speak`, `/agent/voice`, `/image`, `/puzzle/attempt`. | `20` |
| `NESTED_WORLDS_DISABLE_AI` | Set to `1` to disable `/speak` and `/agent/voice` without a redeploy. | unset |
| `NESTED_WORLDS_DISABLE_IMAGES` | Set to `1` to disable `/image` without a redeploy. | unset |
| `NESTED_WORLDS_TRUST_PROXY` | Set to `1` only when running behind a trusted reverse proxy so the rate limiter can read `X-Forwarded-For`. | unset |
| `SENTRY_DSN` | Optional. `sentry-sdk` ships as a default dependency; set the DSN to forward unhandled handler exceptions to Sentry. | unset |
| `SENTRY_ENVIRONMENT` | Tag for the Sentry environment field. | `production` |

The browser frontend (`frontend/`) is a separate Vite project:

```bash
cd frontend
npm install
npm run dev    # dev server with hot reload
npm run build  # production bundle
```

## Running Locally

```bash
# Generate and explore the world hierarchy
python main.py world

# Run an agent traversal
python main.py agent --name Scout --danger-threshold 4

# Find and play puzzles
python main.py puzzles

# Start an interactive session (spatial navigation + conversation + ambient)
python main.py play

# Start the REST API server (http://127.0.0.1:8080)
python main.py serve

# Speak to a node using Claude
python main.py speak --node "Vault-3" --message "What secrets do you hold?"

# View saved worlds and agent run history
python main.py history

# Snapshot the SQLite store (safe while the server is running)
python main.py backup --to /backups/worlds-$(date +%Y%m%d).db

# Manage per-user beta invite keys
python main.py invite mint --name Alice --note "design partner"
python main.py invite list
python main.py invite revoke nw_...

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
