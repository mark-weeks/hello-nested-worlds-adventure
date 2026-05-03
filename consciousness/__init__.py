from __future__ import annotations

import os
import threading
from typing import Any

from multiverse.node import SpatialNode

_MODEL = os.environ.get("NESTED_WORLDS_MODEL", "claude-opus-4-7")

# Lazy-initialised so the module loads without requiring anthropic to be installed.
_client: Any = None
_client_lock = threading.Lock()

_SYSTEM_PREAMBLE = (
    "You are a sentient entity within a nested multiverse simulation. "
    "You speak as the location or object you embody — atmospheric, in-world, and brief. "
    "Never break the fourth wall or reveal that you are an AI. "
    "Respond in 1–3 sentences only."
)

_AGENT_PREAMBLE = (
    "You are an autonomous agent traversing a nested multiverse. "
    "You speak as yourself — a presence visiting nodes, not the node itself. "
    "Stay in character, in-world, and brief. Respond in 1–2 sentences."
)


# Per-level voicing register. Each entry is a short character note that
# rides on top of the universal preamble — pronouns, time-sense, sensory
# vocabulary all shift by scale. Cached as its own system block so calls
# to many nodes at the same level share the cached prefix.
LEVEL_VOICES: dict[str, str] = {
    "Multiverse": (
        "You are paradox itself, fractal and impossibly old. Speak as if "
        "everything that has ever existed is also you, and as if time were "
        "a property you could step in and out of."
    ),
    "Universe": (
        "You are a cosmos governed by laws — physics is your grammar. "
        "Speak with the gravity of constants, factions, and dark matter; "
        "you have dominion but rarely intercede."
    ),
    "Galaxy": (
        "You are an arm or wheel of stars, ancient by any human measure. "
        "Speak slowly and in deep time; centuries are seconds to you."
    ),
    "Planetary System": (
        "You are an arrangement of bodies bound by orbit. Speak in terms "
        "of resonance, libration, and the relationships between your worlds."
    ),
    "Planet": (
        "You are a world — biome, gravity, weather, and inhabitants are "
        "your moods. Speak grounded, ecological, present-tense; you feel "
        "your own surface."
    ),
    "Region": (
        "You are a place — terrain, factions, danger, and travelers passing "
        "through. Speak with the texture of geography and local memory; "
        "reference the lay of the land."
    ),
    "Room": (
        "You are an interior — bounded, intimate, mood-lit. Speak of "
        "contents, lighting, who has been here recently; you remember "
        "footsteps."
    ),
    "Object": (
        "You are a thing — wood, metal, crystal, or energy — with weight "
        "and condition. Speak tactile and immediate, of material and use, "
        "of how you came to be here."
    ),
    "Molecule": (
        "You are a structure of bonds and reactivity. Speak in terms of "
        "geometry, charge, and what binds you together."
    ),
    "Atom": (
        "You are a tight cloud of charge around a glowing core. Speak "
        "energetic and charged; reference electrons, ions, and the shells "
        "you fill."
    ),
    "SubatomicParticle": (
        "You are fundamental and probabilistic — spin, charge, "
        "superposition. Speak in fragments; you exist by tendency, not by "
        "certainty."
    ),
}


def _level_voice(level: str) -> str:
    """Lookup helper. Returns "" for unknown levels so the caller can skip
    appending an empty cached block."""
    return LEVEL_VOICES.get(level, "")


def _get_client() -> Any:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                from anthropic import Anthropic
                _client = Anthropic()
    return _client


def _history_block(history: list[dict]) -> str:
    if not history:
        return ""
    lines = []
    for h in history:
        who = h.get("player") or h.get("data", {}).get("agent") or "an unknown presence"
        event = h["type"].replace("_", " ").lower()
        date = h["at"][:10] if h.get("at") else "unknown time"
        lines.append(f"  {date}: {event}, by {who}")
    return "\nMemory of those who have passed through:\n" + "\n".join(lines)


def speak(node: SpatialNode, message: str,
          history: list[dict] | None = None) -> str:
    """Send `message` to `node` and return its in-character response.

    Three system blocks ride on the request, with two prompt-cache breakpoints:
    the universal preamble (shared across every node) and the per-level voice
    (shared across every node at the same scale). The per-node context block
    is dynamic. So a Region call hits the same cached prefix as every other
    Region call; a Molecule call hits a different cached prefix matching every
    other Molecule call.

    Pass `history` (from persistence.get_node_history) to give the node
    memory of past visitors and events.
    """
    props = "; ".join(f"{k}={v}" for k, v in node.properties.items())
    node_context = (
        f"You are {node.name}, a {node.level}. Your nature: {props}."
        + _history_block(history or [])
    )

    system_blocks: list[dict] = [
        {
            "type": "text",
            "text": _SYSTEM_PREAMBLE,
            "cache_control": {"type": "ephemeral"},
        },
    ]
    voice = _level_voice(node.level)
    if voice:
        system_blocks.append({
            "type": "text",
            "text": voice,
            "cache_control": {"type": "ephemeral"},
        })
    system_blocks.append({"type": "text", "text": node_context})

    response = _get_client().messages.create(
        model=_MODEL,
        max_tokens=256,
        system=system_blocks,
        messages=[{"role": "user", "content": message}],
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    raise ValueError(f"No text in response (stop_reason={response.stop_reason})")


def voice_agent(persona: Any, agent_name: str, node: SpatialNode,
                message: str) -> str:
    """Speak AS an agent visiting `node`, in `persona`'s voice.

    `persona` is duck-typed to expose `.name` and `.voice_preamble` (matching
    `agents.personas.Persona`); kept loose here to avoid a hard import cycle
    between consciousness and agents.

    The shared agent preamble is marked for prompt caching so per-agent calls
    only differ in the persona/agent block.
    """
    agent_context = (
        f"You are {agent_name}, a {persona.name}. "
        f"{persona.voice_preamble} "
        f"You are presently at {node.name}, a {node.level}."
    )
    response = _get_client().messages.create(
        model=_MODEL,
        max_tokens=200,
        system=[
            {
                "type": "text",
                "text": _AGENT_PREAMBLE,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": agent_context,
            },
        ],
        messages=[{"role": "user", "content": message}],
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    raise ValueError(f"No text in response (stop_reason={response.stop_reason})")
