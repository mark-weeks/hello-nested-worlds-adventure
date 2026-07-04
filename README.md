# Enfolded: Nested World Adventure

**A shared persistent multiverse inhabited simultaneously by human players and AI agents.**

*The title "Enfolded" derives from David Bohm's [implicate order](https://en.wikipedia.org/wiki/Implicate_and_explicate_order) — the idea that every part of the universe enfolds the whole, and what we perceive as separate objects are unfolded projections of a deeper connected reality. This game is a playable version of that idea.*

[enfolded.world](https://enfolded.world)

---

## Concept

Enfolded is an environment where the boundary between player, agent, and world is deliberately blurred.

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
Browser clients. `frontend/` is a React + PixiJS + Vite app for scene rendering, hotspot interaction, and live multiplayer presence. `static/app/` is a vanilla D3 tree explorer served directly by the Python server. AI-generated scene backgrounds are produced via fal.ai (`fal-ai/fast-sdxl`) and cached in persistence.

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
| World model (`multiverse/`) | Functional — named locations, variable branching, rich per-level properties across 11 scales. **Canonical worlds:** every node is a pure function of (seed, path), so a depth-6 view is exactly the top of the depth-11 world — all clients and endpoints agree on node identity, and names resolve to nodes in O(depth) (`resolve_node_by_name`). Causal events durably change node substance via `multiverse/effects.py` (solves stabilize/calm danger, alerts roughen, structural change degrades condition), persisted as a property overlay |
| Agent traversal (`agents/`) | Functional — FSM traversal, self-preservation, interaction logging, causal event emission, persistent memory across runs (keyed by node NAME, so it survives world rebuilds; the visit budget counts fresh ground, so a well-travelled agent keeps exploring), agent-to-agent encounters, four persona archetypes (*tender · destabilizer · scholar · wanderer*) auto-picked by name. **Agents obey the puzzle rules**: they attempt the node's actual engine puzzle with difficulty-weighted odds and can fail — no free solves. Danger alerts propagate upward with dampening |
| Puzzle engine (`puzzles/`) | Functional — node-voiced generators for all 11 levels (`puzzles/generators.py`): scale-themed anagrams, Caesar ciphers, inferred numeric sequences, plus de-leaked hand-written riddles/logic. Traversal is non-linear (drop in at any node, move up or down, explore continuously), so **difficulty is a per-node property spread across the full 1–4 range at every scale — not a depth curve**; scale sets a puzzle's flavour, never how hard it is. Difficulty is surfaced on `/puzzle` (a ★ rating in both frontends) so players can pick their challenge; every puzzle carries graduated hints, with more attempts for harder ones. Each node's puzzle is seeded from its own identity, so it's unique to the node yet reproducible (co-op sees the same puzzle) instead of repeating across neighbours. The answer never appears in the prompt, the hints, or the node's shipped `/world` properties, and is validated server-side (no client-side leak). Static pools remain a graceful fallback for unknown levels. |
| Causality engine (`causality/`) | Functional — bidirectional event propagation (up + down) from any origin with configurable per-hop dampening; events broadcast to all WebSocket clients carrying their REAL propagated strength (hop distance included, ancestors measured truthfully); persisted `ripple_score` accumulates atomically (concurrent participants compound, not overwrite); strong events change node properties via `multiverse/effects.py` and the change survives rebuilds (`causality/wiring.py` is the one standard wiring every surface uses) |
| Persistence (`persistence/`) | Functional — SQLite store for world state, agent runs, puzzle results, agent memory, node interaction history, world mutations, and scene-image cache |
| Server (`server/`) | Functional — REST (`/health` `/worlds` `/world` `/agent` `/observe` `/puzzle` `/players` `/history` `/image` `/speak` `/puzzle/attempt` `/agent/voice` `/position`), WebSocket multiplayer at `/ws` (chat + presence + causal events; HTTP/1.1 handshake, so spec-strict clients connect), co-op puzzle sessions (attempts pooled per room; solver + contributors broadcast on solve), bundled browser UI at `/app`, security headers + CSP, body/frame size caps. **Node identity is server-derived**: `/speak`, `/image`, and `/agent/voice` resolve the named node against the canonical world (404 for forged names) — clients cannot invent a node's nature or write history for places that don't exist |
| World heartbeat (`server/heartbeat.py`) | Functional — the multiverse runs unattended: a daemon loop (default every 180s, `NESTED_WORLDS_HEARTBEAT*` env) sends recurring persona agents (*Tessera, Halden, Mirrorbird…*) on paced traversals that persist history/ripple/effects and broadcast live to the seed-room. FSM-driven — zero API spend |
| CLI (`main.py`) | Functional — `world`, `agent`, `puzzles` (`--limit`, skip/quit, EOF-safe), `play` (`--name` so nodes remember you), `serve`, `speak`, `history` (now includes puzzle results); `--seed` accepted before or after the subcommand. CLI play is part of the shared world: solves persist and cascade, ambient observation leaves real traces, and the session tree carries the world's persisted evolution |
| Node consciousness (`consciousness/`) | Functional — Claude-powered node voices, per-scale character registers (`LEVEL_VOICES`) for all 11 levels. Memory has content: nodes hear what you said and remember what they answered (both persist in the exchange), a per-(node, player) transcript makes conversations multi-turn, and accumulated causal pressure (`ripple_score`) colors the voice. Without a key the world degrades in character: every scale has an authored fallback line (`LEVEL_FALLBACKS`) — never an HTTP 503 or SDK error. Agent voicing via `voice_agent()` fetches real node history |
| Interface (`interface/`) | Functional — interactive terminal session (spatial, conversational, ambient) |
| Frontend (`frontend/`) | Functional — React + PixiJS + Vite client wired to the WebSocket server; node conversation (`/speak`) and puzzle play (`/puzzle`) panels; fal.ai-generated scene backgrounds; named player markers (color hashed by name); animated causal ripples / encounter glyphs / puzzle-solve sparkles overlaid on the current scene. Scene init degrades gracefully (no white-screen) when WebGL is unavailable |
| Beta hardening (`server/guard.py`, `server/observability.py`) | Functional — shared invite key OR per-user invite keys (`invite_keys` table; mint/list/revoke via `python main.py invite ...`), per-IP rate limiter, Anthropic concurrency semaphore (env-tunable), daily Anthropic + fal.ai cost caps — both a global cap and a per-user (per-credential) sub-cap so one account can't drain the shared budget (all persisted), kill switches for AI / images, world-gen parameter bounds, optional Sentry, JSON access log, online SQLite backup CLI |
| Frontends: which is which | Two browser clients. `/` (vanilla-D3 explorer) and `/app` (React+PixiJS) are **both** feature-complete for the core loop — navigate, speak to nodes, solve puzzles, observe, live multiplayer. Invite URLs land testers on `/` by default because it has no WebGL dependency and works on any device first-click; `/app` is the richer immersive view. |
| Non-linear entry (both clients) | Traversal is non-linear (move up or down from any node; no "reach the bottom" goal), so there is no fixed root start. A **first-time player drops in at a node in the middle of the world** — one with places to go both up and down — chosen deterministically from their name. A **returning player resumes exactly where they left off**, and that resume **follows them across devices**: the last node (and the world it belonged to) is stored server-side keyed on the invite key (`GET`/`POST /position`, columns on `invite_keys`), so a tester who opens the game on a new device or browser lands back where they were. `localStorage` stays a same-browser cache and the server is the cross-device source of truth; shared-key / no-key sessions have no server row and fall back to the local cache. Falls back to a fresh drop-in if the saved node is gone. Shared logic in `frontend/src/entry.js` (React) mirrored in `static/explorer.js` (D3). |
| Tests | 486 Python tests across generator (incl. canonical prefix-stability), agents (incl. memory-across-rebuilds and puzzle-rule parity), puzzles (quality invariants — no-leak, solvable, node-unique, per-node difficulty spread, transform integrity, never-in-properties), effects + causal wiring, persistence (incl. invite keys + cross-device position + property overlay), causality, interface, consciousness (incl. transcripts + fallback voices), heartbeat, HTTP/WebSocket server, node resolution, beta guards, Fly deploy config, frontend↔endpoint contract (incl. welcome-roster + history-backfill), and observability — plus 17 Vitest JS tests (entry resolution incl. cross-client parity, WS dispatch) run in CI |

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
| `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` | Hosted beta: global cap on Anthropic calls per UTC day; once exceeded, `/speak` and `/agent/voice` return a fallback string instead of calling the API. | `500` |
| `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` | Hosted beta: per-credential daily Anthropic cap, so no single tester can consume the whole global budget and degrade the cohort. Enforced only when a request carries an invite credential. | `150` |
| `NESTED_WORLDS_FAL_DAILY_CALLS_PER_USER` | Hosted beta: per-credential daily fal.ai image cap. | `60` |
| `NESTED_WORLDS_ANTHROPIC_CONCURRENCY` | Hosted beta: max in-flight Anthropic calls per process. Bounds instantaneous concurrency so a synchronized burst can't trip the org-level RPM. | `8` |
| `NESTED_WORLDS_FAL_DAILY_CALLS` | Hosted beta: cap fal.ai image calls per UTC day. | `200` |
| `NESTED_WORLDS_HEARTBEAT` | Set to `0` to disable the ambient world heartbeat (background agent life). | on |
| `NESTED_WORLDS_HEARTBEAT_INTERVAL` | Seconds between heartbeat ticks. Heartbeat agents are FSM-driven — no API spend. | `180` |
| `NESTED_WORLDS_RATE_LIMIT_PER_MIN` | Hosted beta: per-IP requests/minute on `/speak`, `/agent/voice`, `/image`, `/puzzle/attempt`. | `20` |
| `NESTED_WORLDS_MAX_WS_CONNECTIONS` | Hosted beta: max concurrent WebSocket connections process-wide. Excess upgrades get `503`. | `128` |
| `NESTED_WORLDS_MAX_WS_PER_IP` | Hosted beta: max concurrent WebSocket connections per client IP. | `8` |
| `NESTED_WORLDS_DISABLE_AI` | Set to `1` to disable `/speak` and `/agent/voice` without a redeploy. | unset |
| `NESTED_WORLDS_DISABLE_IMAGES` | Set to `1` to disable `/image` without a redeploy. | unset |
| `NESTED_WORLDS_TRUST_PROXY` | Set to `1` only when running behind a trusted reverse proxy. The rate limiter then reads the real client IP from a proxy-set header (never the spoofable left-most `X-Forwarded-For`). | unset |
| `NESTED_WORLDS_CLIENT_IP_HEADER` | Trusted client-IP header consulted when `TRUST_PROXY=1`. Falls back to the right-most `X-Forwarded-For` entry. | `Fly-Client-IP` |
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

# Find and play puzzles (first 10 by default; 'skip' passes, Ctrl-D stops)
python main.py puzzles --limit 5

# Start an interactive session (spatial navigation + conversation + ambient)
python main.py play --name Ada    # give a name and the nodes remember you

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

# All commands accept --seed INT, before or after the subcommand
python main.py world --seed 7 --depth 6
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

**Mark Weeks** — [markweeks.dev](https://markweeks.dev) · [multilogue.io](https://multilogue.io) · [enfolded.world](https://enfolded.world)
