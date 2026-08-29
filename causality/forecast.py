"""Pure upward-arm cascade forecast — the engine's physics, side-effect-free.

The causal-prediction puzzle family (ADR-010) asks a player to predict how
a disturbance rising from a node carries through its enclosing scales:
where it last sounds, how many scales it rings, which scale it tunnels
through in silence. For those answers to be HONEST, they must be exactly
what the engine would do — so this module re-states the up-arm walk of
`CausalityBus._walk` and `causality.staging.drain_due_hops` as a pure
function over the node's ancestor chain, and
tests/test_causal_prediction.py pins the equivalence against the live bus
(the forecast IS the physics, or the batch does not ship).

Contract mirrored hop for hop:

- Hop 1 lands on the parent carrying full origin strength; each hop
  dampens ITSELF on arrival under the law of the universe it lands in
  (`causality.laws.law_for` of the landing node), with the standard 0.5
  fallback above universes — the same constant the staged path uses.
- Threadbare drops end the arm silently; Quantum tunnels pass through a
  scale undampened and unheard; arrival below MIN_STRENGTH ends the arm.
- Deterministic weather: tunnel/drop/draw rolls hash
  (law, origin, landing, hop) via `hop_token` — same world, same act,
  same forecast, forever.

The forecast needs ONLY the ancestor chain, never children — the same
purity contract every puzzle family honors, because the seal gate builds
puzzles from resolver nodes that carry parents alone. (This is also why
the family declines under Inverted law: flip sends the live one-armed act
into children the chain cannot see, and on the staged both-arm path flip
is a no-op — the Inverted up-arm behaves like plain default physics and
teaches nothing Inverted.)
"""
from __future__ import annotations

from dataclasses import dataclass

from causality import MIN_STRENGTH
from causality.laws import hop_token, law_for
from multiverse.node import SpatialNode

# Matches causality.propagate()'s default and staging.STAGED_DAMPENING —
# the physics above universes, where no law holds.
FALLBACK_DAMPENING = 0.5


@dataclass(frozen=True)
class ForecastHop:
    node: SpatialNode      # the ancestor this hop lands on
    hop: int               # 1 = parent, 2 = grandparent, …
    strength: float        # strength on arrival (after dampening)
    tunneled: bool         # passed through silently, undampened


@dataclass(frozen=True)
class UpArmForecast:
    hops: tuple[ForecastHop, ...]   # every hop until the arm ends
    dropped_at: SpatialNode | None  # a Threadbare fray ended the arm here

    @property
    def rung(self) -> tuple[ForecastHop, ...]:
        """The hops that actually SOUND — arrived and not tunneled."""
        return tuple(h for h in self.hops if not h.tunneled)

    @property
    def tunneled_through(self) -> tuple[ForecastHop, ...]:
        return tuple(h for h in self.hops if h.tunneled)

    @property
    def terminus(self) -> ForecastHop | None:
        """The last scale the cry sounds in, if it sounds anywhere."""
        rung = self.rung
        return rung[-1] if rung else None


def up_arm_forecast(origin: SpatialNode) -> UpArmForecast:
    """Forecast the upward arm of a full-strength cascade from `origin`.

    Pure in (origin identity, ancestor chain as born): no clock, no
    global RNG, no world state beyond the nodes themselves.
    """
    hops: list[ForecastHop] = []
    strength = 1.0
    hop = 0
    node = origin.parent
    while node is not None:
        hop += 1
        law = law_for(node)
        if law is None:
            factor, tunneled = FALLBACK_DAMPENING, False
        else:
            token = hop_token(law, origin.name, node.name, hop)
            if law.drops(token):
                return UpArmForecast(hops=tuple(hops), dropped_at=node)
            tunneled = law.tunnels(token)
            factor = 1.0 if tunneled else law.dampening(hop, "up", token)
        strength *= factor
        if strength < MIN_STRENGTH:
            break
        hops.append(ForecastHop(node=node, hop=hop,
                                strength=strength, tunneled=tunneled))
        node = node.parent
    return UpArmForecast(hops=tuple(hops), dropped_at=None)
