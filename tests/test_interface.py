from __future__ import annotations

import io
from unittest.mock import patch

import pytest

import causality
import persistence
from multiverse.node import SpatialNode
from multiverse.utils import build_depth_map
from interface import (
    _fmt,
    _print_look,
    _print_map,
    _print_breadcrumb,
    _descend,
    _ambient_mode,
    _play_puzzle,
)


def make_tree() -> SpatialNode:
    root = SpatialNode("Aethon-1", "Multiverse", properties={"stability": "stable"})
    galaxy = SpatialNode("Vela-2", "Galaxy", properties={"shape": "spiral"})
    planet = SpatialNode("Kethara-3", "Planet", properties={"danger_level": 2})
    galaxy.add_child(planet)
    root.add_child(galaxy)
    return root


@pytest.fixture(autouse=True)
def _reset_causality():
    causality.clear_handlers()
    causality.clear_log()
    yield
    causality.clear_handlers()
    causality.clear_log()


class TestFormatting:
    def test_fmt_includes_level_and_name(self):
        node = SpatialNode("Vault-1", "Room")
        result = _fmt(node)
        assert "Room" in result
        assert "Vault-1" in result

    def test_fmt_applies_ansi_reset(self):
        node = SpatialNode("X", "Planet")
        assert "\033[0m" in _fmt(node)

    def test_print_look_shows_children(self, capsys):
        root = make_tree()
        _print_look(root)
        out = capsys.readouterr().out
        assert "Vela-2" in out
        assert "[1]" in out

    def test_print_look_leaf_node(self, capsys):
        leaf = SpatialNode("Leaf", "SubatomicParticle", properties={"spin": "up"})
        _print_look(leaf)
        out = capsys.readouterr().out
        assert "leaf node" in out

    def test_print_look_shows_properties(self, capsys):
        node = SpatialNode("X", "Planet", properties={"biome": "jungle", "gravity": 1.5})
        _print_look(node)
        out = capsys.readouterr().out
        assert "biome" in out
        assert "jungle" in out

    def test_print_breadcrumb_shows_path(self, capsys):
        root = make_tree()
        stack = [root, root.children[0]]
        _print_breadcrumb(stack)
        out = capsys.readouterr().out
        assert "Aethon-1" in out
        assert "Vela-2" in out
        assert "→" in out

    def test_print_map_renders_tree(self, capsys):
        root = make_tree()
        _print_map(root)
        out = capsys.readouterr().out
        assert "Aethon-1" in out
        assert "Vela-2" in out
        assert "Kethara-3" in out

    def test_print_map_truncates_at_max_depth(self, capsys):
        root = make_tree()
        _print_map(root, max_depth=0)
        out = capsys.readouterr().out
        assert "Vela-2" not in out or "…" in out


class TestNavigation:
    def test_descend_enters_child(self, capsys):
        root = make_tree()
        stack = [root]
        _descend(stack, 1)
        assert stack[-1].name == "Vela-2"

    def test_descend_out_of_range(self, capsys):
        root = make_tree()
        stack = [root]
        _descend(stack, 99)
        out = capsys.readouterr().out
        assert "No path" in out
        assert len(stack) == 1

    def test_descend_leaf_node(self, capsys):
        leaf = SpatialNode("Leaf", "SubatomicParticle")
        stack = [leaf]
        _descend(stack, 1)
        out = capsys.readouterr().out
        assert "No deeper" in out
        assert len(stack) == 1


class TestDepthMap:
    def test_root_is_depth_zero(self):
        root = make_tree()
        dm = build_depth_map(root)
        assert dm[root.id] == 0

    def test_child_is_depth_one(self):
        root = make_tree()
        dm = build_depth_map(root)
        assert dm[root.children[0].id] == 1

    def test_grandchild_is_depth_two(self):
        root = make_tree()
        grandchild = root.children[0].children[0]
        dm = build_depth_map(root)
        assert dm[grandchild.id] == 2

    def test_all_nodes_present(self):
        root = make_tree()
        dm = build_depth_map(root)
        assert len(dm) == 3  # root + galaxy + planet


