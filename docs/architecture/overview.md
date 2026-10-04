# Architecture Overview

*Refreshed against `main` at #109 (2026-10-03). The system map is unchanged;
the component notes name the modules that exist today. The README's
"Current State" matrix carries the measured claims; this page says where the
code lives.*

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

The vanilla D3 explorer (`static/`) sits beside `frontend/` as a second
browser client; both share the static modules listed under **Frontend**.

---

## Components

### `multiverse/` — World Model
- **`node.py`** — `SpatialNode`: recursive data structure with id, name, level, children, properties; per-node interaction history lives in `persistence/` (`world_mutations`) and is read through `persistence.get_node_history`
- **`generator.py`** — birth-time PCG (generator v2: collision-free three-word semantic names, synthesized `aspect`, per-level property banks). Every new node is a pure function of (seed, path); the banks govern births only
- **`store.py`** — the materialized world (ADR-006): `birth_world` births each seed once (idempotent), serves stored prefix views, resolves path-encoded names in O(depth) via `resolve_node_by_name`, and owns `GENERATOR_VERSION`
- **`wrap.py`** — the wrap passage (ADR-008): descending below any particle surfaces at the root; ascending beyond the root lands on the one hinge particle, selected by a seed-pure rule and pinned write-once in `world_meta`
- **`effects.py`** — causal events change node substance (solves stabilize, alerts roughen, structural change degrades condition); deltas persist as a property overlay and are chronicled (ADR-009)
- **`chronicle.py`** — the two era display banks behind `/chronicle`; frozen until eras are materialized (ADR-006)
- **`history.py`** — evidence-bound narration of history rows (M3, ADR-021): original actions, traveling ripples and delayed outcomes read differently, actors stay untyped
- **`description.py`**, **`senses.py`** — read-only descriptions of current substance (including retained material traces) and the versioned sensory interpretation both clients render from
- **`verbs.py`** — the original eleven scale-native verbs, retained for existing actors and delayed work; cosmic-scale verbs mature on a slow clock (`NESTED_WORLDS_MATURATION_SCALE`)
- **`interventions_v1.py` / `interventions_v2.py` / `interventions_v3.py`** — frozen interpreters for accepted expressive work by version; v3 is the current commit-then-discover rule set (ADR-028). **`delayed_v2.py`** is the frozen M2 operation interpreter (ADR-020)
- **`situation.py`** — the authored first situation (ADR-025), deliberately not a generic quest engine; its scripted choice is retired from new play (#109), its clues and receipts remain readable
- **`quality.py`** — the executable launch census behind `scripts/world_quality.py`
- **`utils.py`** — tree helpers: `count_nodes`, `find_node`, `build_depth_map`, `build_distance_map`, `apply_ripple_scores`, `apply_property_overrides`

### `consciousness/` — Node Voice Layer
Claude-powered persona system. The model is called in exactly four places: node voice, agent voice, moderation classify, and intention interpretation.
- `LEVEL_VOICES` and `LEVEL_LORE` — per-scale character notes and deep lore for all 11 levels, assembled into cached prompt bibles that exceed the model's cache minimum (`cached_prefix_meets_minimum`, `warn_if_cache_ineffective`)
- `speak(node, message, history, transcript, ripple_score, speaker)` — two system blocks (cached bible + dynamic node context) plus a real multi-turn message list from the per-(node, speaker) transcript
- `voice_agent(persona, agent_name, node, message, history)` — speaks AS an agent visiting a node, framed by its archetype and grounded in the node's real history
- `LEVEL_FALLBACKS` / `fallback_voice(node)` — the authored failure voice: when the API is unavailable, every scale answers with an in-register line of silence instead of an error (HTTP 200, `ai: false`)
- **`interventions.py`** — interprets a submitted intention into enum-bounded ordered steps; never predicts outcomes or writes patches
- Thread-safe lazy `Anthropic` client init; concurrency semaphore; sanitised inbound text. The moderation screen itself lives in `server/moderation.py` and `content_screen.py`

### `causality/` — Causal Engine
- `EventKind`, `CausalEvent`, `CausalityBus`, `emit(...)`, `propagate(origin, kind, dampening, direction)` — origin fires once, then cascades up and/or down with per-hop dampening until `MIN_STRENGTH`; each fire bumps the persisted `ripple_score` atomically
- **`laws.py`** — per-universe physics: each Universe's declared law profile routes its cascades
- **`staging.py`** — consequences travel at world speed: only the origin's immediate ring fires inside the request; farther rings are staged in the durable `causal_queue` and drained one ring per hop delay
- **`delivery.py`** — atomic claim/apply fences for staged producers (M1, ADR-019; M2, ADR-020), so accepted work survives process death, duplicate delivery and concurrent workers
- **`forecast.py`** — a pure, side-effect-free forecast of the engine's physics, used by the Causal Augury puzzle family (ADR-010) and pinned equivalent to the live bus
- **`wiring.py`** — the one standard bus wiring (record mutations + additive persisted ripple + material effects + chronicled deltas) used by the server, the heartbeat and the CLI

### `agents/` — AI Agent System
- **`agent.py`** — `Agent` dataclass with FSM traversal, self-preservation, interaction logging, persistent memory across runs, agent-to-agent encounters
- **`behaviors.py`** — `State` enum, `transition()`, behavioral predicates
- **`personas.py`** — four archetypes (*tender, destabilizer, scholar, wanderer*) with `for_name()` / `by_name()`; the archetype voice text lives in the consciousness agent bible
- **`roster.py`** — the named cast: twelve individuals with trait sheets (*Tessera, Halden, Mirrorbird, …*)
- **`banter.py`** — deterministic agent-to-agent conversation at zero API spend; openers, responses, closings and node observations rotate before they repeat
- Agents attempt puzzles under the engine's rules (difficulty-weighted, reproducible, can fail) and never claim human progress; memory is keyed by node name; M4 attention (ADR-022) separates known places from relevant revisits and bounds work per heartbeat tick

### `persistence/` — World State
SQLite-backed store, WAL mode, 27 additive migrations (`persistence/migrations/`, applied atomically per file).
- **`__init__.py`** — world identity (`world_nodes`, `world_meta` with write-once `pin_world_meta`), the append-only chronicle (`record_mutation`, `get_node_history`, `get_mutations`), chronicled deltas (`record_substance_change` / `record_substance_transition`) and the state-at-T fold (ADR-009/011), agent runs and memory, puzzle results, invite keys and registration tokens, cost budgets, image cache, online backup/restore, content-level redaction and double-gated pruning
- **`participants.py`** — participant identity separate from credentials (ADR-024): journal notes, published profile, home bookmark, credential rotation
- **`puzzle_content.py`** (with `puzzles/instances.py`) — stored first-use puzzle definitions and their public observational evidence
- **`intents.py`** — request-ID receipts: a retry returns its committed response; a changed intent under the same ID is refused
- **`interventions.py`** — atomic expressive commitments and recoverable, versioned consequences (migration 0027)
- **`situations.py`** — bounded, atomic progression for the first shared situation (ADR-025); new scripted choices are refused, existing receipts and consequences stay recoverable
- **`ideas.py`** / **`ideas_cli.py`** — community Ideas storage and operator moderation commands (ADR-026); no world, puzzle, chronicle or agent writes
- **`history.py`** — bounded, read-only provenance for narration (never searches by actor or time)
- **`recovery.py`** — read-only operator diagnostics behind `python main.py work-report`

### `server/` — API Layer
Threaded `http.server` with REST + WebSocket (HTTP/1.1 handshake), security headers (CSP, X-Frame-Options, …), POST/frame size caps. `/speak`, `/image`, `/agent/voice`, `/wayback`, `/node` and every write route resolve node identity server-side against the canonical world; every path sits behind `server.guard.world_seed` (ADR-007).
- **`handlers.py`** — HTTP dispatch and endpoint orchestration (the routing extraction into the sub-API pattern below is a standing commitment)
- **Sub-APIs:** `intervention_api.py` (`/interventions`, `/interventions/commit`), `participant_api.py` (`/me`, `/profile`, `/profile/save`, `/profile/home`, `/journal/data`, `/journal/note`), `situation_api.py` (`/situation`, `/situation/discover`, `/situation/choose`, `/situation/follow-up` — legacy continuity: `/situation/choose` refuses new choices while retaining existing receipts, #109), `ideas_api.py` (`/ideas/list`, `/ideas/detail`, `/ideas/search`, `/ideas/submit`, `/ideas/vote`, `/ideas/withdraw`), `idea_promotion.py` (operator publication with durable intent)
- **`guard.py`** — the invite gate, canonical-seed boundary, rate limiters, cost caps, kill switches; **`moderation.py`** — the fail-open two-tier input screen (ADR-004 §2); **`observability.py`** — JSON access log and Sentry
- **`heartbeat.py`** — the world runs unattended: a daemon loop sends the roster on paced traversals (FSM-driven, zero API spend) and a pump drains the four durable queues (staged causal hops, matured verbs, situation consequences, expressive work)
- **REST (core):** `/health`, `/worlds`, `/world`, `/node`, `/players`, `/history`, `/chronicle`, `/wayback`, `/agent`, `/observe` (SSE), `/puzzle`, `/puzzle/evidence`, `/image`, `GET`/`POST /position`, plus `POST /speak`, `/puzzle/attempt`, `/act`, `/agent/voice`, `/register`, `/client-error`
- **WebSocket** (`/ws`): presence, player-to-player chat, broadcast of causal and delivery events, ping/keepalive — `websocket.py` (upgrade + loop), `protocol.py` (RFC 6455 framing), `rooms.py` (presence + co-op `PuzzleSession`)
- **`world_mechanics.py`** — constellations, particle entanglement, canonical node hydration; **`imageprompt.py`** — per-level prompt assembly + style-signature cache key; **`history.py`** — post-commit presentation that never invalidates accepted work
- **Pages and static:** `/` (explorer), `/app` (React bundle), `/guide`, `/register`, `/journal`, `/ideas`, `/media/*`, the shared static modules, easter-egg routes under `/easter-egg/`

### `interface/` — Terminal Interaction Layer
Interactive terminal session (`run_session`) with three modes — spatial (`go`/`up`/`map`), conversational (`speak`), and ambient (`observe`) — plus inline puzzles and the original scale-native verbs. Each scale level renders in a distinct ANSI colour.

### `frontend/` — Browser Clients
- **`/app`** — React + PixiJS + Vite app (`frontend/src`, built into `static/app/`): scene rendering, hotspots, the Act surface (`Interventions.jsx`), Replay History (`Wayback.jsx`), chronicle, presence, journal links. Primary development surface since the ADR-005 2026-09-12 revision
- **`/`** — the vanilla D3 map explorer (`static/index.html` + `static/explorer.js`); still the invite destination; the only client with ambient `/observe`
- **Shared modules** (`static/`): `clientlogic.js` (entry, passage affordances, chronicle rendering), `interface.js` + `navigation.js` (identity block, Speak | Puzzle | Act, named passages, return trail), `intents.js` (request-ID receipts), `interventions.js` (the Act surface), `sensory.js` (deterministic scene from served senses), `score.js` (eleven sampled musical forms). `nodeart.js` is the explorer's fallback renderer. Curated plates and samples live in `static/media/`

### `puzzles/` — Embedded Challenges
- **`types.py`** — `Puzzle` dataclass (kind, attempts, hints, result)
- **`engine.py`** — `PuzzleEngine` (attach, collect, run); puzzles live in the engine keyed by node name, never in `node.properties`
- **`generators.py`** — per-node generation for all 11 scales: world-reading families (contextual seals, lineage/bond/enfold puzzles, Keeper Witnesses, Ancestral Compasses), the Causal Augury prediction family (ADR-010), and the decode families (anagrams, ciphers, sequences, riddles) as a minority. `node_difficulty` draws each node's 1–4 rating from its identity, never from depth
- **`gates.py`** — sealed passages (the LOCK puzzle's fiction made mechanical); a seal never traps someone already inside
- **`instances.py`** — durable first-use puzzle content: the definition a node first served is stored with its public evidence and an `epoch`; pure generators still describe future instances
- **`quality.py`** — the executable ecology census behind `scripts/puzzle_quality.py`; **`data.py`** — static fallback pools for unknown levels
- The server validates attempts so the answer never leaves the server; superseded questions are refused without consuming an attempt

---

## Interaction Patterns

All four patterns occur naturally within the same world model:

| Pattern | Mechanism |
|---------|-----------|
| Human → Human | Shared world state, cross-scale causality, pooled puzzle sessions, chat |
| Human → Agent | Direct conversation (`/agent/voice`), shared traversal space |
| Agent → Human | Causal effects, node voice encounters, a kept commitment |
| Agent → Agent | Shared traversal, deterministic banter, goal conflict/cooperation |

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
        ├──► Act on the place ──► persistence/interventions ──► commit now, discover as it settles
        │
        ├──► Trigger action ──► causality/ ──► propagate effects across scales, ring by ring
        │
        ├──► Encounter agent ──► agents/ ──► deterministic in-character banter (Claude-voiced only via /agent/voice)
        │
        └──► All state changes ──► persistence/ ──► append-only chronicle; the world evolves for all participants
```
