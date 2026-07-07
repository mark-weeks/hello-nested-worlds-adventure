"""Per-universe physics — laws_of_physics made mechanically real.

Every Universe declares a law ("Newtonian", "Inverted", "Fractal", …).
Until now that was flavor: five different physics that all behaved
identically. This module makes the law the ROUTING RULE of the causal
rails inside that universe's subtree, so a player discovers a universe's
temperament by acting and being surprised — the same act carries
differently under different skies:

  Newtonian     — strict locality: heavy dampening, cascades die young
  Quantum       — hops may tunnel: pass silently THROUGH a scale,
                  undampened, and land beyond it
  Fractal       — self-similar: every second hop keeps full strength,
                  so consequences travel roughly twice as far
  Inverted      — direction flips: acting on a particle shakes the
                  galaxy; acting on a galaxy stirs the particles
  Probabilistic — per-hop dampening is drawn, not fixed (seeded — the
                  same cascade always rolls the same)
  Recursive     — every third hop echoes at full strength
  Viscous       — far-travelling but slow: staged hops take twice as long
  Crystalline   — anisotropic lattice: transmits upward well, downward
                  poorly
  Tidal         — surge and ebb: dampening alternates strong/weak
  Threadbare    — lossy: a hop may simply drop, and the cascade dies there
  Palindromic   — mirrored rhythm: dampening reads the same forwards
                  and back
  Slow light    — the news travels at a crawl: triple staged delay

The law that governs a hop is the law of the universe the hop lands IN —
a cascade that climbs out of one universe and descends into another
changes physics at the boundary, which is exactly how a multiverse
should feel.

Determinism: stochastic-flavored laws (tunneling, drops, drawn
dampening) hash (law, origin, node, hop) — same world, same act, same
weather. No wall clock, no global RNG. Nodes with no Universe ancestor
(the Multiverse root, synthetic test trees) have no law and keep the
default physics, so every existing cascade contract holds outside real
universes.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multiverse.node import SpatialNode


@dataclass(frozen=True)
class LawProfile:
    name: str
    damp_up: tuple[float, ...] = (0.5,)    # cycled by hop index, upward arm
    damp_down: tuple[float, ...] = (0.5,)  # cycled by hop index, downward arm
    flip: bool = False           # up-cascades travel down and vice versa
    tunnel_chance: float = 0.0   # hop passes through silently, undampened
    drop_chance: float = 0.0     # hop dies silently, cascade ends there
    drawn: bool = False          # dampening drawn per hop from the pattern
    delay_scale: float = 1.0     # staged hop delay multiplier

    def _roll(self, token: str) -> float:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF

    def dampening(self, hop: int, direction: str, token: str) -> float:
        pattern = self.damp_up if direction == "up" else self.damp_down
        if self.drawn:
            idx = int(self._roll(f"draw:{token}") * len(pattern)) % len(pattern)
            return pattern[idx]
        return pattern[(hop - 1) % len(pattern)]

    def tunnels(self, token: str) -> bool:
        return self.tunnel_chance > 0 and \
            self._roll(f"tunnel:{token}") < self.tunnel_chance

    def drops(self, token: str) -> bool:
        return self.drop_chance > 0 and \
            self._roll(f"drop:{token}") < self.drop_chance


PROFILES: dict[str, LawProfile] = {p.name: p for p in (
    LawProfile("Newtonian",     damp_up=(0.35,), damp_down=(0.35,)),
    LawProfile("Quantum",       tunnel_chance=0.25),
    LawProfile("Fractal",       damp_up=(0.5, 1.0), damp_down=(0.5, 1.0)),
    LawProfile("Inverted",      flip=True),
    LawProfile("Probabilistic", damp_up=(0.3, 0.5, 0.7),
                                damp_down=(0.3, 0.5, 0.7), drawn=True),
    LawProfile("Recursive",     damp_up=(0.5, 0.5, 1.0),
                                damp_down=(0.5, 0.5, 1.0)),
    LawProfile("Viscous",       damp_up=(0.6,), damp_down=(0.6,),
                                delay_scale=2.0),
    LawProfile("Crystalline",   damp_up=(0.8,), damp_down=(0.3,)),
    LawProfile("Tidal",         damp_up=(0.7, 0.3), damp_down=(0.7, 0.3)),
    LawProfile("Threadbare",    drop_chance=0.15),
    LawProfile("Palindromic",   damp_up=(0.4, 0.6), damp_down=(0.4, 0.6)),
    LawProfile("Slow light",    damp_up=(0.45,), damp_down=(0.45,),
                                delay_scale=3.0),
)}


def law_for(node: "SpatialNode") -> LawProfile | None:
    """The law of the universe that holds `node` — None above Universe
    scale (the multiverse keeps no single physics) and for trees that
    carry no Universe (synthetic tests), where default physics apply."""
    n = node
    while n is not None:
        if n.level == "Universe":
            return PROFILES.get(str(n.properties.get("laws_of_physics", "")))
        n = n.parent
    return None


def hop_token(law: LawProfile, origin_name: str, node_name: str,
              hop: int) -> str:
    """The deterministic identity of one hop, for tunnel/drop/draw rolls."""
    return f"{law.name}:{origin_name}:{node_name}:{hop}"
