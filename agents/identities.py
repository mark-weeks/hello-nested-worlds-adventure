"""Server-owned agent identities: the only names an agent acts or speaks under.

An agent's name is durable. ``AGENT_VISIT`` and ``AGENT_VOICE`` rows carry it
as ``data.agent``, ``agent_memory`` and ``agent_runs`` are keyed by it, and
both clients turn ``data.agent`` in node history into a Speak target.
``data.agent`` is not a redactable field (``persistence._REDACTABLE_FIELDS``)
and moderation never screens it, so a name a client chose there could only be
removed by a whole-DB restore — outside the chronicle's three sanctioned
mechanisms. No HTTP or socket path lets a client choose a name outside this
set, defined once here: ``POST /agent/voice`` accepts a requested name only
through ``canonical``, and every other path names its agent itself.

- The wandering cast (``consciousness.WANDERER_CAST``), walked by the
  heartbeat.
- The authored situation's keeper (``multiverse.situation.KEEPER``, ADR-025).
  Today that is a cast member; it is listed so a future keeper cannot fall
  outside the set.
- Two fixed utility walkers: ``SCOUT`` (``GET /agent``) and ``OBSERVER``
  (``GET /observe`` and the CLI play session's ambient observer).
"""
from __future__ import annotations

import sqlite3

from typing import Any

from consciousness import WANDERER_CAST
from multiverse.situation import KEEPER
from persistence import name_key

SCOUT = "Scout"
OBSERVER = "Observer"
UTILITY_IDENTITIES: tuple[str, ...] = (SCOUT, OBSERVER)

# Ordered and de-duplicated: the cast, then the keeper if it is not already
# a cast member, then the utility walkers.
SERVER_IDENTITIES: tuple[str, ...] = tuple(
    dict.fromkeys([*WANDERER_CAST, KEEPER, *UTILITY_IDENTITIES]))

# Names a server identity was once stored under: retired spelling -> the
# identity's current name. A rename moves no stored row, so what was saved
# under the old spelling is read through this map: a personal block
# (``persistence.blocks``) keeps following the member, and the beta metrics
# keep counting the old rows as the cast's. A retired spelling is not a
# server identity: nothing acts, speaks or is reserved under it.
RETIRED_IDENTITIES: dict[str, str] = {"Cartographer-9": "Cartographer"}

# Keyed by ``persistence.name_key``, the comparison every name check uses.
_CANONICAL: dict[str, str] = {name_key(name): name for name in SERVER_IDENTITIES}


def canonical(raw: Any) -> str | None:
    """The canonical spelling of a server-owned identity, or None.

    Compared by ``persistence.name_key``: trimmed, case-folded and
    NFKC-normalized, with invisible default-ignorable characters removed,
    so ``" tessera "``, a fullwidth ``"Ｔｅｓｓｅｒａ"`` and ``"Tessera"``
    followed by a zero-width space are ``"Tessera"``. Anything else,
    including a non-string, is not an agent
    this world knows. The reserved-name checks call this, or compare the
    same key, so no spelling of a server identity is left for a player.
    """
    if not isinstance(raw, str):
        return None
    return _CANONICAL.get(name_key(raw))


def cast_held_by_players() -> dict[str, tuple[str, ...]]:
    """Cast names a registered player already holds: name -> registered spellings.

    Registration refuses a reserved name, so a row like this was written
    before the name was reserved: "Cartographer" was free to register until
    the cast member "Cartographer-9" took it (ADR-041 D5). The player keeps
    the name, the credential and the history. The cast member stays out of
    the world instead (`walking_cast`, `voiced`), so no agent acts or speaks
    under a name a player holds. Revoked names count: they stay taken, and
    their rows stay in the chronicle. One read of `invite_keys`, a row per
    invited player. `python main.py invite duplicates` lists the same rows
    for the operator.
    """
    import persistence
    cast = set(WANDERER_CAST)
    held: dict[str, list[str]] = {}
    for row in persistence.list_invite_keys(include_revoked=True):
        name = canonical(row["name"])
        if name in cast:
            held.setdefault(name, []).append(row["name"])
    return {name: tuple(spellings) for name, spellings in held.items()}


def walking_cast(roster=WANDERER_CAST) -> list[str]:
    """The cast members free to walk: the roster, in order, less every
    member whose name a registered player holds."""
    held = cast_held_by_players()
    return [name for name in roster if name not in held]


def voiced(raw: Any) -> str | None:
    """`canonical`, except that a cast member whose name a registered
    player holds is not an agent this world can voice."""
    name = canonical(raw)
    if name is None:
        return None
    try:
        held = cast_held_by_players()
    except sqlite3.Error:
        # A failed collision read must not turn a quiet-line path into a
        # 5xx (failure stays in fiction): answer as the roster alone says.
        return name
    return None if name in held else name
