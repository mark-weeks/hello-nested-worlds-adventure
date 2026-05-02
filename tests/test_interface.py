from __future__ import annotations

import io
from unittest.mock import patch

import pytest

import causality
from multiverse.node import SpatialNode
from interface import (
    _fmt,
    _print_look,
    _print_map,
    _print_breadcrumb,
    _descend,
    _ambient_mode,
    build_depth_map,
    _play_puzzle,
    _AMBIENT_DAMPENING,
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
                _ambient_mode(root)
        assert causality._default._handlers == []
        assert causality.get_log() == []

    def test_ambient_fires_causal_events(self, capsys):
        root = make_tree()
        with patch("builtins.input", return_value=""):
            with patch("time.sleep"):
                _ambient_mode(root)
        out = capsys.readouterr().out
        # Every tree node should appear as the agent visits it
        assert "Aethon-1" in out
        assert "Vela-2" in out
        assert "Kethara-3" in out

    def test_ambient_clears_log_on_exit(self):
        root = make_tree()
        with patch("builtins.input", return_value=""):
            with patch("time.sleep"):
                _ambient_mode(root)
        assert causality.get_log() == []

    def test_ambient_strength_dampens_with_depth(self, capsys):
        root = make_tree()
        with patch("builtins.input", return_value=""):
            with patch("time.sleep"):
                _ambient_mode(root)
        out = capsys.readouterr().out
        # Root should show 1.00, deeper nodes less
        assert "1.00" in out
        assert f"{_AMBIENT_DAMPENING:.2f}" in out


class TestPuzzleMode:
    def test_play_puzzle_at_any_level(self, capsys):
        # Every node now gets a level-appropriate puzzle
        leaf = SpatialNode("Barren", "SubatomicParticle")
        with patch("builtins.input", return_value="wrong"):
            _play_puzzle(leaf, seed=999)
        out = capsys.readouterr().out
        assert "===" in out  # puzzle header always appears

    def test_play_puzzle_with_puzzle_node(self, capsys):
        node = SpatialNode("Vault", "Room", properties={"has_puzzle": True})
        with patch("builtins.input", return_value="quit"):
            _play_puzzle(node, seed=42)
