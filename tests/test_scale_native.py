"""Scale-native mechanics: physics that differ per universe, time that
differs per scale, locality that fails at the smallest one, and the
nesting itself as puzzle content — the layer that makes the scales PLAY
differently, not just look and sound different.
"""
from __future__ import annotations

import json
import threading
import urllib.request

import pytest

import persistence
from causality import CausalityBus, EventKind
from causality.laws import PROFILES, law_for
from multiverse.generator import LEVELS, generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.verbs import (
    MATURATION_SECONDS, VERBS, apply_verb, maturation_seconds,
)
from puzzles.engine import build_puzzle
from puzzles.types import PuzzleKind
from server import heartbeat


@pytest.fixture(autouse=True)
def _zero_hop_delay(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    yield


def _walk(n, out):
    out.append(n)
    for c in n.children:
        _walk(c, out)
    return out


def _universe_tree(law: str, depth: int = 5, breadth: int = 2):
    """A synthetic universe with a chosen law, deep enough to measure reach."""
    levels = LEVELS[1:]  # Universe downward
    uni = SpatialNode("U-1", "Universe", properties={"laws_of_physics": law})

    def grow(parent, level_index, path):
        if level_index >= depth:
            return
        for i in range(1, breadth + 1):
            child = SpatialNode(f"N-{path}{i}", levels[level_index],
                                properties={})
            parent.add_child(child)
            grow(child, level_index + 1, f"{path}{i}")

    grow(uni, 1, "1")
    return uni


class TestLawsOfPhysics:
    def test_every_bank_law_has_a_profile(self):
        from multiverse.generator import _LEVEL_GENERATORS
        import random
        laws = {_LEVEL_GENERATORS["Universe"](random.Random(i))
                ["laws_of_physics"] for i in range(500)}
        assert laws <= set(PROFILES), (
            f"unprofiled laws: {laws - set(PROFILES)} — a universe with no "
            "physics profile silently falls back to default")

    def test_law_is_the_containing_universes(self):
        uni = _universe_tree("Newtonian")
        deep = _walk(uni, [])[-1]
        assert law_for(deep).name == "Newtonian"
        assert law_for(SpatialNode("X", "Room", properties={})) is None

    def test_newtonian_locality_vs_fractal_reach(self):
        # Same tree shape, same act — the law decides how far it carries.
        reach = {}
        for law in ("Newtonian", "Fractal"):
            uni = _universe_tree(law)
            origin = uni.children[0]
            bus = CausalityBus()
            bus.propagate(origin, EventKind.PUZZLE_SOLVED, {})
            reach[law] = len(bus.get_log())
        assert reach["Fractal"] > reach["Newtonian"], reach

    def test_inverted_universe_flips_direction(self):
        # An upward alert in an Inverted universe sinks instead of rising.
        uni = _universe_tree("Inverted")
        mid = uni.children[0].children[0]
        bus = CausalityBus()
        bus.propagate(mid, EventKind.DANGER_ALERT, {}, direction="up")
        fired = {name for name, _ in bus.get_log()}
        descendants = {n.name for n in _walk(mid, [])}
        assert fired <= descendants, "inverted 'up' must travel down"
        assert len(fired) > 1, "…and it must actually travel"

    def test_threadbare_drops_and_quantum_tunnels_deterministically(self):
        for law in ("Threadbare", "Quantum"):
            uni = _universe_tree(law, depth=5, breadth=2)
            origin = uni.children[0]
            runs = []
            for _ in range(2):
                bus = CausalityBus()
                bus.propagate(origin, EventKind.PUZZLE_SOLVED, {})
                runs.append([(n, round(e.strength, 4))
                             for n, e in bus.get_log()])
            assert runs[0] == runs[1], f"{law} physics must be deterministic"

    def test_quantum_tunneling_skips_but_carries(self):
        # Somewhere in a quantum universe, a node is skipped while its
        # descendants still fire — the event passed THROUGH it.
        uni = _universe_tree("Quantum", depth=5, breadth=3)
        origin = uni.children[0]
        bus = CausalityBus()
        bus.propagate(origin, EventKind.PUZZLE_SOLVED, {})
        fired = {name for name, _ in bus.get_log()}
        skipped_with_fired_child = [
            n for n in _walk(origin, [])
            if n.name not in fired
            and any(c.name in fired for c in n.children)
        ]
        assert skipped_with_fired_child, "no tunneling observed"

    def test_lawless_trees_keep_the_legacy_contract(self):
        # Synthetic trees with no Universe ancestor: caller dampening,
        # exact legacy strengths.
        region = SpatialNode("R-1", "Region", properties={})
        room = SpatialNode("Rm-11", "Room", properties={})
        obj = SpatialNode("O-111", "Object", properties={})
        region.add_child(room)
        room.add_child(obj)
        bus = CausalityBus()
        bus.propagate(room, EventKind.PUZZLE_SOLVED, {}, dampening=0.5)
        strengths = {n: round(e.strength, 4) for n, e in bus.get_log()}
        assert strengths == {"Rm-11": 1.0, "R-1": 0.5, "O-111": 0.5}


class TestDeepTime:
    def test_cosmic_scales_mature_and_small_scales_are_instant(self):
        assert maturation_seconds("Galaxy") > 0
        assert maturation_seconds("Room") == 0
        assert maturation_seconds("SubatomicParticle") == 0
        assert set(MATURATION_SECONDS) == {
            "Multiverse", "Universe", "Galaxy", "Planetary System"}

    def test_scale_env_dials_the_clock(self, monkeypatch):
        monkeypatch.setenv("NESTED_WORLDS_MATURATION_SCALE", "0")
        assert maturation_seconds("Galaxy") == 0
        monkeypatch.setenv("NESTED_WORLDS_MATURATION_SCALE", "2")
        assert maturation_seconds("Galaxy") == MATURATION_SECONDS["Galaxy"] * 2

    def test_planted_change_lands_via_the_pump(self, monkeypatch):
        # Plant with a zero-length clock, then drain: the overlay applies,
        # the chronicle gains SCALE_ACT_MATURED, the room hears it arrive.
        from tests.test_heartbeat import _FakeSock, _decode_frames
        from server.rooms import Player, get_room
        seed = 4501
        root = generate_node_hierarchy(seed=seed, max_depth=3)
        galaxy = root.children[0].children[0]
        verb = VERBS["Galaxy"]
        changed, _ = apply_verb(galaxy, verb, token="Ada:test")
        assert changed
        persistence.enqueue_verb_maturation(
            seed, galaxy.name, verb.name, changed, "Ada", 0)
        assert persistence.pending_verb_maturations(seed) == 1

        room = get_room(seed)
        sock = _FakeSock()
        with room.lock:
            room.players["w"] = Player(name="W", seed=seed, current_node="",
                                       session_id="w", sock=sock)
        landed = heartbeat.drain_matured_verbs()
        assert landed == 1
        assert persistence.pending_verb_maturations(seed) == 0

        overlay = persistence.load_node_property_overrides(seed)
        assert overlay.get(galaxy.name, {}).get("kindled") is True
        history = [h["type"] for h in
                   persistence.get_node_history(seed, galaxy.name)]
        assert "SCALE_ACT_MATURED" in history
        frames = [f for f in _decode_frames(sock.raw)
                  if f.get("type") == "scale_act"]
        assert frames and frames[0]["matured"] is True
        assert frames[0]["changed"].get("kindled") is True

    def test_act_endpoint_plants_instead_of_applying(self, monkeypatch):
        monkeypatch.setenv("NESTED_WORLDS_MATURATION_SCALE", "1")
        from server import _Handler, _ThreadedServer
        server = _ThreadedServer(("127.0.0.1", 0), _Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            root = generate_node_hierarchy(seed=4502, max_depth=6)
            uni = root.children[0]
            body = json.dumps({"seed": 4502, "depth": 6,
                               "node_name": uni.name,
                               "player_name": "Ada"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/act", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
            assert data["matures_in"] and data["matures_in"] > 0
            assert "still traveling" in data["flavor"]
            # Not landed yet: no overlay, but the act is chronicled and
            # the change is in flight.
            overlay = persistence.load_node_property_overrides(4502)
            assert uni.name not in overlay
            assert persistence.pending_verb_maturations(4502) == 1
            acts = [h for h in persistence.get_node_history(4502, uni.name)
                    if h["type"] == "SCALE_ACT"]
            assert acts and acts[0]["data"]["matures_in"] > 0
        finally:
            server.shutdown()


class TestEntanglement:
    def _entangled_pair(self, seed=42):
        from server.handlers import _entangled_twin
        root = generate_node_hierarchy(seed=seed)
        for n in _walk(root, []):
            if n.level != "SubatomicParticle":
                continue
            twin = _entangled_twin(n)
            if twin is not None:
                return n, twin, root
        pytest.skip("no entangled pair in this seed")

    def test_pairing_is_symmetric_and_gated_on_tendency(self):
        from server.handlers import _entangled_twin
        a, b, _ = self._entangled_pair()
        assert _entangled_twin(b) is a or _entangled_twin(b).name == a.name
        assert "entangled" in (a.properties.get("tendency"),
                               b.properties.get("tendency"))

    def test_solving_one_resolves_the_twin(self):
        from server import _Handler, _ThreadedServer
        a, b, _ = self._entangled_pair(seed=42)
        server = _ThreadedServer(("127.0.0.1", 0), _Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            answer = build_puzzle(a).answer
            body = json.dumps({"seed": 42, "depth": 11, "node_name": a.name,
                               "answer": answer,
                               "player_name": "Ada"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/puzzle/attempt", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
            assert data["correct"] is True
            twin_puzzle = build_puzzle(b)
            solve = persistence.get_puzzle_solve(42, b.name, twin_puzzle.name)
            assert solve is not None, "the twin must resolve with its partner"
            twin_rows = [h for h in persistence.get_node_history(42, b.name)
                         if h["type"] == "PUZZLE_SOLVED"]
            assert twin_rows[0]["data"]["entangled_with"] == a.name
        finally:
            server.shutdown()

    def test_unentangled_siblings_stay_local(self):
        from server.handlers import _entangled_twin
        root = generate_node_hierarchy(seed=42)
        loners = [n for n in _walk(root, [])
                  if n.level == "SubatomicParticle"
                  and _entangled_twin(n) is None]
        assert loners, "most particles must stay classical"


class TestEnfoldPuzzles:
    def _cosmic(self, seed=42):
        root = generate_node_hierarchy(seed=seed)
        return [n for n in _walk(root, [])
                if n.level in ("Multiverse", "Universe", "Galaxy",
                               "Planetary System")]

    @staticmethod
    def _is_enfold(p):
        return p.name.startswith(("The Enfolding Count", "The Depth Within",
                                  "The Fold Ordinal"))

    def test_cosmic_scales_serve_enfolds(self):
        served = [build_puzzle(n) for n in self._cosmic()]
        enfolds = [p for p in served if self._is_enfold(p)]
        assert len(enfolds) / len(served) >= 0.2
        assert all(p.kind is PuzzleKind.NAVIGATION for p in enfolds)

    def test_answers_derive_from_the_name_alone(self):
        # Structural answers must be correct AND independent of whether the
        # node came with children attached (pure function of identity).
        from multiverse.generator import resolve_node_by_name
        for n in self._cosmic():
            p = build_puzzle(n)
            if not self._is_enfold(p):
                continue
            suffix = n.name.rpartition("-")[2]
            assert p.answer in {str(len(suffix) - 1),
                                str(len(LEVELS) - len(suffix)),
                                suffix[-1]}, n.name
            resolved = resolve_node_by_name(42, n.name)  # childless twin
            q = build_puzzle(resolved)
            assert (q.name, q.answer) == (p.name, p.answer), (
                "an enfold must not depend on attached children")

    def test_human_scales_never_serve_enfolds(self):
        root = generate_node_hierarchy(seed=42, max_depth=8)
        for n in _walk(root, []):
            if n.level in ("Planet", "Region", "Room", "Object"):
                assert not self._is_enfold(build_puzzle(n)), n.name

    def test_enfolds_never_leak(self):
        from puzzles.generators import _answer_leaks
        for n in self._cosmic():
            p = build_puzzle(n)
            if self._is_enfold(p):
                assert not _answer_leaks(p, n), n.name