class TestAmbientMode:
    def test_ambient_does_not_pollute_global(self):
        """Ambient mode runs in an isolated CausalityBus; global is untouched."""
        root = make_tree()
        with patch("builtins.input", return_value=""):
            with patch("time.sleep"):
                _ambient_mode(root, seed=777)
        assert causality._default._handlers == []
        assert causality.get_log() == []

    def test_ambient_fires_causal_events(self, capsys):
        root = make_tree()
        with patch("builtins.input", return_value=""):
            with patch("time.sleep"):
                _ambient_mode(root, seed=777)
        out = capsys.readouterr().out
        # Every tree node should appear as the agent visits it
        assert "Aethon-1" in out
        assert "Vela-2" in out
        assert "Kethara-3" in out

    def test_ambient_clears_log_on_exit(self):
        root = make_tree()
        with patch("builtins.input", return_value=""):
            with patch("time.sleep"):
                _ambient_mode(root, seed=777)
        assert causality.get_log() == []

    def test_ambient_shows_real_event_strengths(self, capsys):
        # A puzzle node makes the agent INTERACT, which propagates with
        # dampening — the displayed bar must show the engine's actual
        # strengths (1.00 at origin, 0.50 one hop out), not a display-side
        # depth curve.
        root = make_tree()
        planet = root.children[0].children[0]
        planet.properties["has_puzzle"] = True
        with patch("builtins.input", return_value=""):
            with patch("time.sleep"):
                _ambient_mode(root, seed=777)
        out = capsys.readouterr().out
        assert "1.00" in out
        assert "0.50" in out

    def test_ambient_leaves_persistent_traces(self):
        # What you watched happen genuinely happened: the observer's events
        # land in world_mutations like every other participant's.
        root = make_tree()
        with patch("builtins.input", return_value=""):
            with patch("time.sleep"):
                _ambient_mode(root, seed=778)
        mutations = persistence.get_mutations(778)
        assert mutations, "ambient observation must leave durable traces"
        assert any(m["data"].get("agent") == "Observer" for m in mutations)


class TestPuzzleMode:
    def test_play_puzzle_at_any_level(self, capsys):
        # Every node now gets a level-appropriate puzzle
        leaf = SpatialNode("Barren", "SubatomicParticle")
        with patch("builtins.input", return_value="wrong"):
            _play_puzzle(leaf, seed=999)
        out = capsys.readouterr().out
        assert "===" in out  # puzzle header always appears

    def test_play_puzzle_abandon_is_safe(self, capsys):
        node = SpatialNode("Vault-1", "Room", properties={"has_puzzle": True})
        with patch("builtins.input", return_value="quit"):
            _play_puzzle(node, seed=42)
        out = capsys.readouterr().out
        assert "===" in out

    def test_puzzle_never_leaks_into_node_properties(self):
        # REGRESSION: the Puzzle object (repr includes answer + hints) used
        # to be stored in node.properties, where `look` printed it and the
        # consciousness prompt ingested it — the node could be asked for its
        # own answer. Puzzles must never touch properties.
        node = SpatialNode("Vault-1", "Room", properties={"has_puzzle": True})
        with patch("builtins.input", return_value="quit"):
            _play_puzzle(node, seed=42)
        assert "puzzle" not in node.properties

    def test_solved_puzzle_persists_and_cascades(self, capsys):
        # A CLI solve is a real solve: mutation recorded, ripple accrued.
        from puzzles.engine import PuzzleEngine
        node = SpatialNode("Vault-1", "Room", properties={"has_puzzle": True})
        engine = PuzzleEngine(seed=31)
        engine.attach_puzzles(node)
        answer = engine.puzzle_for(node).answer
        with patch("builtins.input", return_value=answer):
            _play_puzzle(node, seed=31)
        mutations = persistence.get_mutations(31)
        assert any(m["type"] == "PUZZLE_SOLVED" for m in mutations)
        assert persistence.get_ripple_score(31, "Vault-1") > 0


class TestPassageTags:
    def test_meaningful_traits_are_tagged(self, capsys):
        from interface import _passage_tags
        danger = SpatialNode("D", "Region", properties={"danger_level": 8})
        calm = SpatialNode("C", "Region",
                           properties={"danger_level": 2, "stabilized": True})
        hot = SpatialNode("H", "Room", properties={})
        hot.ripple_score = 0.5
        assert "danger 8" in _passage_tags(danger)
        assert "stabilized" in _passage_tags(calm)
        assert "≈ pressure" in _passage_tags(hot)

    def test_ubiquitous_traits_are_not_tagged(self):
        from interface import _passage_tags
        node = SpatialNode("N", "Room",
                           properties={"has_puzzle": True, "exits": 2})
        assert _passage_tags(node) == []

    def test_look_renders_tags_on_children(self, capsys):
        root = SpatialNode("Root", "Planet", properties={"biome": "ocean"})
        root.add_child(SpatialNode("Hot", "Region",
                                   properties={"danger_level": 9}))
        _print_look(root)
        out = capsys.readouterr().out
        assert "danger 9" in out
