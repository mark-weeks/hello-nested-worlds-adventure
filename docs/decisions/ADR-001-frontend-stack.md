# ADR-001: Stack Selection

**Status:** Revised 2026-05-03 — implementation diverged from the original decision; this revision records what actually shipped and the triggers for revisiting.

---

## Context

Enfolded requires a multiplayer-capable client and server for a multiverse node-traversal game. Two hard constraints shape every choice:

- **Solo dev** — fast path to beta, minimal operational surface
- **Budget** — minimal infrastructure cost, preference for free tiers and pay-as-you-go

---

## Decision (as built)

**React + PixiJS (Vite) + Python stdlib `http.server` with hand-rolled WebSocket + fal.ai + SQLite**

| Component | Role | Notes |
|-----------|------|-------|
| React + Vite | All non-game UI: lobbies, text panels, node history, player presence indicators | `frontend/` |
| PixiJS | Scene rendering, hotspot detection, pan interaction within nodes | `frontend/src/` |
| Python stdlib `http.server` + `ThreadingMixIn` | Threaded HTTP server, REST endpoints, static file serving | `server/__init__.py`, `server/handlers.py` |
| Hand-rolled WebSocket (`struct`) | Real-time multiplayer: presence, chat, causal-event broadcast | `server/protocol.py`, `server/rooms.py` |
| fal.ai (`fal-ai/fast-sdxl` via `urllib`) | AI scene generation, pay-as-you-go | `server/handlers.py:/image` |
| SQLite (`persistence/`) | Scene-image cache, world state, agent memory, node history, mutations | `persistence/__init__.py` |

---

## Why this diverges from the original decision

The original ADR named **FastAPI WebSockets**, **Redis** (scene cache), **Cloudflare R2** (image storage), and **Flux Schnell**. None of those shipped:

- **FastAPI → stdlib `http.server`.** The original rationale was "Python-primary, no new runtime required." The stdlib choice honors that constraint *more strictly* — zero new runtime dependencies (no uvicorn/hypercorn). With ~780 lines of server code, 116 tests passing, and security headers / body and frame size caps already in place, the stdlib server has met every Phase 1 requirement.
- **Redis / R2 → SQLite.** A single SQLite database now handles world state, agent runs, agent memory, node history, world mutations, *and* the scene-image cache. One persistence layer beats three for solo dev. R2 may still be relevant if image volume grows beyond local disk.
- **Flux Schnell → fast-sdxl.** Cost per image is comparable; the model swap is incidental. ADR-002 should be updated to match.

Net effect: fewer moving parts than the original decision, same capability surface for Phase 1.

---

## Trade-offs accepted

The stdlib + hand-rolled WebSocket choice carries known costs:

- **Thread-per-connection scaling.** `ThreadingMixIn` allocates one OS thread per open WebSocket. Fine for tens of concurrent players; problematic at hundreds.
- **Hand-rolled WebSocket protocol.** `server/protocol.py` covers the subset we use (text frames, ping). Fragmentation, compression, backpressure, and edge cases are ours to maintain.
- **`http.server` is "not recommended for production"** by the Python docs. Mitigations in place: CSP and security headers, body/frame size caps, thread-safe Anthropic client init, sanitised inputs, server-side puzzle validation.
- **No Pydantic / OpenAPI.** Validation is hand-rolled; no auto-generated API docs.

These are acceptable for the current scale and team size.

---

## Revisit when…

Migrate to FastAPI (or similar async framework) when *any* of the following becomes true:

- Concurrent WebSocket clients consistently exceed ~100, or thread count becomes a host-resource concern
- A new feature requires WebSocket fragmentation, per-message compression, or non-trivial backpressure handling
- Validation / OpenAPI / dependency-injection benefits begin to outweigh migration cost (e.g., an external API consumer ships against the server)
- The hand-rolled protocol code accumulates more than one bug per quarter
- Authentication / session management beyond the current presence model is needed

Migrate from SQLite-only persistence when:

- Scene-image cache volume exceeds practical local-disk limits → introduce R2
- Multi-process or multi-host deployment is required → introduce Redis or equivalent

---

## Rejected Alternatives (frontend rendering)

**Phaser.js** — Overkill for a point-and-click interaction model. Adds physics and sprite overhead that the game does not need.

**Godot HTML export** — Large bundles, multiplayer relay complexity, diverges from the Python-primary stack.

**2D tile-based (Stardew-style)** — High effort, low differentiation, wrong fit for node graph design.

**Full 3D with character movement** — Out of scope for solo dev beta timeline.
