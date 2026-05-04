# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

### Added
- **Operational observability** (`server/observability.py`, `main.py`): three pieces aimed at running the hosted beta with eyes open. Optional Sentry integration — `SENTRY_DSN` + `pip install '.[sentry]'` enables forwarding uncaught request exceptions; unset DSN or missing SDK is a silent no-op (with a warning when DSN is set but the SDK isn't installed). `send_default_pii=False` keeps IPs and headers off the wire. Per-request structured access log emitted by `nested_worlds.access` as one JSON line carrying timestamp, hashed IP (SHA-1, 8 chars), method, path component (query string redacted so the invite key never reaches logs), status, latency in ms, and response length. `do_GET` / `do_POST` now wrap dispatch in a top-level try/except that routes uncaught exceptions through `capture_exception` and replies 500 instead of letting `BaseHTTPRequestHandler` close the connection silently. New `python main.py backup --to PATH` subcommand uses sqlite's online `Connection.backup()` to snapshot the live WAL-mode DB without pausing the server, creating parent dirs and setting 0o600 on the output for cron-style scheduling.
- **Beta hardening guardrails** (`server/guard.py`, `persistence/migrations/0003_cost_budget.sql`): six gates so a public beta URL is safe to share with invited testers. (1) Invite-key gate read from `NESTED_WORLDS_BETA_KEY`, accepted via `X-Beta-Key` header or `?key=` query param so the WebSocket connector — which can't easily set headers — still authenticates; `/health` is exempt so platform load balancers can probe without the secret. (2) Per-IP fixed-window rate limiter on `/speak`, `/agent/voice`, `/image`, `/puzzle/attempt` (default 20 req/min). Reads `X-Forwarded-For` only when `NESTED_WORLDS_TRUST_PROXY=1` so the header can't be spoofed in untrusted deploys. (3) Daily Anthropic call cap persisted in the new `cost_budget` table (migration 0003); past the cap, `/speak` and `/agent/voice` return a friendly "the worlds are quiet today" fallback instead of calling the API. (4) Daily fal.ai call cap on the same table; `/image` reports "daily image budget exhausted" past the cap. (5) Kill switches `NESTED_WORLDS_DISABLE_AI` and `NESTED_WORLDS_DISABLE_IMAGES` so the host can flip a secret without a redeploy. (6) Bounds on the four world-generator inputs (`depth`, `min_breadth`, `max_breadth`) applied centrally in `_build_world` so every endpoint that rebuilds the world tree (`/world`, `/observe`, `/puzzle`, `/puzzle/attempt`) inherits the clamp.
- **Animated presence overlays in the scene** (`frontend/src/components/SceneView.jsx`, `frontend/src/App.jsx`): when a `causal_event`, `agent_encounter`, or `puzzle_solved` arrives for the player's current node, a transient renders on top of the scene — an expanding ripple keyed off `EventKind` (gold for solves, red for failures, orange for danger, etc.), a converging-glyph encounter mark, or a four-pointed sparkle. Transients live in a separate Pixi `Container` driven by `app.ticker` so animations survive React re-renders, and are cleared on navigation. Player presence markers gained name labels and a name-hashed color palette so co-presence is legible at a glance. Closes the in-scene halves of game-design.md §"Solving the Myst Problem" rows 1 and 2 (Presence trails, Agent visibility).
- **Co-op puzzle sessions** (`server/rooms.py`, `server/handlers.py`): every `/puzzle/attempt` against the same `(seed, node_name)` now pools attempts and contributors across all players in the room. `PuzzleSession` tracks the shared attempt counter, the contributor set, and the first solver; `record_attempt()` is atomic under the room lock so concurrent solvers can't both claim. Once any player guesses correctly, the puzzle is marked solved for everyone — subsequent attempts return `result: SOLVED` with the original solver intact and the new caller appended to `contributors`. The `puzzle_solved` broadcast and the `PUZZLE_SOLVED` mutation now carry `solver` and `contributors`. The React (`frontend/src/App.jsx`) and D3 (`static/explorer.js`) clients render the solver-plus-contributors line in the event feed and pass `player_name` with their attempt. Closes the game-design.md *"Optional cooperation when players share goals"* line.
- The server now tracks puzzle attempts itself rather than trusting the client-supplied `attempt` field (which existed only as a leak guard via clamping). `correct_answer` is released on real failure (`session.attempts >= max_attempts`) and not before — a shorter, clearer security contract.
- **Test isolation** (`tests/conftest.py`): autouse fixture now also clears the global rooms registry between tests, so co-op puzzle state from one test never leaks into the next.
- **Dynamic puzzles at every level** (`puzzles/engine.py`, `puzzles/data.py`): all 11 canonical levels now resolve to property-driven generators (was 3-of-11 — Region, Universe, Planet). New generators cover Multiverse (ANAGRAM on theme), Galaxy (RIDDLE on shape), Planetary System (LOGIC on planet_count), Room (NAVIGATION on exits), Object (LOGIC on weight_kg), Molecule (LOGIC on bond_count), Atom (LOGIC on atomic_number), and SubatomicParticle (RIDDLE on particle_type). Galaxy and Particle riddles use new poetic clue maps in `puzzles/data.py` mirroring the existing `BIOME_CLUES` pattern. The static `LEVEL_POOLS` are kept as a graceful fallback for unknown levels.
- **Per-level node voicing** (`consciousness/`): `LEVEL_VOICES` catalog covers all 11 scales with distinct character notes (pronouns, time-sense, sensory vocabulary). `speak()` now sends three system blocks — universal preamble, per-level voice, per-node context — with cache breakpoints on the first two so a Region call shares its cached prefix with every other Region call. Closes the architecture-doc claim that each scale has its own register and complements the per-level visual baselines shipped in `server/imageprompt.py`.
- **Bidirectional causal propagation** (`causality/`, `multiverse/node.py`): `SpatialNode` now carries a `parent` pointer (set by `add_child` and the constructor's `children=` kwarg). `CausalityBus.propagate` gains a `direction` parameter (`down` | `up` | `both`, default `both`); origin fires exactly once, then the event cascades up the ancestor chain and/or down the subtree with the same per-hop dampening. Each fire bumps `node.ripple_score` proportional to the event's (already-dampened) strength, clamped to 1.0 — closing the README/ADR-002 callout that the field existed but was never mutated. Closes the README's *"carries effects up and down the hierarchy with dampening"* claim and lights up the seventh row of the `game-design.md` style matrix (high ripple weight → psychedelic).
- **Structured per-level image prompts** (`server/imageprompt.py`): closes ADR-002 §2 and the bulk of the game-design.md style matrix. Each of the 11 hierarchy scales gets a baseline aesthetic register from the design doc; `derive_modifiers()` adds property/history-driven mood tags (six of seven matrix rows: heavy agent activity, conflict, cooperation, pristine, corrupted, puzzle). The image cache key now folds in a short `style_signature(...)` so visuals regenerate when modifiers flip — not only when raw history count crosses a 5-event bucket.
- **Agent personas** (`agents/personas.py`): four archetypes — *tender*, *destabilizer*, *scholar*, *wanderer* — each with a voice preamble. Personas are auto-assigned deterministically from the agent's name (sha1-keyed) and can be overridden via the `persona` query/body param on `/agent`, `/observe`, and the new `/agent/voice` endpoint. The chosen persona surfaces in `AgentLog.persona`, `Agent.report()`, every causal-event payload (`{"agent": ..., "persona": ...}`), `world_mutations` rows, and the `agent_encounter` broadcast (`agent1_persona` / `agent2_persona`). Closes the README/architecture-doc claim that agents have *"distinct personalities"* and *"some destabilize; some tend."*
- **Agent voicing** (`consciousness.voice_agent`, `POST /agent/voice`): an agent speaks AS itself in its persona's voice, distinct from the existing node-voice path (`speak()`). The shared agent system preamble is prompt-cached.
- **Broader mutation recording** (`server/`, `interface/`): every interaction surface now lands in `world_mutations`, not just puzzle solves. Agent traversals (`AGENT_VISIT`, `DANGER_ALERT`) record via a per-request causality bus handler in `/agent` and `/observe`; failed puzzles record `PUZZLE_FAILED`; player chat records `PLAYER_CHAT` against the speaker's current node; `/speak` and the CLI `_speak_to` record `PLAYER_SPEAK`. Closes Phase 1 carry-over §1 — consciousness prompts and image-cache invalidation now see a richer history signal.
- **Test isolation** (`tests/conftest.py`): autouse fixture redirects `persistence._DB_PATH` per test, so server tests no longer touch `~/.nested-worlds/worlds.db`.
- **Browser frontend** (`frontend/`): React + PixiJS + Vite client wired to the WebSocket server. AI-generated scene backgrounds via fal.ai (Flux Schnell), cached in persistence
- **WebSocket multiplayer** (`server/`): `/ws` endpoint with presence, player-to-player chat, ping/keepalive, and broadcast of causal events to all connected clients
- **Persistent agent memory** (`agents/`, `persistence/`): agents remember visited nodes across runs; `save_agent_memory` / `load_agent_memory` / `list_agent_memories`
- **Agent-to-agent encounters** (`agents/`): when traversing agents meet, encounter events are emitted into the causal bus
- **Interaction-history-aware consciousness** (`consciousness/`): per-node history from `persistence.get_node_history` is injected into the prompt so nodes reference past visitors
- **Browser UI** (`static/app/`): vanilla D3 tree explorer mounted at `/app`; supports Observe and Puzzle actions
- **Easter eggs**: hidden routes under `/easter-egg/` (Konami code, illusion page)
- **Server module split** (`server/handlers.py`, `protocol.py`, `rooms.py`) and HTTP server integration tests
- **Interactive interface** (`interface/`): `run_session()` brings the world to life as a playable terminal session. Three interaction modes in a single REPL:
  - *Spatial* — navigate the hierarchy with `go <N>` / `up`; each scale level rendered in a distinct ANSI colour
  - *Conversational* — `speak [message]` routes to the consciousness module (Claude); unrecognised input is forwarded as a speak message
  - *Ambient* — `observe` runs an agent traversal from the current node with live causal-event output (node name, event kind, dampened strength bar)
  - `map` prints an ASCII subtree (3 levels deep); `puzzle` drops into the puzzle engine at the current location
- **`play` CLI subcommand** (`main.py`): `python main.py play [--depth N] [--min-breadth N] [--max-breadth N]`
- **Architecture decision records** (`docs/decisions/`): ADR-001 (frontend stack), ADR-002 (image generation); Phase 1 beta scope (`docs/roadmap/`); game design doc (`docs/design/`); infrastructure stack (`docs/infrastructure/`)
- **`multiverse/utils.py`**: `count_nodes`, `find_node`, `build_depth_map` extracted from scattered call sites
- Test suite expanded to **297 tests** (HTTP server integration, WebSocket frame parsing, consciousness thread-safety, persistence, interface, beta guards, observability, etc.)

### Changed
- **Puzzle system**: reworked into level-specific pools across all 11 hierarchy levels; attempts validated on the server (no client-controlled answer leak)
- **REST endpoints** added: `/observe`, `/puzzle`, `/players`, `/history`, `/image`, `POST /speak`, `POST /puzzle/attempt`
- Default server bind host changed to `127.0.0.1` (was `0.0.0.0`)
- `persistence/` no longer exposes a noisy boilerplate decorator; surface API simplified

### Security
- CSP and security headers (`X-Frame-Options`, `Referrer-Policy`, etc.) on all responses
- `escHtml` applied to every `innerHTML` insertion in the browser UI
- POST body size cap and WebSocket frame size limit
- Sanitised `/speak` inputs and thread-safe Anthropic client initialisation
- Puzzle attempt counter moved server-side


### Changed
- **Project renamed** to *Nested Worlds Adventure* (`pyproject.toml`, CLI, server banner, README)
- **Planetary System** added between Galaxy and Planet in the 11-level hierarchy (`multiverse/generator.py`); includes star_type, planet_count, habitable_zone, and asteroid_belt properties
- **Self-preservation** replaces "danger avoidance" throughout the agent system: `should_avoid` renamed to `should_preserve`, log messages changed from "avoided" to "withdrew", CLI help updated
- **Puzzle engine** expanded with four new `PuzzleKind` variants: `PATTERN`, `LOGIC`, `ANAGRAM`, `NAVIGATION` — each with multiple puzzle instances
- Default `max_depth` updated to 11 to match the expanded 11-level hierarchy



### Vision
Reframed as a shared persistent multiverse for simultaneous human and AI participation. Core new systems identified: node consciousness (Claude-powered voice layer), causality engine (cross-scale propagation), persistence (world state database), server (real-time API), and interface (generative visual layer). README and architecture docs updated to reflect new direction. New module directories scaffolded.

### Added
- **Enriched generator** (`multiverse/generator.py`): named locations (e.g. "Kethara", "Verdant Hollow"), variable branching (`min_breadth`/`max_breadth`), and richer level-specific properties (biome, faction control, particle spin, etc.)
- **Agent system** (`agents/`): `Agent` class with FSM traversal (`Idle → Explore → Interact → Exit`), danger-avoidance logic, interaction detection, and structured traversal logs
- **Puzzle engine** (`puzzles/`): `Puzzle` type with four kinds (Riddle, Cipher, Lock, Sequence), attempt tracking, hints, and `PuzzleEngine` for attaching/collecting puzzles from the world graph
- **Test suite** (`tests/`): 33 pytest tests covering generator determinism, agent FSM transitions, avoidance, puzzle solving, and engine idempotency
- **CLI** (`main.py`): `argparse`-based interface with three subcommands: `world`, `agent`, `puzzles`

---

## [Phase 1.5] — 2025-09-13

### Added
- Metadata generation for `SpatialNode` objects by level (gravity, element, danger_level, etc.)

## [Phase 1] — 2025-09-13

### Added
- `SpatialNode` class with recursive children and properties dict
- `generate_node_hierarchy()` with seed-based deterministic generation
- 10-level spatial hierarchy: Multiverse → … → SubatomicParticle
- Project folder structure: `multiverse/`, `agents/`, `puzzles/`, `docs/`
