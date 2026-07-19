"""Scale-native verbs: one act per level, each the restorative counterpart
to the world's decay events. Unit coverage for multiverse/verbs.py plus the
full HTTP flow: POST /act applies the material change at the origin,
persists it as a property overlay, records the chronicle entry, and stages
the outward cascade on the causal queue.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

import persistence
from multiverse.generator import LEVELS, generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.verbs import VERBS, VERBS_BY_NAME, apply_verb


@pytest.fixture(autouse=True)
def _zero_hop_delay(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    # Legacy semantics: these tests predate deep time; verbs act instantly.
    monkeypatch.setenv("NESTED_WORLDS_MATURATION_SCALE", "0")
    yield


def _node(level, props):
    return SpatialNode(f"Test-{level}", level, properties=dict(props))


class TestVerbTable:
    def test_every_level_has_exactly_one_verb(self):
        assert set(VERBS) == set(LEVELS)

    def test_verb_names_are_unique(self):
        names = [v.name for v in VERBS.values()]
        assert len(names) == len(set(names))
        assert set(VERBS_BY_NAME) == set(names)

    def test_every_verb_has_a_tagline(self):
        for v in VERBS.values():
            assert len(v.tagline) > 10

    def test_level_mismatch_raises(self):
        node = _node("Room", {})
        with pytest.raises(ValueError, match="only works at"):
            apply_verb(node, VERBS_BY_NAME["mend"])


class TestVerbEffects:
    def test_mend_repairs_condition_stepwise(self):
        node = _node("Object", {"condition": "corrupted"})
        for expected in ("damaged", "worn", "pristine"):
            changed, flavor = apply_verb(node, VERBS_BY_NAME["mend"])
            assert changed["condition"] == expected
            assert expected in flavor
        # Fully mended: nothing left to do.
        changed, flavor = apply_verb(node, VERBS_BY_NAME["mend"])
        assert changed is None
        assert "whole" in flavor

    def test_mend_clears_fracture(self):
        node = _node("Object", {"fractured": True})
        changed, _ = apply_verb(node, VERBS_BY_NAME["mend"])
        assert changed["fractured"] is False

    def test_ward_lowers_danger_to_a_floor(self):
        node = _node("Region", {"danger_level": 3})
        assert apply_verb(node, VERBS_BY_NAME["ward"])[0]["danger_level"] == 2
        assert apply_verb(node, VERBS_BY_NAME["ward"])[0]["danger_level"] == 1
        # At the floor the only remaining change was the warded flag (set on
        # the first call), so a third ward is a no-op.
        assert apply_verb(node, VERBS_BY_NAME["ward"])[0] is None

    def test_inscribe_accumulates_forever(self):
        node = _node("Room", {})
        for n in range(1, 5):
            changed, _ = apply_verb(node, VERBS_BY_NAME["inscribe"])
            assert changed["inscriptions"] == n

    def test_seed_wakes_a_barren_world(self):
        node = _node("Planet", {"inhabited": False, "population": 0})
        changed, flavor = apply_verb(node, VERBS_BY_NAME["seed"])
        assert changed["inhabited"] is True
        assert changed["population"] == 10_000
        assert "lives" in flavor

    def test_seed_swells_an_inhabited_world(self):
        node = _node("Planet", {"inhabited": True, "population": 1000})
        changed, _ = apply_verb(node, VERBS_BY_NAME["seed"])
        assert changed["population"] > 1000

    def test_observe_collapses_superposition_deterministically(self):
        collapses = set()
        for _ in range(3):
            node = _node("SubatomicParticle",
                         {"spin": "superposed", "coherence": 0.5})
            changed, flavor = apply_verb(
                node, VERBS_BY_NAME["observe"], token="Ada:Quark-111111")
            assert changed["spin"] in ("up", "down")
            assert changed["spin"] in flavor
            collapses.add(changed["spin"])
        assert len(collapses) == 1  # same observer, same particle, same fold

    def test_observe_firms_coherence(self):
        node = _node("SubatomicParticle", {"spin": "up", "coherence": 0.5})
        changed, _ = apply_verb(node, VERBS_BY_NAME["observe"])
        assert changed["coherence"] == 0.6

    def test_attune_repairs_stability(self):
        node = _node("Multiverse", {"stability": "collapsing"})
        assert apply_verb(node, VERBS_BY_NAME["attune"])[0]["stability"] == "fraying"
        assert apply_verb(node, VERBS_BY_NAME["attune"])[0]["stability"] == "stable"

    def test_calibrate_converges_on_balance(self):
        node = _node("Universe", {"dark_matter_ratio": 0.9})
        changed, _ = apply_verb(node, VERBS_BY_NAME["calibrate"])
        assert changed["dark_matter_ratio"] == 0.85

    def test_kindle_align_catalyze_excite_move_their_numbers(self):
        cases = [
            ("Galaxy", "kindle", {"star_density": 100}, "star_density", 105),
            ("Planetary System", "align", {"ecliptic_tilt_deg": 20.0},
             "ecliptic_tilt_deg", 18.0),
            ("Molecule", "catalyze", {"bond_count": 3}, "bond_count", 4),
            ("Atom", "excite", {"resonance_nm": 400.0, "ionized": True},
             "resonance_nm", 380.0),
        ]
        for level, verb, props, key, expected in cases:
            node = _node(level, props)
            changed, _ = apply_verb(node, VERBS_BY_NAME[verb])
            assert changed[key] == expected, f"{verb} on {level}"

    def test_every_verb_mutates_a_canonical_node(self):
        # Against real generated nodes (not synthetic props), every level's
        # verb finds something to do on first use — at minimum its flag.
        root = generate_node_hierarchy(seed=7, max_depth=11)
        by_level = {}

        def walk(n):
            by_level.setdefault(n.level, n)
            for c in n.children:
                walk(c)
        walk(root)
        assert set(by_level) == set(LEVELS)
        for level, node in by_level.items():
            if level == "Object":
                # A pristine object legitimately has nothing to mend; give
                # the verb something to work backward.
                node.properties["condition"] = "worn"
            changed, flavor = apply_verb(node, VERBS[level], token="t:x")
            assert changed, f"{VERBS[level].name} had no first effect at {level}"
            assert flavor


class TestActEndpoint:
    @pytest.fixture()
    def srv(self):
        from server import _Handler, _ThreadedServer
        server = _ThreadedServer(("127.0.0.1", 0), _Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()

    def _post(self, srv, path, body):
        req = urllib.request.Request(
            f"{srv}{path}", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())

    def test_act_applies_persists_records_and_stages(self, srv):
        root = generate_node_hierarchy(seed=42, max_depth=6)
        target = root.children[0]  # Universe: has parent AND children

        data = self._post(srv, "/act", {
            "seed": 42, "depth": 6, "node_name": target.name,
            "player_name": "Ada",
        })
        assert data["verb"] == "calibrate"
        assert data["changed"]
        assert data["flavor"]

        # Persisted overlay: the world every participant sees carries it.
        overlay = persistence.load_node_property_overrides(42)[target.name]
        assert overlay.get("calibrated") is True

        # Chronicle entries: the player-attributed record plus the causal
        # rail's own record (which carries the actor in its payload).
        hist = persistence.get_node_history(42, target.name)
        acts = [h for h in hist if h["type"] == "SCALE_ACT"]
        assert any(a["player"] == "Ada" for a in acts)

        # The outward cascade is on the queue, not already everywhere.
        assert persistence.pending_causal_hops(42) >= 2

    def test_act_rejects_the_wrong_verb_for_the_scale(self, srv):
        root = generate_node_hierarchy(seed=42, max_depth=6)
        with pytest.raises(urllib.error.HTTPError) as exc:
            self._post(srv, "/act", {
                "seed": 42, "depth": 6, "node_name": root.children[0].name,
                "verb": "mend",
            })
        assert exc.value.code == 400
        assert "calibrate" in exc.value.read().decode()

    def test_act_404s_on_a_forged_node(self, srv):
        with pytest.raises(urllib.error.HTTPError) as exc:
            self._post(srv, "/act", {
                "seed": 42, "depth": 6, "node_name": "Fake-99", "verb": "ward",
            })
        assert exc.value.code == 404

    def test_world_carries_the_verb_affordance(self, srv):
        with urllib.request.urlopen(f"{srv}/world?seed=42&depth=2") as resp:
            world = json.loads(resp.read())["world"]
        assert world["verb"] == {
            "name": "attune",
            "tagline": VERBS["Multiverse"].tagline,
        }
        assert world["children"][0]["verb"]["name"] == "calibrate"

    def test_second_act_still_reports_flavor_without_change(self, srv):
        root = generate_node_hierarchy(seed=43, max_depth=6)
        # Walk to a subatomic particle? depth 6 world bottoms at Region.
        # Use the root (Multiverse): attune twice — second may still change
        # (flag on first, stability on second) so act until exhausted.
        for _ in range(4):
            data = self._post(srv, "/act", {
                "seed": 43, "depth": 6, "node_name": root.name,
            })
        assert data["changed"] is None
        assert data["flavor"]  # the fiction never goes silent
