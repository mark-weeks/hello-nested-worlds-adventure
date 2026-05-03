# ADR-002: Image Generation Architecture

**Status:** Decided

---

## Phase 1 Approach: Prompt Engineering Only

No IP-Adapter or LoRA conditioning at beta. Consistency is achieved through structured prompt templates and node-ID-seeded randomness. Thematic coherence is sufficient for Phase 1 — pixel-perfect consistency is neither required nor desirable given that style drift is a core mechanic.

---

## Prompt Assembly (Python)

Scene prompts are programmatically assembled from node state:

```python
def build_prompt(node):
    base_style = HIERARCHY_STYLES[node.level]
    property_modifiers = get_style_modifiers(node)  # from property matrix
    evolution_weight = node.ripple_score             # 0.0–1.0
    history_marks = node.interaction_summary         # "conflict", "cooperation", etc.
    return (
        f"{base_style}, {property_modifiers}, {history_marks}, "
        "cinematic composition, depth of field, no text, no UI elements"
    )
```

---

## Caching Strategy

| Step | Detail |
|------|--------|
| Generate | Once on node discovery |
| Cache | Scene hash in Redis, keyed to `node_id` |
| Invalidate | When `ripple_score` shift exceeds regeneration threshold (default: `> 0.3`) |
| Store | Cloudflare R2 as `.webp` |

---

## Cost Model

| Item | Cost |
|------|------|
| fal.ai Flux Schnell | ~$0.003 / image |
| 100 beta players × 10 node discoveries / session | ~$3.60 / session in generation |
| Target monthly infrastructure budget | < $20 (generation + Redis + R2) |

---

## Phase 2 Upgrade Path (not Phase 1)

- **IP-Adapter reference conditioning** — when player return frequency makes consistency a retention issue
- **Style zone LoRAs** (~$10–30 one-time training per zone) — when world visual coherence becomes a competitive priority
