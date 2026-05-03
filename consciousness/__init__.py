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

    The shared behavioural preamble is marked for prompt caching so repeated
    calls across different nodes reuse the cached prefix and avoid redundant
    token processing.

    Pass `history` (from persistence.get_node_history) to give the node
    memory of past visitors and events.
    """
    props = "; ".join(f"{k}={v}" for k, v in node.properties.items())
    node_context = (
        f"You are {node.name}, a {node.level}. Your nature: {props}."
        + _history_block(history or [])
    )

    response = _get_client().messages.create(
        model=_MODEL,
        max_tokens=256,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PREAMBLE,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": node_context,
            },
        ],
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
