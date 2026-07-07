"""Composed puzzles: the world's own relationships as puzzle structure.

Constellations (nested — a container completes over its children),
lineage sigils (enfolded — the answer is distributed across the ancestor
chain), and bonds (an atom answers one scale up). The middle of the
world stops being mechanically flat.
"""
from __future__ import annotations

import json
import threading
import urllib.request

import pytest

import persistence
from multiverse.generator import generate_node_hierarchy, resolve_node_by_name
from puzzles.engine import build_puzzle
from server.handlers import (
    _check_constellation, _constellation_progress,
)
from server.rooms import get_room
from tests.test_heartbeat import _FakeSock, _decode_frames


@pytest.fixture(autouse=True)
def _zero_hop_delay(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    yield


def _walk(n, out):
    out.append(n)
    for c in n.children:
        _walk(c, out)
    return out


def _human_solve(seed, node, epoch=None):
    if epoch is None:
        epoch = persistence.count_node_mutations(seed, node.name,
                                                 "PUZZLE_REARM")
    pz = build_puzzle(node, epoch)
    persistence.record_mutation(
        seed, node.name, "PUZZLE_SOLVED", "Ada",
        {"puzzle": pz.name, "contributors": ["Ada"]},
        actor_identity="ada-id")
    return pz


class TestLineageSigils:
    def _lineages(self, seed=42):
        root = generate_node_hierarchy(seed=seed)
        return [(n, build_puzzle(n)) for n in _walk(root, [])
                if build_puzzle(n).name.startswith("The Lineage Sigil")]

    def test_served_at_deep_scales_only(self):
        pairs = self._lineages()
        assert pairs, "the deep world must serve lineage sigils"
        assert {n.level for n, _ in pairs} <= {"Object", "Molecule"}

    def test_answer_is_the_ancestral_acrostic(self):
        for n, p in self._lineages()[:40]:
            anc = {}
            up = n.parent
            while up is not None:
                anc[up.level] = up
                up = up.parent
            expected = (anc["Region"].properties["weather"].strip()[0]
                        + anc["Planet"].properties["biome"].strip()[0]
                        + anc["Galaxy"].properties["shape"].strip()[0]).lower()
            assert p.answer == expected, n.name

    def test_pure_function_of_identity(self):
        # The resolver builds the full ancestor chain, so a childless twin
        # must yield the identical puzzle.
        for n, p in self._lineages()[::25]:
            twin = resolve_node_by_name(42, n.name)
            q = build_puzzle(twin)
            assert (q.name, q.answer) == (p.name, p.answer), n.name

    def test_never_leaks(self):
        from puzzles.generators import _answer_leaks
        for n, p in self._lineages()[::10]:
            assert not _answer_leaks(p, n), n.name


class TestBondPuzzles:
    def _bonds(self, seed=42):
        root = generate_node_hierarchy(seed=seed)
        return [(n, build_puzzle(n)) for n in _walk(root, [])
                if build_puzzle(n).name.startswith("The Bond of the ")]

    def test_served_at_atoms_only(self):
        pairs = self._bonds()
        assert pairs, "atoms must serve bond puzzles"
        assert {n.level for n, _ in pairs} == {"Atom"}

    def test_answer_reads_the_binding_molecule(self):
        for n, p in self._bonds()[:40]:
            mol = n.parent
            assert p.answer in {
                str(mol.properties.get("geometry", "")).strip().lower(),
                str(mol.properties.get("compound_type", "")).strip().lower(),
            }, n.name

    def test_pure_function_of_identity(self):
        for n, p in self._bonds()[::40]:
            twin = resolve_node_by_name(42, n.name)
            q = build_puzzle(twin)
            assert (q.name, q.answer) == (p.name, p.answer), n.name


class TestConstellations:
    def _region(self, seed):
        root = generate_node_hierarchy(seed=seed)
        return next(n for n in _walk(root, [])
                    if n.level == "Region" and n.children)

    def test_partial_progress_does_not_complete(self):
        seed = 4601
        region = self._region(seed)
        _human_solve(seed, region.children[0])
        solved, total = _constellation_progress(seed, region)
        assert (solved, total) == (1, len(region.children))
        _check_constellation(seed, get_room(seed), region, "Ada", "ada-id")
        assert persistence.count_node_mutations(
            seed, region.name, "CONSTELLATION_COMPLETE") == 0

    def test_full_progress_completes_permanently_and_broadcasts(self):
        seed = 4602
        region = self._region(seed)
        room = get_room(seed)
        sock = _FakeSock()
        from server.rooms import Player
        with room.lock:
            room.players["w"] = Player(name="W", seed=seed, current_node="",
                                       session_id="w", sock=sock)
        for child in region.children:
            _human_solve(seed, child)
        _check_constellation(seed, room, region, "Ada", "ada-id")

        rows = [h for h in persistence.get_node_history(seed, region.name, 50)
                if h["type"] == "CONSTELLATION_COMPLETE"]
        assert len(rows) == 1
        assert rows[0]["player"] == "Ada"
        assert rows[0]["data"]["children"] == len(region.children)
        overlay = persistence.load_node_property_overrides(seed)
        assert overlay[region.name]["constellated"] is True
        frames = [f for f in _decode_frames(sock.raw)
                  if f.get("type") == "constellation_complete"]
        assert frames and frames[0]["node"] == region.name
        # The completion cascades outward under the local physics.
        assert persistence.pending_causal_hops(seed) > 0

        # Idempotent — and permanent: a later renewal of a child does not
        # unlight it, and a re-check does not double-record.
        persistence.record_mutation(seed, region.children[0].name,
                                    "PUZZLE_REARM", None, {"trigger": "X"})
        _check_constellation(seed, room, region, "Ben", "ben-id")
        rows = [h for h in persistence.get_node_history(seed, region.name, 50)
                if h["type"] == "CONSTELLATION_COMPLETE"]
        assert len(rows) == 1

    def test_agent_solves_do_not_light_constellations(self):
        seed = 4603
        region = self._region(seed)
        for child in region.children:
            pz = build_puzzle(child, 0)
            persistence.record_mutation(
                seed, child.name, "PUZZLE_SOLVED", None,
                {"puzzle": pz.name, "agent": "Tessera"},
                actor_identity="Tessera")
        _check_constellation(seed, get_room(seed), region, None, None)
        assert persistence.count_node_mutations(
            seed, region.name, "CONSTELLATION_COMPLETE") == 0

    def test_solve_endpoint_lights_the_container(self):
        # End to end: solving the last room of a region over HTTP fires
        # the constellation without any explicit client involvement.
        from server import _Handler, _ThreadedServer
        seed = 42
        region = self._region(seed)
        server = _ThreadedServer(("127.0.0.1", 0), _Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            # Pre-solve all children but the last directly…
            for child in region.children[:-1]:
                _human_solve(seed, child)
            # …then solve the last one through the real endpoint.
            last = region.children[-1]
            answer = build_puzzle(last).answer
            body = json.dumps({"seed": seed, "depth": 11,
                               "node_name": last.name, "answer": answer,
                               "player_name": "Ada"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/puzzle/attempt", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                assert json.loads(resp.read())["correct"] is True
            rows = [h for h in
                    persistence.get_node_history(seed, region.name, 50)
                    if h["type"] == "CONSTELLATION_COMPLETE"]
            assert len(rows) == 1

            # And /puzzle reports the container's nested progress.
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/puzzle?seed={seed}&depth=11"
                    f"&node_name={urllib.parse.quote(region.name)}") as resp:
                data = json.loads(resp.read())
            assert data["constellation"]["complete"] is True
            assert data["constellation"]["solved"] == len(region.children)
        finally:
            server.shutdown()
