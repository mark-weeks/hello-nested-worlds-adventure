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
Deterministic FSM travelers with distinct personas, goals, and relationships to specific nodes and scales — Claude-adjacent rather than Claude-driven: their traversal and in-character banter run at zero API spend, and they are voiced by Claude only when addressed directly (`/agent/voice`). Agents traverse the world, interact with nodes and each other, accumulate memory, and can be engaged in conversation. Some destabilize; some tend. Their behavior is driven by goals and shaped by world state.

**Persistence** (`persistence/`)
World state lives in a database. The multiverse exists between sessions. Interaction history, causal state, and agent memory persist. Multiple participants can be present simultaneously.

**Server** (`server/`)
Real-time API layer. WebSocket-based synchronization for multi-participant presence and player chat, broadcasting causal events to all connected clients. REST endpoints for world state, observation, puzzles, and node speech. Serves the bundled browser UI from `/app`.

**Interface** (`interface/`)
The terminal interaction layer. Spatial navigation, conversational `speak`, ambient observation, and embedded puzzles in a single REPL.

**Frontend** (`frontend/`, `static/app/`)
Browser clients. `frontend/` is a React + PixiJS + Vite app for scene rendering, hotspot interaction, and live multiplayer presence, built into `static/app/` and served at `/app`. The vanilla D3 tree explorer (`static/index.html` + `static/explorer.js`) is served at `/` directly by the Python server. AI-generated scene backgrounds are produced via fal.ai (`fal-ai/fast-sdxl`) and cached in persistence.

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

*Matrix last verified against code: 2026-08-04.*

