# Phase 1 Beta Scope

Status reflects what shipped to `main`. See the [CHANGELOG](../CHANGELOG.md) for commit-level detail.

---

## Shipped

1. **AI-generated scene image per node** — `fal-ai/fast-sdxl` via fal.ai (model swap from Flux Schnell — see ADR-002), prompt assembled per-node from level + properties, cached in SQLite
2. **Clickable hotspots with hover states** — PixiJS scenes rendered in `frontend/`, child nodes navigable
3. **Text panel alongside scene** — node level / name / properties + presence + event feed in the React UI
4. **Basic multiplayer presence** — WebSocket-based; other player markers and movement broadcast in real time
5. **Graph traversal end-to-end** — REST + WebSocket; world state persists in SQLite across sessions
6. **Causal-event broadcasting** — `causality/` events fan out to all connected clients
7. **Persistent agent memory** — agents remember visited nodes across runs

---

## Not yet shipped (carry-over to Phase 1 close-out)

- ~~**Cache invalidation by interaction richness.**~~ Shipped. `AGENT_VISIT`, `DANGER_ALERT`, `PUZZLE_FAILED`, `PLAYER_SPEAK`, and `PLAYER_CHAT` now route through `persistence.record_mutation`, so the `len(get_node_history) // 5` bucket actually advances across the world rather than only on puzzle solves.
- ~~**Structured prompt assembly per level**~~ Shipped. `server/imageprompt.py` covers all 11 levels with `HIERARCHY_STYLES` baselines plus property/history-driven mood modifiers. Cache key includes a style signature so a modifier flip regenerates the image.
- ~~**React client name prompt**~~ Shipped. `frontend/src/App.jsx` renders a `NameEntry` form on first load and persists the chosen name to `localStorage`, matching the D3 explorer's join modal.

---

## Out of Scope for Phase 1 (deferred to Phase 2)

- ~~Animated ripple effects on the multiverse graph~~ Shipped — animated causal ripples / ring flashes render in both clients; see CHANGELOG
- ~~Cooperative mechanics in-product~~ Shipped — co-op puzzle sessions (`server/rooms.py::PuzzleSession`) pool attempts/contributors per room; see CHANGELOG
- ~~Full multiverse map view (D3 / Cytoscape)~~ Shipped — the vanilla D3 explorer (`static/explorer.js`, served at `/`) is the map view and the default invite target
- IP-Adapter scene conditioning
- Style zone LoRAs
- Pan animation polish
- First-party image hosting (R2 or equivalent) — see ADR-002 "Revisit when…" for the trigger
