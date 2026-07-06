"""The named cast — twelve individuals with trait sheets.

The hash fallback in `agents.personas.for_name` gave the original eight cast
members whatever archetype sha1 happened to land on: four tenders, two
scholars, one wanderer, and a single destabilizer — the world's entire
entropy engine hanging off one name, with "Aunt Entropy" miscast as a
scholar and "Cartographer-9" as the destabilizer. This module assigns
personas deliberately, balanced 3/3/3/3, and gives each regular a small
trait sheet the heartbeat reads:

- ``home_levels``: the scales this agent gravitates toward. Drop-ins re-aim
  at home ground most of the time, so The Locksmith haunts Rooms and Aunt
  Entropy the cosmic shells instead of everyone rambling uniformly.
- ``danger_threshold``: personal courage — the agent withdraws when a
  node's danger_level exceeds it. Destabilizers walk into danger that turns
  a tender back; caution is character, not a shared constant.
- ``favored_verb``: the scale-act this agent reaches for first when tending
  (a name from ``multiverse.verbs.VERBS``). None for personas that don't
  perform verbs (destabilizers corrode, wanderers only pass through).
- ``tic``: a signature phrase that occasionally rides the agent's banter
  lines, so a transcript reads as THIS speaker, not just any member of the
  archetype.

Names must stay in sync with ``consciousness.WANDERER_CAST`` — the leaf
copy the cached voice bibles are built from (consciousness deliberately
imports nothing from the agents package). ``tests/test_roster.py`` pins the
two lists together so they cannot drift.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    name: str
    persona: str                   # archetype name (agents.personas.CATALOG)
    home_levels: tuple[str, ...]   # entries from multiverse.generator.LEVELS
    danger_threshold: int          # withdraw when danger_level exceeds this
    favored_verb: str | None       # multiverse.verbs name, or None
    tic: str                       # signature phrase, surfaces in banter


PROFILES: tuple[AgentProfile, ...] = (
    # ── tenders: the keepers ────────────────────────────────────────────
    AgentProfile("Tessera", "tender", ("Room", "Object"), 6,
                 "mend", "Piece by piece."),
    AgentProfile("The Locksmith", "tender", ("Room",), 5,
                 "inscribe", "Every seal remembers its key."),
    AgentProfile("Bellhollow", "tender", ("Region", "Planet"), 6,
                 "ward", "Softly, now."),
    # ── destabilizers: the entropy engine ───────────────────────────────
    AgentProfile("Aunt Entropy", "destabilizer", ("Universe", "Galaxy"), 10,
                 None, "Everything falls; I only keep the schedule."),
    AgentProfile("Vex", "destabilizer", ("Room", "Object"), 9,
                 None, "Ask me how it breaks."),
    AgentProfile("Karst", "destabilizer", ("Region", "Planet"), 9,
                 None, "Given time, water wins."),
    # ── scholars: the record ────────────────────────────────────────────
    AgentProfile("Halden", "scholar", ("Planetary System", "Planet"), 7,
                 "inscribe", "Noted, dated, filed."),
    AgentProfile("Cartographer-9", "scholar", ("Galaxy", "Planetary System"), 7,
                 "calibrate", "The map has been amended."),
    AgentProfile("Marginalia", "scholar", ("Molecule", "Atom"), 6,
                 "observe", "See footnote."),
    # ── wanderers: the roads ────────────────────────────────────────────
    AgentProfile("Sela", "wanderer", ("Region", "Room"), 8,
                 None, "The road was patient today."),
    AgentProfile("Mirrorbird", "wanderer", ("Atom", "SubatomicParticle"), 8,
                 None, "So the mirror said."),
    AgentProfile("Petrichor", "wanderer", ("Planet", "Region"), 7,
                 None, "Rain was here first."),
)

ROSTER: dict[str, AgentProfile] = {p.name: p for p in PROFILES}
CAST_NAMES: tuple[str, ...] = tuple(p.name for p in PROFILES)


def profile_for(name: str) -> AgentProfile | None:
    """Trait sheet for a cast regular; None for anyone off the roster."""
    return ROSTER.get(name)
