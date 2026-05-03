# Infrastructure Stack

The as-built Phase 1 stack. Diverges from the original ADRs in three places (FastAPI → stdlib `http.server`, Redis → SQLite, Cloudflare R2 → fal.ai-hosted URL caching). See ADR-001 and ADR-002 for the rationale and revisit triggers.

| Layer | Service | Notes |
|-------|---------|-------|
| Browser frontend | React + PixiJS + Vite (`frontend/`) | Scene rendering, hotspots, multiplayer presence; built into `static/app/` |
| Browser frontend (alt) | Vanilla D3 (`static/index.html` + `static/explorer.js`) | Tree explorer served at `/` directly by the Python server |
| Backend HTTP/WebSocket | Python stdlib `http.server` + `ThreadingMixIn` (`server/`) | Threaded, no external HTTP framework; security headers + CSP + body/frame caps |
| WebSocket protocol | Hand-rolled framing via `struct` (`server/protocol.py`) | Subset we use: text frames + ping; ~55 lines |
| Multiplayer state | In-memory rooms (`server/rooms.py`) | Per-seed presence, broadcast, chat |
| Image generation | fal.ai (`fal-ai/fast-sdxl`) via `urllib` | Pay-as-you-go, no SDK dependency |
| Image cache + storage | SQLite (`persistence.cache_image`) | Cache key includes a coarse interaction-history bucket so visuals refresh as the node evolves |
| Persistence | SQLite (`persistence/`) | World state, agent runs, agent memory, node interaction history, world mutations, image cache |
| LLM | Anthropic (Claude) via official SDK | Node consciousness (`/speak`) and agent personas |

## Runtime requirements

- Python 3.11+ (stdlib server, no external HTTP framework)
- Node 22+ (only for building the React frontend; not required to run the server)
- `ANTHROPIC_API_KEY` for `/speak`
- `FAL_KEY` for AI scene backgrounds (optional — frontend gracefully degrades)

## Migration triggers

See ADR-001 ("Revisit when…") and ADR-002 ("Revisit when…") for the conditions under which any layer of this stack should be replaced (concurrent WebSocket scaling, multi-host deployment, fal.ai URL expiration, etc.).