| System | Status |
|--------|--------|
| World model (`multiverse/`) | Functional — named locations, variable branching, rich per-level properties across 11 scales. **One shared canonical launch world (ADR-007):** the hosted server serves curated seed 382 to every human and agent; arbitrary client seeds are rejected before they can birth a parallel persistent history. At birth every node is a pure function of (seed, path), then its stored row is authoritative; a depth-6 view is exactly the top of the same depth-11 materialized world. **Every node identity is readable and unique:** generator v2 assigns a collision-free three-word semantic name plus its path suffix, every node has a synthesized `aspect`, and property fingerprints do not repeat across the 4,208-node launch world (guarded by tests and the executable launch census). Causal events durably change node substance via `multiverse/effects.py`, persisted as a property overlay. **The hierarchy closes into a traversal-layer loop (ADR-008):** descending below any SubatomicParticle surfaces at the Multiverse root; ascending beyond the root lands at the world's one hinge particle — selected once by a seed-pure rule constrained to a fully unsealed lineage, pinned write-once in `world_meta`, and never re-selected by code. Containment stays a tree; causality does not wrap |
| Agent traversal (`agents/`) | Functional — FSM traversal, self-preservation, interaction logging, causal event emission, persistent memory across runs (keyed by node NAME, so it survives world rebuilds; the visit budget counts fresh ground, so a well-travelled agent keeps exploring), agent-to-agent encounters, four persona archetypes (*tender · destabilizer · scholar · wanderer*) auto-picked by name. **Agents obey the puzzle rules**: they attempt the node's actual engine puzzle with difficulty-weighted odds and can fail — no free solves. Danger alerts propagate upward with dampening |
| Puzzle engine (`puzzles/`) | Functional — node-voiced generators for all 11 levels (`puzzles/generators.py`) combine transforms with **world-reading mechanics**: contextual seals, lineage/bond/enfold puzzles, Keeper Witnesses that make readable ancestor names into landmarks, and Ancestral Compasses assembled from two enclosing scales. Ancestor names intentionally remain visible for orientation: gentle Keepers ask for one landmark, while 3–4★ Keepers compose a new answer from two or three named scales instead of presenting copyable answer text. Traversal is non-linear (drop in anywhere, move up or down), so **difficulty is a per-node property spread across the full 1–4 range at every scale — not a depth curve**. The executable ecology gate (`scripts/puzzle_quality.py`) prevents the generic decode families from retaking the world: in seed 382 they are 37.81%, world-reading families are 61.50%, no family exceeds 21.91%, prompts are 99.86% unique, and answers 54.42% unique. Puzzles carry graduated hints and server-side answers that never appear in their prompt, hints, or current node properties. Identity remains deterministic across full-tree and direct stored-node resolution, so co-op and renewal epochs agree. Static pools remain a fallback for unknown levels. |
| Causality engine (`causality/`) | Functional — bidirectional event propagation (up + down) from any origin with configurable per-hop dampening; events broadcast to all WebSocket clients carrying their REAL propagated strength (hop distance included, ancestors measured truthfully); persisted `ripple_score` accumulates atomically (concurrent participants compound, not overwrite); strong events change node properties via `multiverse/effects.py` and the change survives rebuilds (`causality/wiring.py` is the one standard wiring every surface uses). **Consequences travel at world speed** (`causality/staging.py`): only the origin's immediate ring fires inside the triggering request — farther rings are staged in a durable queue (`causal_queue`) and drained by a pump thread, one ring per hop delay (default 12s, `NESTED_WORLDS_HOP_DELAY`), each arrival broadcast live as it lands; staged hops persist, so a restart delays a ripple, never loses it |
| Persistence (`persistence/`) | Functional — SQLite store for world state, agent runs, puzzle results, agent memory, node interaction history, world mutations, staged causal hops, and scene-image cache. **The database is a continuous chronicle, not per-cohort scratch**: each new player (human or agent) builds on the traces of everyone before them — migrations are additive-only and the DB is never wiped between cohorts (policy in `docs/roadmap/phase-2-scale.md`) |
| Server (`server/`) | Functional — REST (`/health` `/worlds` `/world` `/agent` `/observe` `/puzzle` `/players` `/history` `/chronicle` `/image` `/speak` `/puzzle/attempt` `/act` `/agent/voice` `/position` `/client-error`), player guide at `/guide`, WebSocket multiplayer at `/ws`, co-op puzzle sessions, bundled browser UI at `/app`, security headers + CSP, body/frame size caps. **Canonical-world boundary:** `NESTED_WORLDS_CANONICAL_SEED` governs every HTTP, SSE, WebSocket, position, and heartbeat path; missing seed selects it, a mismatch is rejected before lookup/birth, and stale alternate-world positions cannot redirect a player. **Node identity is server-derived**: `/speak`, `/image`, and `/agent/voice` resolve the named node against that world (404 for forged names). WebSockets retain strict RFC 6455 framing and non-blocking per-player writer queues; agents remain addressable through persisted memory and node-scoped history |
| World heartbeat (`server/heartbeat.py`) | Functional — the canonical world runs unattended: a daemon loop (default every 180s, `NESTED_WORLDS_HEARTBEAT*` env) sends recurring persona agents (*Tessera, Halden, Mirrorbird…*) on paced traversals that persist history/ripple/effects and broadcast live to the shared room. It cannot fall back to an old alternate seed when the hosted boundary is active. FSM-driven — zero API spend |
| CLI (`main.py`) | Functional — `world`, `agent`, `puzzles`, `play`, `serve`, `speak`, `history`; `--seed` remains accepted for operator curation, deterministic evaluation, and isolated local development. To act in the hosted world's history, operators use its configured canonical seed. Player-facing browser clients cannot choose or create worlds |
| Node consciousness (`consciousness/`) | Functional — Claude-powered node voices with per-scale registers (`LEVEL_VOICES`) AND deep per-scale lore (`LEVEL_LORE`: diction, how each scale senses its neighbors, pressure behavior, exemplar exchanges) for all 11 levels. Memory has content: nodes hear what you said and remember what they answered, per-(node, speaker) transcripts make conversations multi-turn (keyed on the invite credential, so same-name strangers stay strangers), and accumulated causal pressure colors the voice. **Prompt caching genuinely fires**: both bibles exceed the real 4096-token Opus minimum (guarded by tests), so after the first call in a 1h window the prefix bills at the ~10x cache-read discount. Without a key the world degrades in character: every scale has an authored fallback line — never an HTTP 503 or SDK error |
| Interface (`interface/`) | Functional — interactive terminal session (spatial, conversational, ambient) |
| Frontend (`frontend/`) | Functional — React + PixiJS + Vite and vanilla-D3 clients wired to the same server-owned world; neither exposes seed/world creation. Node conversation, puzzles, speak-to-presences, passage affordances, multiplayer presence, and chronicle all converge on the shared history. **Per-node generative art** (`static/nodeart.js`) and **per-node generative soundscape** (`static/nodesound.js`) are shared by both clients: scale, properties, history, causal pressure, and condition shape what each place looks and sounds like. Sound stays opt-in for browser activation; fal.ai imagery is an optional enhancement wash; WebGL failure degrades gracefully |
| Beta hardening (`server/guard.py`, `server/observability.py`) | Functional — per-user invite keys are the whole invite gate (`invite_keys` table; mint/list/revoke via `python main.py invite ...`; no shared key, so every gated session is a known, unique, named player — ADR-004 §7), **invite-gated self-service registration** (`invite create` mints a single-use token; the player picks their own unique name at `/register` and redemption atomically mints their play key — name taken → "choose another", token survives for the retry), **input moderation** (ADR-004 §2: fail-open two-tier screen on `/speak`, `/agent/voice`, WS chat, and registered names — a µs-scale local filter blocks only unambiguous slurs and escalates anything fuzzy to one uncached Haiku-tier classify on its own daily budget; declined input gets an authored in-fiction line and leaves no chronicle row, no broadcast, no voice-budget charge; `NESTED_WORLDS_DISABLE_MODERATION=1` kill switch), per-IP rate limiter, Anthropic concurrency semaphore (env-tunable), daily Anthropic + fal.ai cost caps — both a global cap and a per-user (per-credential) sub-cap so one account can't drain the shared budget (all persisted), kill switches for AI / images, world-gen parameter bounds, optional Sentry, JSON access log, online SQLite backup CLI |
| Frontends: which is which | Two browser clients. `/` (vanilla-D3 explorer) and `/app` (React+PixiJS) are **both** feature-complete for the core loop — navigate, speak to nodes, solve puzzles, live multiplayer. Ambient observe (`/observe` SSE) is explorer-only; `/app` covers the rest of the loop. For the beta, the explorer is the **default surface** (ADR-005): invite URLs land on `/` because it has no WebGL dependency and works on any device first-click, and the guide names `/app` as "the scene view" to try once oriented — the same world and key carry over via localStorage. |
| Non-linear entry (both clients) | Traversal is non-linear, so there is no fixed root start. A first-time player drops into the middle of the shared world; a returning player resumes their last canonical-world node across devices via their invite-key position. `localStorage` remains a same-browser cache; a stale node that does not exist in the hosted world falls back to a fresh drop-in. Entry, passage-badge, and chronicle-rendering rules are canonical in `static/clientlogic.js` and consumed by both clients |
| Tests | 877 Python tests across generator and stored-world continuity, agents, puzzle quality/ecology, effects and staged causality, persistence, chronicled deltas, the wrap passage, consciousness, heartbeat, HTTP/WebSocket conformance, canonical-world boundaries, node resolution, beta guards, deployment contracts, frontend↔endpoint contracts, and observability — plus 91 Vitest tests for canonical entry/resume/affordance/chronicle/wrap/display-name behavior, WebSocket dispatch, and deterministic node art and sound. CI also builds the production frontend, rejects a stale committed bundle, smoke-tests the installed wheel, and runs Playwright against the real server under the production CSP. |

