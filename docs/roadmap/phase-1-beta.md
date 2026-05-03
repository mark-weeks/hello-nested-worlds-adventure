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

- **Cache invalidation by interaction richness.** Currently the cache key buckets `len(get_node_history) // 5`, which only changes for nodes that get `record_mutation`-recorded events. Today only `PUZZLE_SOLVED` calls that. Wiring `AGENT_VISIT`, `PLAYER_SPEAK`, etc. into `record_mutation` would make the visual evolution premise actually function across the world.
- **Structured prompt assembly per level** — current prompt is a flat property dump (see ADR-002 "Unmet Phase 1 commitments §2"). Per-level `HIERARCHY_STYLES` baselines would make the eleven scales visually distinct.
- **React client name prompt** — the React app at `/app/` currently hardcodes the player name `"Traveller"`; the D3 explorer at `/` prompts via a join modal. They should match.

---

## Out of Scope for Phase 1 (deferred to Phase 2)

- Animated ripple effects on the multiverse graph
- Cooperative mechanics in-product
- Full multiverse map view (D3 / Cytoscape)
- IP-Adapter scene conditioning
- Style zone LoRAs
- Pan animation polish
- First-party image hosting (R2 or equivalent) — see ADR-002 "Revisit when…" for the trigger
