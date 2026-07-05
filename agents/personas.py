"""Agent persona archetypes.

Each persona shapes how an agent reads to humans without changing the FSM
contract: same `transition()` rules, same `should_preserve()` predicate. The
persona surfaces in three places:

- agent log entries (`AgentLog.persona`) and `report()` formatting
- causal event payloads (`{"agent": name, "persona": persona.name}`) — fans
  out to WebSocket clients and into `world_mutations` rows
- voice prompts: `consciousness.voice_agent` frames an agent's spoken
  messages by `persona.name` against the archetype texts embedded in the
  consciousness agent bible (`_AGENT_ARCHETYPES`) — the single source of
  archetype voice text, so there is no duplicate copy here to drift

`for_name()` resolves cast regulars through their deliberate roster
assignment (agents/roster.py) and everyone else through a deterministic
hash of the name, so the same name always gets the same persona across
runs and machines without needing to thread a seed through.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    description: str


TENDER = Persona(
    name="tender",
    description="caretaker of nodes, attentive to fragility and continuity",
)

DESTABILIZER = Persona(
    name="destabilizer",
    description="drawn to instability, provokes change wherever they pass",
)

SCHOLAR = Persona(
    name="scholar",
    description="documents and theorizes, treats every node as evidence",
)

WANDERER = Persona(
    name="wanderer",
    description="transient observer, present briefly, rarely committed",
)


CATALOG: tuple[Persona, ...] = (TENDER, DESTABILIZER, SCHOLAR, WANDERER)
_BY_NAME: dict[str, Persona] = {p.name: p for p in CATALOG}


def for_name(name: str) -> Persona:
    """Resolve an agent's persona: deliberate for the cast, hashed otherwise.

    Cast regulars carry an explicit assignment on their roster trait sheet
    (agents/roster.py), keeping the archetype balance a design decision —
    the pure hash dealt the original cast four tenders and one destabilizer,
    with Aunt Entropy landing "scholar". Names off the roster still hash
    deterministically (sha1, not Python's randomized hash), so ad-hoc agents
    keep a stable persona across runs and machines.
    """
    from agents.roster import profile_for  # deferred: keeps roster import-free
    profile = profile_for(name)
    if profile is not None and profile.persona in _BY_NAME:
        return _BY_NAME[profile.persona]
    digest = hashlib.sha1(name.encode("utf-8")).digest()
    return CATALOG[digest[0] % len(CATALOG)]


def by_name(persona_name: str) -> Persona | None:
    """Look up a persona by archetype name (e.g. "tender"). Returns None if
    the name isn't a known archetype, leaving the caller to fall back to
    `for_name()` or another default."""
    return _BY_NAME.get(persona_name.lower()) if persona_name else None