---

## Setup

```bash
# Use the pinned runtimes, then install the locked Python and Node dependencies
nvm use
./setup.sh
source .venv/bin/activate

# Copy the environment template and fill in keys you need
cp .env.example .env
```

Environment variables (see `.env.example`):

| Variable | Required for | Default |
|----------|--------------|---------|
| `ANTHROPIC_API_KEY` | Node consciousness (`speak`, browser chat with nodes) | — |
| `NESTED_WORLDS_MODEL` | Override the Claude model | `claude-opus-4-8` |
| `FAL_KEY` | AI-generated scene backgrounds (`fal-ai/fast-sdxl`) | optional |
| Invite gate (no env var) | Hosted beta: the gate is the per-user `invite_keys` table, not an env var — there is no shared key. Mint keys with `python main.py invite mint --name <player>`, or create a single-use self-service invite with `invite create` (the player picks their own unique name at `/register?invite=<token>`). Minting the first key closes the gate so every HTTP and WebSocket request needs a valid `?key=...` or `X-Beta-Key`, and every gated session is a known, unique, named player. Keys and registration tokens are stored hashed at rest (sha256): the plaintext credential appears once at mint/registration and cannot be recovered later — revoke and re-mint if lost (`invite list` / `invite tokens` show an 8-char hash prefix). Mint no keys for local dev. | open until first mint |
| `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` | Hosted beta: global cap on Anthropic calls per UTC day; once exceeded, `/speak` and `/agent/voice` return a fallback string instead of calling the API. | `500` |
| `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` | Hosted beta: per-credential daily Anthropic cap, so no single tester can consume the whole global budget and degrade the cohort. Enforced only when a request carries an invite credential. | `150` |
| `NESTED_WORLDS_FAL_DAILY_CALLS_PER_USER` | Hosted beta: per-credential daily fal.ai image cap. | `60` |
| `NESTED_WORLDS_ANTHROPIC_CONCURRENCY` | Hosted beta: max in-flight Anthropic calls per process. Bounds instantaneous concurrency so a synchronized burst can't trip the org-level RPM. | `8` |
| `NESTED_WORLDS_FAL_DAILY_CALLS` | Hosted beta: cap fal.ai image calls per UTC day. | `200` |
| `NESTED_WORLDS_HEARTBEAT` | Set to `0` to disable the ambient world heartbeat (background agent life). | on |
| `NESTED_WORLDS_HEARTBEAT_INTERVAL` | Seconds between heartbeat ticks. Heartbeat agents are FSM-driven — no API spend. | `180` |
| `NESTED_WORLDS_HOP_DELAY` | Seconds a staged causal cascade waits between rings — how fast consequences travel across scales. `0` makes staged hops due immediately (they still run through the queue). | `12` |
| `NESTED_WORLDS_CAUSAL_PUMP` | Set to `0` to disable the pump thread that drains staged causal hops (queued hops then wait until a pump runs again). | on |
| `NESTED_WORLDS_RATE_LIMIT_PER_MIN` | Hosted beta: per-IP requests/minute on `/speak`, `/agent/voice`, `/image`, `/puzzle/attempt`, `/act`, `/register`, `/client-error`. | `20` |
| `NESTED_WORLDS_RATE_LIMIT_GET_PER_MIN` | Hosted beta: per-IP requests/minute on the expensive read endpoints `/world`, `/agent`, `/observe`, `/puzzle`, `/chronicle`, `/history`. | `120` |
| `NESTED_WORLDS_MAX_WS_CONNECTIONS` | Hosted beta: max concurrent WebSocket connections process-wide. Excess upgrades get `503`. | `128` |
| `NESTED_WORLDS_MAX_WS_PER_IP` | Hosted beta: max concurrent WebSocket connections per client IP. | `8` |
| `NESTED_WORLDS_DISABLE_AI` | Set to `1` to disable `/speak` and `/agent/voice` without a redeploy. | unset |
| `NESTED_WORLDS_DISABLE_IMAGES` | Set to `1` to disable `/image` without a redeploy. | unset |
| `NESTED_WORLDS_DISABLE_MODERATION` | Set to `1` to turn off the input-moderation screen without a redeploy (ADR-004 §2). | unset |
| `NESTED_WORLDS_MODERATION_MODEL` | Model for the moderation classify call (ambiguous inputs only; clean input costs zero API calls). | `claude-haiku-4-5` |
| `NESTED_WORLDS_MODERATION_DAILY_CALLS` | Daily cap on classify calls — moderation's own budget line; when exhausted the screen fails open, never blocking chat. | `2000` |
| `NESTED_WORLDS_MODERATION_BLOCK_EXTRA` / `..._WATCH_EXTRA` | Comma-separated hot extensions to the block / watch term lists — react to live abuse without a redeploy. | unset |
| `NESTED_WORLDS_TRUST_PROXY` | Set to `1` only when running behind a trusted reverse proxy. The rate limiter then reads the real client IP from a proxy-set header (never the spoofable left-most `X-Forwarded-For`). | unset |
| `NESTED_WORLDS_CLIENT_IP_HEADER` | Trusted client-IP header consulted when `TRUST_PROXY=1`. Falls back to the right-most `X-Forwarded-For` entry. | `Fly-Client-IP` |
| `NESTED_WORLDS_MUTATION_TTL_DAYS` | Days of `world_mutations` retention. **Continuity-violating** — the mutation log is the world's permanent chronicle and feeds the generative art, so this is ignored (with a warning) unless `NESTED_WORLDS_ALLOW_HISTORY_PRUNE=1` is also set. | unset |
| `NESTED_WORLDS_ALLOW_HISTORY_PRUNE` | Explicit confirmation flag for the above. Do not set it casually. | unset |
| `SENTRY_DSN` | Optional. `sentry-sdk` ships as a default dependency; set the DSN to forward unhandled handler exceptions to Sentry. | unset |
| `SENTRY_ENVIRONMENT` | Tag for the Sentry environment field. | `production` |

The browser frontend (`frontend/`) is a separate Vite project:

```bash
cd frontend
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

# Operator/dev commands accept --seed INT; the hosted clients do not
python main.py world --seed 7 --depth 6

# Audit the unborn launch world's visible variety and puzzle ecology
python scripts/world_quality.py --seed 382
python scripts/puzzle_quality.py --seed 382
```

The four design-partner captures are reproducible from an isolated temporary
database after Playwright Chromium and `ffmpeg` are installed:

```bash
cd frontend
npm run capture:pitch
```

## Running Tests

```bash
./scripts/check.sh

# Include the real-browser smoke tests after Playwright Chromium is installed
ENFOLDED_E2E=1 ./scripts/check.sh
```

---

## License

MIT

## Author

**Mark Weeks** — [markweeks.dev](https://markweeks.dev) · [multilogue.io](https://multilogue.io) · [enfolded.world](https://enfolded.world)
