# ADR-002: Image Generation Architecture

**Status:** Revised 2026-05-03 — implementation diverged from the original decision; this revision records what shipped, what is deliberately deferred, and what remains an unmet Phase 1 commitment.

---

## Phase 1 Approach: Prompt Engineering Only

No IP-Adapter or LoRA conditioning at beta. Consistency is achieved through structured prompt templates and node-ID-seeded randomness. Thematic coherence is sufficient for Phase 1 — pixel-perfect consistency is neither required nor desirable given that style drift is a core mechanic. **This still holds.**

---

## Prompt Assembly (as built)

Currently in `server/handlers.py::_do_image`:

```python
prop_summary = ", ".join(f"{k}: {v}" for k, v in list(node_props.items())[:6])
prompt = (
    f"A {node_level.lower()} in a nested multiverse sci-fi world. "
    f"{prop_summary}. "
    "Cinematic lighting, intricate detail, deep space aesthetic, "
    "dark palette with bioluminescent accents."
)
```

This is a thinner version of what the original ADR prescribed. It produces serviceable images but does not yet incorporate per-level style baselines (`HIERARCHY_STYLES`), structured property modifiers, `ripple_score` weighting, or `interaction_summary` history marks. The node fields exist (`multiverse/node.py:21-22`) and are wired into the world model — just not into prompt assembly.

Acceptable for Phase 1 beta; richer assembly is a near-term enhancement, not a blocker.

---

## Generation Backend (as built)

| Aspect | Decision (original) | As built |
|--------|--------------------|----------|
| Provider | fal.ai | fal.ai ✓ |
| Model | Flux Schnell | `fal-ai/fast-sdxl` |
| Steps | — | `num_inference_steps: 4` |
| Size | — | `landscape_4_3` |
| Transport | — | `urllib` (no SDK dependency) |

The model swap to `fast-sdxl` is incidental — comparable cost and quality; revisit only if image quality becomes a complaint.

---

## Caching Strategy (as built)

| Step | As built | Original prescription | Status |
|------|----------|-----------------------|--------|
| Generate | Once per `(seed, node_id)` | Once on node discovery | ✓ matches intent |
| Cache | SQLite (`persistence.cache_image`), keyed to `f"{seed}:{node_id}"` | Redis hash, keyed to `node_id` | Backend swap — see "Why" |
| Invalidate | Never | When `ripple_score` shift > 0.3 | **Not implemented — see "Unmet Phase 1 commitments"** |
| Store | fal.ai-hosted URL (string in SQLite) | Cloudflare R2 as `.webp` | Backend swap — see "Why" |

---

## Why this diverges from the original decision

- **Redis → SQLite.** A single SQLite database now handles all persistence (world state, agent memory, node history, mutations, *and* image cache). Solo dev benefits from one persistence layer. Redis is preserved as a future option once multi-process or multi-host deployment is required.
- **Cloudflare R2 .webp → fal.ai-hosted URLs.** We currently cache the URL fal.ai returns rather than re-hosting the image. This is cheaper (no R2 bucket, no transcode, no egress accounting) and ships faster, but couples us to fal.ai URL lifetime — see "Revisit when…".
- **Flux Schnell → fast-sdxl.** Incidental model choice during implementation. Cost per image and latency are comparable.

Net effect: simpler stack, same observable behavior for Phase 1 — *with one consequential omission* (invalidation).

---

## Unmet Phase 1 commitments

These are not deferrals — they are gaps that should be closed before Phase 1 beta is considered complete, because they tie directly to the world-evolution premise.

### 1. Ripple-score-based cache invalidation

**Why it matters:** the design premise is a causally evolving multiverse where node visuals reflect accumulated state. With static `(seed, node_id)` cache keys, a node's image is fixed at first discovery and never reflects subsequent causal pressure or interaction history. The `ripple_score` and `interaction_summary` fields already exist on `SpatialNode` but are not consumed by image generation.

**Smallest viable implementation:**
- Include a coarse bucket of `ripple_score` (e.g., rounded to 0.3) and an `interaction_summary` token in the cache key
- Or: keep the simple key, but check `ripple_score` delta against the cached row's stored score and regenerate when delta > 0.3
- Either approach is single-digit lines of change

### 2. Structured prompt assembly

**Why it matters:** the current prompt is a flat property dump. Per-level baselines (`HIERARCHY_STYLES`) and ripple/history weighting would make the visual register actually distinct across the eleven scales — which is a stated design goal in the README ("each with its own aesthetic register").

**Lower priority than (1)** — visuals are serviceable now, and this is iterative.

---

## Revisit when…

Move from fal.ai-URL caching to first-party storage (R2 or equivalent) when *any* of:

- fal.ai URL expiration becomes observable (cached URLs return 404)
- Image volume × storage cost exceeds R2's free tier (10 GB) — at ~150 KB/image that's ~70k images
- Compliance or branding requires hosting our own assets
- We need image transformations (resize, format conversion) at request time

Move from SQLite to Redis for the cache layer when:

- Multi-process or multi-host deployment ships (parallel to ADR-001's persistence trigger)
- Cache hit-rate metrics or per-key TTLs become operationally useful

Reconsider the model (fast-sdxl → Flux Schnell or other) when:

- Image quality becomes a recurring user complaint
- Cost per image drifts materially against budget

---

## Cost Model (current)

| Item | Cost |
|------|------|
| fal.ai `fast-sdxl` | ~$0.003 / image (comparable to original Flux Schnell estimate) |
| 100 beta players × 10 node discoveries / session | ~$3 / session in generation |
| Storage | $0 (fal.ai-hosted URLs cached as strings in SQLite) |
| Target monthly budget | < $20 (generation only, until R2 trigger fires) |

---

## Phase 2 Upgrade Path (unchanged)

- **IP-Adapter reference conditioning** — when player return frequency makes consistency a retention issue
- **Style zone LoRAs** (~$10–30 one-time training per zone) — when world visual coherence becomes a competitive priority
