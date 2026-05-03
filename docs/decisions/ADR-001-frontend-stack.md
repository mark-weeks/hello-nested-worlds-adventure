# ADR-001: Frontend Stack Selection

**Status:** Decided

---

## Context

Nested World Adventure requires a multiplayer-capable frontend for a multiverse node-traversal game. Two hard constraints shape every choice:

- **Solo dev** — fast path to beta, minimal operational surface
- **Budget** — minimal infrastructure cost, preference for free tiers and pay-as-you-go

---

## Decision

**React + PixiJS + FastAPI WebSockets + fal.ai (Flux Schnell) + Redis + Cloudflare R2**

---

## Rationale

| Component | Role |
|-----------|------|
| React | All non-game UI: lobbies, text panels, node history, player presence indicators |
| PixiJS | Scene rendering, hotspot detection, pan interaction within nodes |
| FastAPI WebSockets | Real-time multiplayer — Python-primary, no new runtime required |
| fal.ai Flux Schnell | AI scene generation (~$0.003/image), pay-as-you-go |
| Redis | Scene hash caching and regeneration threshold tracking |
| Cloudflare R2 | Image storage — free tier 10 GB, zero egress cost |

---

## Rejected Alternatives

**Phaser.js** — Overkill for a point-and-click interaction model. Adds physics and sprite overhead that the game does not need.

**Godot HTML export** — Large bundles, multiplayer relay complexity, diverges from the Python-primary stack.

**2D tile-based (Stardew-style)** — High effort, low differentiation, wrong fit for node graph design.

**Full 3D with character movement** — Out of scope for solo dev beta timeline.
