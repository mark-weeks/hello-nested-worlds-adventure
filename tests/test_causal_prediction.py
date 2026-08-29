"""The Causal Augury (ADR-010): puzzles that predict the world's dynamics.

Pinned here, as behavior:

- THE FORECAST IS THE PHYSICS: `causality.forecast.up_arm_forecast` fires
  exactly what the live bus fires on the upward arm — same scales, same
  strengths — across every non-flip law on synthetic worlds and across the
  launch world's sampled nodes. The family does not ship without this.
- ANSWERS ARE THE ENGINE'S: every served Augury's answer re-derives from
  the forecast (reach count, terminus living name, echo living name).
- THE ELECTION IS SEED-PURE AND SURGICAL: ~10% of Region-and-deeper serve
  the family (exactly 396 on seed 382, at every epoch); the whole augury path runs in its
  own RNG domain, so every rejection — decline or leak screen — falls
  through byte-identically to the puzzle the node would otherwise serve.
- THE COVENANTS HOLD: difficulty spans 1–4 within the family (per-node,
  never a depth curve), answers never leak, resolver-built and tree-built
  nodes serve identical puzzles, and renewal epochs keep the family while
  renaming the puzzle.
"""
from __future__ import annotations

import pytest

from causality import CausalityBus, EventKind, MIN_STRENGTH
from causality.forecast import up_arm_forecast
from causality.laws import PROFILES, law_for
from multiverse import store
from multiverse.generator import LEVELS, generate_node_hierarchy
from multiverse.node import SpatialNode
from puzzles.generators import (
    _AUGURY_LEVELS,
    _answer_leaks,
    _augury_elected,
    _living_name,
    _make_causal_augury,
    build_puzzle,
    node_difficulty,
)

SEED = 382

# The launch world's Augury census, pinned: 430 elected of 4,077 eligible
# (10.55%) across the six inhabited scales, 396 served at EVERY epoch
# (9.41% of all 4,208 puzzles; 34 elected nodes declined structurally — a
# Threadbare fray before the cry sounds, or every form leaking — and fall
# through byte-identically). Ratified with the conscious puzzle-identity
# re-pin this batch carries.
LAUNCH_AUGURY_SERVED = 396


def _walk(root: SpatialNode) -> list[SpatialNode]:
    out = [root]
    for child in root.children:
        out.extend(_walk(child))
    return out


def _chain_world(law: str) -> SpatialNode:
    """A synthetic single-chain world: one node per scale, the Universe
    carrying `law`. Names carry real path suffixes so living names and
    hash tokens behave exactly as they do in a born world."""
    nodes = []
    for depth, level in enumerate(LEVELS, start=1):
        name = f"Test {level.replace(' ', '')} Chain-{'1' * depth}"
        nodes.append(SpatialNode(name, level, properties={}))
    nodes[1].properties["laws_of_physics"] = law
    for parent, child in zip(nodes, nodes[1:]):
        parent.add_child(child)
    return nodes[0]


def _augury_form(puzzle) -> str:
    if "count the enclosing scales" in puzzle.prompt:
        return "reach"
    if "UNDIMMED" in puzzle.prompt:
        return "echo"
    return "terminus"


class TestForecastIsThePhysics:
    def test_forecast_matches_the_live_bus_under_every_walkable_law(self):
        for law_name, profile in PROFILES.items():
            if profile.flip:
                continue  # the one-armed up walk flips into children there
            root = _chain_world(law_name)
            leaf = _walk(root)[-1]
            forecast = up_arm_forecast(leaf)
            bus = CausalityBus()
            bus.propagate(leaf, EventKind.PUZZLE_SOLVED, direction="up")
            fired = [(name, round(e.strength, 12))
                     for name, e in bus.get_log() if name != leaf.name]
            assert fired == [(h.node.name, round(h.strength, 12))
                             for h in forecast.rung], law_name

    def test_forecast_matches_the_live_bus_across_the_launch_world(self):
        root = generate_node_hierarchy(seed=SEED, max_depth=11)
        mismatches = 0
        checked = 0
        for node in _walk(root)[::13]:
            if node.parent is None:
                continue
            law = law_for(node)
            if law is not None and law.flip:
                continue
            forecast = up_arm_forecast(node)
            bus = CausalityBus()
            bus.propagate(node, EventKind.PUZZLE_SOLVED, direction="up")
            fired = [(name, round(e.strength, 12))
                     for name, e in bus.get_log() if name != node.name]
            if fired != [(h.node.name, round(h.strength, 12))
                         for h in forecast.rung]:
                mismatches += 1
            checked += 1
        assert checked > 200
        assert mismatches == 0

    def test_forecast_is_pure(self):
        root = _chain_world("Probabilistic")  # the drawn-dampening law
        leaf = _walk(root)[-1]
        first = up_arm_forecast(leaf)
        again = up_arm_forecast(leaf)
        assert [(h.node.name, h.strength) for h in first.hops] == \
               [(h.node.name, h.strength) for h in again.hops]

    def test_threadbare_frays_end_the_arm(self):
        # Somewhere in a Threadbare world an arm ends by fray rather than
        # fade — and the forecast knows exactly where.
        root = generate_node_hierarchy(seed=SEED, max_depth=11)
        frays = [up_arm_forecast(n) for n in _walk(root)
                 if (law := law_for(n)) is not None
                 and law.name == "Threadbare" and n.parent is not None]
        dropped = [f for f in frays if f.dropped_at is not None]
        assert dropped, "seed 382's Threadbare universe must fray somewhere"
        for forecast in dropped[:20]:
            assert all(h.node.name != forecast.dropped_at.name
                       for h in forecast.hops)


