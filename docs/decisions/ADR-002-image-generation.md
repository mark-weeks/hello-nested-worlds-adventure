# ADR-002: Image Generation Architecture

**Status:** Revised 2026-05-03 — implementation diverged from the original decision; this revision records what shipped, what is deliberately deferred, and what remains an unmet Phase 1 commitment.

---

## Phase 1 Approach: Prompt Engineering Only

No IP-Adapter or LoRA conditioning at beta. Consistency is achieved through structured prompt templates and node-ID-seeded randomness. Thematic coherence is sufficient for Phase 1 — pixel-perfect consistency is neither required nor desirable given that style drift is a core mechanic. **This still holds.**

---

## Prompt Assembly (as built)

Lives in `server/imageprompt.py`, called from `server/handlers.py::_do_image`. Three pieces:

1. **`HIERARCHY_STYLES`** — per-level aesthetic baseline string, covering all 11 scales (Multiverse → SubatomicParticle).
2. **`derive_modifiers(properties, history)`** — implements the property→signal matrix from `docs/design/game-design.md`. Six of seven rows are live (agent activity, conflict, cooperation, pristine, corrupted, puzzle). The seventh — *high ripple weight* — still waits on causality→`ripple_score` being mutated.
3. **`assemble_prompt(level, name, properties, history)`** — combines baseline + modifiers + property summary into the final fal.ai prompt.

Inputs are the same `world_mutations` rows the cache key already consumes; no extra DB calls vs. the previous flat-dump prompt.

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
| Generate | Once per `(seed, node_id, history_bucket, style_signature)` | Once on node discovery | ✓ matches intent |
| Cache | SQLite (`persistence.cache_image`), keyed to `f"{seed}:{node_id}:{history_bucket}:{sig}"` | Redis hash, keyed to `node_id` | Backend swap — see "Why" |
| Invalidate | Cache key folds in `len(history) // 5` (count bucket) **and** `imageprompt.style_signature(...)` (modifier flip) | When `ripple_score` shift > 0.3 | ✓ same intent, different signal — see "Invalidation signal" |
| Store | fal.ai-hosted URL (string in SQLite) | Cloudflare R2 as `.webp` | Backend swap — see "Why" |

### Invalidation signal

The original ADR keyed invalidation off `ripple_score`, a field on `SpatialNode`. That field is now mutated on every causality-bus fire (`causality/__init__.py::CausalityBus._fire`), but it lives in memory on the in-process tree — not in persistence — so the server cache layer still doesn't have a cross-request handle on it. The cache key instead folds in (a) a coarse bucket of accumulated interaction history (`world_mutations` rows for the node, divided by 5) and (b) a style-modifier signature (`server.imageprompt.style_signature`). Together these deliver the user-visible behaviour the ADR promised — visuals refresh as a node accumulates state, *and* refresh whenever the modifier mix would change.

Persisted `ripple_score` (so the cache layer can read it across requests) remains a future enhancement; until then the high-ripple matrix row uses total mutation count as a serviceable proxy.

---

## Why this diverges from the original decision

- **Redis → SQLite.** A single SQLite database now handles all persistence (world state, agent memory, node history, mutations, *and* image cache). Solo dev benefits from one persistence layer. Redis is preserved as a future option once multi-process or multi-host deployment is required.
- **Cloudflare R2 .webp → fal.ai-hosted URLs.** We currently cache the URL fal.ai returns rather than re-hosting the image. This is cheaper (no R2 bucket, no transcode, no egress accounting) and ships faster, but couples us to fal.ai URL lifetime — see "Revisit when…".
- **Flux Schnell → fast-sdxl.** Incidental model choice during implementation. Cost per image and latency are comparable.

Net effect: simpler stack, same observable behavior for Phase 1 — *with one consequential omission* (invalidation).

---

## Unmet Phase 1 commitments

These are not deferrals — they are gaps that should be closed before Phase 1 beta is considered complete, because they tie directly to the world-evolution premise.

### 1. ~~Ripple-score-based cache invalidation~~ — closed via interaction-history signal

**Resolved.** Cached images now refresh as a node accumulates interactions; see the "Invalidation signal" subsection above. The original `ripple_score` field remains unused — when causality→ripple_score is wired up, the signal can swap in without changing the cache contract.

### 2. ~~Structured prompt assembly~~ — closed via `server/imageprompt.py`

**Resolved.** Per-level baselines (`HIERARCHY_STYLES`) cover all 11 scales, and six of the seven property→signal matrix rows from `docs/design/game-design.md` are live. The seventh (*high ripple weight*) waits on causality→`ripple_score` mutation to land.

The cache key now includes a style signature so a modifier flip (e.g. crossing the AGENT_VISIT≥5 threshold, or DANGER_ALERT appearing for the first time) regenerates the image even if the count bucket hasn't advanced.

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
