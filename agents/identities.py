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

# Keyed by ``persistence.name_key``, the comparison every name check uses.
_CANONICAL: dict[str, str] = {name_key(name): name for name in SERVER_IDENTITIES}


def canonical(raw: Any) -> str | None:
    """The canonical spelling of a server-owned identity, or None.

    Compared by ``persistence.name_key``: trimmed, case-folded and
    NFKC-normalized, so ``" tessera "`` and a fullwidth ``"Ｔｅｓｓｅｒａ"`` are
    ``"Tessera"``. Anything else, including a non-string, is not an agent
    this world knows. The reserved-name checks call this, or compare the
    same key, so no spelling of a server identity is left for a player.
    """
    if not isinstance(raw, str):
        return None
    return _CANONICAL.get(name_key(raw))
