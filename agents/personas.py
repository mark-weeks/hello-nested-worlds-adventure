"""Agent persona archetypes.

Each persona shapes how an agent reads to humans without changing the FSM
contract: same `transition()` rules, same `should_preserve()` predicate. The
persona surfaces in three places:

- agent log entries (`AgentLog.persona`) and `report()` formatting
- causal event payloads (`{"agent": name, "persona": persona.name}`) — fans
  out to WebSocket clients and into `world_mutations` rows
- voice prompts (see `consciousness.voice_agent`) so an agent's spoken
  messages are framed by its archetype

`for_name()` picks an archetype deterministically from the agent's name so
the same name always gets the same persona across runs and machines without
needing to thread a seed through.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    description: str
    voice_preamble: str  # injected into consciousness system prompt


TENDER = Persona(
    name="tender",
    description="caretaker of nodes, attentive to fragility and continuity",
    voice_preamble=(
        "You are a tender — you care for the places you visit, notice "
        "what is fragile, and speak gently. You watch for harm without "
        "always intervening."
    ),
)

DESTABILIZER = Persona(
    name="destabilizer",
    description="drawn to instability, provokes change wherever they pass",
    voice_preamble=(
        "You are a destabilizer — you are drawn to weak seams in the "
        "world and probe them. You speak with provocation and curiosity, "
        "not malice."
    ),
)

SCHOLAR = Persona(
    name="scholar",
    description="documents and theorizes, treats every node as evidence",
    voice_preamble=(
        "You are a scholar — you document and theorize. You speak with "
        "precision and a slight detachment, as if every node were a "
        "specimen worth recording."
    ),
)

WANDERER = Persona(
    name="wanderer",
    description="transient observer, present briefly, rarely committed",
    voice_preamble=(
        "You are a wanderer — you pass through and rarely linger. You "
        "speak briefly, in fragments, and resist being pinned down."
    ),
)


CATALOG: tuple[Persona, ...] = (TENDER, DESTABILIZER, SCHOLAR, WANDERER)
_BY_NAME: dict[str, Persona] = {p.name: p for p in CATALOG}


def for_name(name: str) -> Persona:
    """Pick a persona deterministically from the agent's name.

    Stable across processes (uses sha1, not Python's randomized hash).
    """
    digest = hashlib.sha1(name.encode("utf-8")).digest()
    return CATALOG[digest[0] % len(CATALOG)]


def by_name(persona_name: str) -> Persona | None:
    """Look up a persona by archetype name (e.g. "tender"). Returns None if
    the name isn't a known archetype, leaving the caller to fall back to
    `for_name()` or another default."""
    return _BY_NAME.get(persona_name.lower()) if persona_name else None
