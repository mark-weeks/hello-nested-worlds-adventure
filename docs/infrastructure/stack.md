# Infrastructure Stack

The as-built stack, refreshed against `main` at #108 (2026-10-03). It diverges
from the original ADRs in three places (FastAPI → stdlib `http.server`, Redis →
SQLite, Cloudflare R2 → fal.ai-hosted URL caching). See ADR-001 and ADR-002 for
the rationale and revisit triggers, and ADR-003 for the persistence contract.

| Layer | Service | Notes |
|-------|---------|-------|
| Browser frontend (scene) | React + PixiJS + Vite (`frontend/`) | Scene rendering, hotspots, Act surface, journal, multiplayer presence; built into `static/app/` and served at `/app`. Primary development surface since the ADR-005 2026-09-12 revision |
| Browser frontend (map) | Vanilla D3 (`static/index.html` + `static/explorer.js`) | Tree explorer served at `/` directly by the Python server; still the invite destination (ADR-005) |
| Shared client modules | `static/clientlogic.js`, `interface.js`, `navigation.js`, `intents.js`, `interventions.js`, `sensory.js`, `score.js` | Entry/affordance/chronicle rules, navigation vocabulary, request-ID receipts, the Act surface, deterministic senses and the sampled score, consumed by both clients. `nodeart.js` remains the explorer's fallback renderer |
| Local media | `static/media/` (four PNG plates, eleven VSCO 2 CE samples, manifests) | Ships in the wheel; no provider needed for the curated places or the score. Provenance in `docs/media/expressive-world.md` |
| Backend HTTP/WebSocket | Python stdlib `http.server` + `ThreadingMixIn` (`server/`) | Threaded, no external HTTP framework; security headers + CSP + body/frame caps; sub-API modules for interventions, participants, situations and Ideas |
| WebSocket protocol | Hand-rolled framing via `struct` (`server/protocol.py`) | Full RFC 6455 framing — masking enforcement, fragmentation reassembly, ping/pong, close handshake; conformance-tested against a real client |
| Multiplayer state | In-memory rooms (`server/rooms.py`) | Per-world presence, broadcast, chat, pooled co-op puzzle sessions |
| Background work | In-process daemon threads (`server/heartbeat.py`) | The world heartbeat (FSM agents, zero API spend) and the pump that drains staged causal hops, matured verbs, situation consequences and expressive work from durable SQLite queues |
| Image generation | fal.ai (`fal-ai/fast-sdxl`) via `urllib` | Optional enhancement wash over the local renderers; pay-as-you-go, no SDK dependency |
| Image cache + storage | SQLite (`persistence.cache_image`) | Cache key includes a coarse interaction-history bucket and a style signature so visuals refresh as the node evolves |
| Persistence | SQLite, WAL mode (`persistence/`, 27 additive migrations) | World identity (`world_nodes`, `world_meta`), chronicle and chronicled deltas, agent runs and memory, puzzle results and stored first-use puzzle content, invite keys and registration, participants/journal/profile, situations, Ideas, delivery queues, cost budgets, image cache |
| LLM | Anthropic (Claude) via the official SDK | Four call sites: node voice, agent voice, moderation classify (Haiku) and intention interpretation; prompt-cached bibles; authored fallbacks when no key or budget |
| Deployment | Fly.io, one VM, one persistent volume (`Dockerfile`, `fly.toml`, `scripts/deploy.sh`) | Runbook in `docs/infrastructure/fly-deployment.md`; deploys refuse to run over an unbacked chronicle. Not yet deployed |
| Off-host backup | GitHub Actions (`.github/workflows/backup.yml`) | Hourly dispatched online SQLite backup; continuous replication is the first post-launch batch (ADR-005) |
| Error reporting | Sentry (`sentry-sdk`, default dependency) | Active when `SENTRY_DSN` is set |

## Runtime requirements

- Python 3.11 (pinned by `pyproject.toml`, `.python-version`, the Dockerfile and CI, for deterministic world birth; stdlib server, no external HTTP framework)
- Node 20.19 (pinned by `.nvmrc`, CI and the Dockerfile; only for building the React frontend, not required to run the server)
- `ANTHROPIC_API_KEY` for live voices and intention interpretation (the world degrades in character without it)
- `FAL_KEY` for AI scene backgrounds (optional — both clients render without it)

## Migration triggers

See ADR-001 ("Revisit when…"), ADR-002 ("Revisit when…") and ADR-003 for the
conditions under which any layer of this stack should be replaced (concurrent
WebSocket scaling, multi-host deployment, fal.ai URL expiration, measured
SQLite contention). The phase-2 plan (`docs/roadmap/phase-2-scale.md`) lists
the observable signals that pull each one forward.
