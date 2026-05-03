"""Image-prompt assembly for fal.ai scene generation.

Closes ADR-002 §2 — Structured prompt assembly. Each of the 11 hierarchy
scales now has a baseline aesthetic register from `docs/design/game-design.md`,
and the node's accumulated interaction history (from `world_mutations`,
populated by every interaction surface as of the previous change) layers
property-driven style modifiers on top.

The prompt is fully deterministic given (level, properties, history); a
short signature of the same inputs is folded into the cache key so visuals
regenerate when the style would visibly change, not just when raw history
count crosses a 5-event bucket.
"""
from __future__ import annotations

import hashlib
from typing import Iterable


# Per-level aesthetic baselines. Sourced from `docs/design/game-design.md`
# and extended to cover all 11 levels of the hierarchy.
HIERARCHY_STYLES: dict[str, str] = {
    "Multiverse":        "abstract, luminous, impossibly vast, fractal cosmology",
    "Universe":          "cosmic web, dark energy filaments, deep field astronomy",
    "Galaxy":            "dreamy, soft light, deep color, spiral arms or stellar drift",
    "Planetary System":  "orbital paths, multiple light sources, sweeping scale",
    "Planet":            "full-disc atmospheric, terrestrial, low-orbit perspective",
    "Region":            "painterly, atmospheric, grounded landscape",
    "Room":              "interior, bounded space, mood-lit",
    "Object":            "hyper-detailed, intimate, close-up, material-honest",
    "Molecule":          "structural diagram, geometric bonds, scientific illustration",
    "Atom":              "electron clouds, schematic, glowing nucleus",
    "SubatomicParticle": "particle traces, abstract energy, faint geometry",
}

_DEFAULT_STYLE = "in-world cinematic, atmospheric"


def _count_kinds(history: Iterable[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for h in history:
        kind = h.get("type") or ""
        counts[kind] = counts.get(kind, 0) + 1
    return counts


# ripple_score sits on [0, 1] (clamped in CausalityBus._fire). 0.5 is reached
# after roughly five full-strength events on the node; that's our threshold for
# the "high ripple weight" register the design doc calls out.
RIPPLE_UNSTABLE_THRESHOLD: float = 0.5


def derive_modifiers(properties: dict, history: list[dict],
                     ripple_score: float = 0.0) -> list[str]:
    """Return style modifier tags from the node's properties + mutation history.

    Mirrors the property→signal matrix in `docs/design/game-design.md`.
    Order is stable so callers can hash the result for cache keying.

    `ripple_score` is the persisted cumulative causal pressure for this node
    (loaded from `node_runtime_state`); when it crosses the unstable threshold
    the visual register tips into psychedelic territory. This replaces the
    earlier total-mutation-count proxy now that the real signal survives the
    per-request world rebuild.
    """
    counts = _count_kinds(history)

    # Pristine: no recorded interactions and no accumulated ripple yet →
    # ethereal, nothing else applies.
    if not counts and ripple_score <= 0.0:
        return ["ethereal, minimal, untouched"]

    mods: list[str] = []

    # Heavy AI agent activity (≥5 visits) → surreal.
    if counts.get("AGENT_VISIT", 0) >= 5:
        mods.append("surreal, geometry-distorted")

    # Conflict / danger history.
    if counts.get("DANGER_ALERT", 0) >= 1:
        mods.append("noir, chiaroscuro, shadow-heavy")

    # Player cooperation: ≥2 distinct human speakers.
    speakers = {
        h.get("player") for h in history
        if h.get("type") in ("PLAYER_SPEAK", "PLAYER_CHAT") and h.get("player")
    }
    if len(speakers) >= 2:
        mods.append("warm, impressionist, layered")

    # Puzzle node — either marked-as-puzzle or solved-here.
    if properties.get("has_puzzle") or counts.get("PUZZLE_SOLVED", 0):
        mods.append("Escher-like, geometric, op art")

    # Repeated puzzle failure → tension.
    if counts.get("PUZZLE_FAILED", 0) >= 2:
        mods.append("oppressive, claustrophobic")

    # Corrupted node (object property).
    if properties.get("condition") == "corrupted":
        mods.append("glitch art, dark expressionist")

    # High accumulated ripple — the design doc's "high ripple weight."
    if ripple_score >= RIPPLE_UNSTABLE_THRESHOLD:
        mods.append("psychedelic, saturated, unstable")

    return mods


def _prop_pairs(properties: dict, limit: int = 6) -> list[tuple[str, object]]:
    """Stable, capped property listing for prompt + signature."""
    return sorted(properties.items())[:limit]


def assemble_prompt(level: str, name: str, properties: dict,
                    history: list[dict], ripple_score: float = 0.0) -> str:
    """Build the full text prompt sent to fal.ai for one scene image."""
    baseline  = HIERARCHY_STYLES.get(level, _DEFAULT_STYLE)
    modifiers = derive_modifiers(properties, history, ripple_score)
    pairs     = _prop_pairs(properties)
    prop_summary = ", ".join(f"{k}: {v}" for k, v in pairs) if pairs else ""

    parts = [
        f"A {level.lower()} called {name} in a nested multiverse.",
        f"Style: {baseline}.",
    ]
    if modifiers:
        parts.append(f"Mood: {'; '.join(modifiers)}.")
    if prop_summary:
        parts.append(f"Properties: {prop_summary}.")
    parts.append("In-world, atmospheric, no text, no UI elements.")

    return " ".join(parts)


def style_signature(level: str, properties: dict,
                    history: list[dict], ripple_score: float = 0.0) -> str:
    """8-char hash of the style-determining inputs.

    Two inputs that produce the same prompt produce the same signature; two
    that produce visibly different prompts produce different signatures. The
    server folds this into the image cache key so visuals refresh whenever
    the style would actually change, not only when history count crosses a
    fixed bucket boundary.
    """
    baseline  = HIERARCHY_STYLES.get(level, _DEFAULT_STYLE)
    modifiers = derive_modifiers(properties, history, ripple_score)
    pairs     = _prop_pairs(properties)
    seed_str  = f"{baseline}|{'|'.join(modifiers)}|{pairs}"
    return hashlib.sha1(seed_str.encode("utf-8")).hexdigest()[:8]