@pytest.fixture(scope="module")
def launch_auguries():
    root = generate_node_hierarchy(seed=SEED, max_depth=11)
    served = []
    for node in _walk(root):
        if node.level not in _AUGURY_LEVELS or not _augury_elected(node):
            continue
        puzzle = build_puzzle(node)
        if puzzle.name.startswith("The Causal Augury"):
            served.append((node, puzzle))
    return served


class TestAuguryFamily:

    def test_launch_census_is_pinned(self, launch_auguries):
        assert len(launch_auguries) == LAUNCH_AUGURY_SERVED

    def test_every_answer_is_the_engines_forecast(self, launch_auguries):
        for node, puzzle in launch_auguries:
            forecast = up_arm_forecast(node)
            rung = forecast.rung
            form = _augury_form(puzzle)
            if form == "reach":
                assert puzzle.answer == str(len(rung)), node.name
            elif form == "terminus":
                assert puzzle.answer == _living_name(rung[-1].node), node.name
            else:
                echo = next(rung[i] for i in range(1, len(rung))
                            if rung[i].strength == rung[i - 1].strength)
                assert puzzle.answer == _living_name(echo.node), node.name

    def test_no_answer_leaks(self, launch_auguries):
        for node, puzzle in launch_auguries:
            assert not _answer_leaks(puzzle, node), node.name

    def test_difficulty_spans_the_full_range(self, launch_auguries):
        # The covenant: difficulty is the node's own draw, never a depth
        # curve — the family inherits the full 1–4 spread.
        spread = {puzzle.difficulty for _, puzzle in launch_auguries}
        assert spread == {1, 2, 3, 4}
        for node, puzzle in launch_auguries[:50]:
            assert puzzle.difficulty == node_difficulty(node)

    def test_resolver_and_tree_serve_identical_auguries(self, launch_auguries):
        for node, puzzle in launch_auguries[::40]:
            resolved = store.resolve_node_by_name(SEED, node.name)
            rebuilt = build_puzzle(resolved)
            assert (rebuilt.name, rebuilt.prompt, rebuilt.answer) == (
                puzzle.name, puzzle.prompt, puzzle.answer)

    def test_renewal_keeps_the_family_for_every_augury(self, launch_auguries):
        # Family continuity is a contract, not a tendency: form validity is
        # epoch-independent (a leaking form is retried with another valid
        # form), so EVERY node that serves an Augury at epoch 0 serves one
        # at every pinned renewal epoch — renewal renames the puzzle, never
        # its mechanics. (PR #80 review: the single-sample version of this
        # test missed a census churn of 2 at epoch 1 and 4 at epoch 2.)
        for epoch in (1, 2):
            for node, _epoch0 in launch_auguries:
                renewed = build_puzzle(node, epoch=epoch)
                assert renewed.name.startswith("The Causal Augury"), (
                    f"{node.name} lost its Augury at renewal epoch {epoch}")
                assert renewed.name.endswith(f" · Renewal {epoch}")

    def test_the_family_declines_under_inverted_law(self):
        root = _chain_world("Inverted")
        leaf = _walk(root)[-1]
        import random
        assert _make_causal_augury(leaf, random.Random(0),
                                   node_difficulty(leaf)) is None

    def test_a_decline_consumes_no_rng(self, monkeypatch):
        # An elected node the family cannot serve must fall through
        # byte-identically — the weighted draw sees an untouched RNG.
        import puzzles.generators as generators
        root = _chain_world("Inverted")
        leaf = _walk(root)[-1]
        monkeypatch.setattr(generators, "_augury_elected", lambda n: True)
        elected = build_puzzle(leaf)
        monkeypatch.setattr(generators, "_augury_elected", lambda n: False)
        unelected = build_puzzle(leaf)
        assert (elected.name, elected.prompt, elected.answer) == (
            unelected.name, unelected.prompt, unelected.answer)

    def test_election_is_seed_pure(self):
        root = generate_node_hierarchy(seed=SEED, max_depth=11)
        sample = [n for n in _walk(root) if n.level in _AUGURY_LEVELS][:200]
        first = [_augury_elected(n) for n in sample]
        again = [_augury_elected(n) for n in sample]
        assert first == again
        assert any(first) and not all(first)

    def test_the_cry_and_its_forecast_agree_on_minimum_strength(self):
        # Every rung the forecast reports is genuinely audible.
        root = generate_node_hierarchy(seed=SEED, max_depth=11)
        for node in _walk(root)[::101]:
            if node.parent is None:
                continue
            for hop in up_arm_forecast(node).rung:
                assert hop.strength >= MIN_STRENGTH
