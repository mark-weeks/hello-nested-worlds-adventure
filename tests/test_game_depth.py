"""The game-element depth batch: puzzle vocabulary and dressing, renewal +
entropy, agents acting by persona, and per-node verb character.
"""
from __future__ import annotations

import random
import threading

import pytest

import persistence
from causality import CausalityBus, EventKind
from causality.wiring import wire_world_handlers
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from puzzles.engine import PuzzleEngine, build_puzzle
from server import heartbeat
from server.rooms import clear_rooms, get_room


@pytest.fixture(autouse=True)
def _zero_hop_delay(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    yield


def _walk(n, out):
    out.append(n)
    for c in n.children:
        _walk(c, out)
    return out


class TestPuzzleVocabulary:
    def test_answer_space_no_longer_memorizable(self):
        # Pre-expansion: 55% distinct at depth 6 (83 nodes), 4% at depth 11
        # (one riddle answered 410 nodes). The reshape tripled the depth-6
        # world (293 nodes drawing on the same per-level banks), so the
        # honest guards are a ratio floor plus an absolute answer-space
        # floor — together they keep the answer key from collapsing back
        # into a dozen memorizable words per level.
        nodes = _walk(generate_node_hierarchy(seed=42, max_depth=6), [])
        answers = [build_puzzle(n).answer for n in nodes]
        assert len(set(answers)) / len(answers) >= 0.45
        assert len(set(answers)) >= 120

    def test_word_answers_rarely_repeat(self):
        # Numeric sequence answers may repeat (same number, different rule,
        # 99%-distinct prompts); WORD answers are the memorization exploit.
        nodes = _walk(generate_node_hierarchy(seed=42, max_depth=8), [])
        words = [a for a in (build_puzzle(n).answer for n in nodes)
                 if not a.isdigit()]
        from collections import Counter
        worst = Counter(words).most_common(1)[0][1]
        assert worst <= max(3, len(words) // 30), (
            f"a word answer repeats {worst}x across {len(words)} puzzles")

    def test_prompts_are_dressed_in_the_nodes_properties(self):
        nodes = _walk(generate_node_hierarchy(seed=42, max_depth=6), [])
        dressed = sum(
            1 for n in nodes
            if any(str(v) in build_puzzle(n).prompt
                   for k, v in n.properties.items()
                   if isinstance(v, str) and len(str(v)) > 3))
        assert dressed / len(nodes) >= 0.5

    def test_dressing_never_leaks_the_answer(self):
        from puzzles.generators import _answer_leaks
        nodes = _walk(generate_node_hierarchy(seed=42, max_depth=6), [])
        for n in nodes:
            assert not _answer_leaks(build_puzzle(n), n), n.name


class TestLockPuzzles:
    """The travel-key mechanic: `locked` finally does something. A locked
    node's puzzle sends the player one scale UP to read a truth about the
    place that holds it — knowledge-of-the-world, not word-decoding."""

    def _locked(self, root):
        return [n for n in _walk(root, [])
                if n.properties.get("locked") and n.parent is not None]

    def test_locked_rooms_usually_serve_their_lock(self):
        from puzzles.types import PuzzleKind
        locked = self._locked(generate_node_hierarchy(seed=42, max_depth=8))
        assert locked, "the reference world must contain locked rooms"
        served = sum(1 for n in locked
                     if build_puzzle(n).kind is PuzzleKind.LOCK)
        assert served / len(locked) >= 0.5

    def test_answer_is_readable_in_the_keeper_one_scale_up(self):
        from puzzles.generators import _LOCK_KEY_CANDIDATES, _answer_leaks
        from puzzles.types import PuzzleKind
        checked = 0
        for n in self._locked(generate_node_hierarchy(seed=42, max_depth=8)):
            p = build_puzzle(n)
            if p.kind is not PuzzleKind.LOCK:
                continue
            checked += 1
            keeper_values = {str(n.parent.properties[k]).strip().lower()
                             for k in _LOCK_KEY_CANDIDATES
                             if isinstance(n.parent.properties.get(k), str)}
            assert p.answer in keeper_values, n.name
            # Not answerable from where you stand: the key never appears
            # among the locked node's own property values or its prompt.
            own = {str(v).strip().lower() for v in n.properties.values()}
            assert p.answer not in own, n.name
            assert not _answer_leaks(p, n), n.name
        assert checked > 0

    def test_unlocked_nodes_never_serve_a_lock(self):
        from puzzles.types import PuzzleKind
        for n in _walk(generate_node_hierarchy(seed=42, max_depth=6), []):
            if not n.properties.get("locked"):
                assert build_puzzle(n).kind is not PuzzleKind.LOCK, n.name

    def test_lock_keys_are_overlay_immutable(self):
        # The decay/verb overlay mutates danger_level, condition, stability,
        # stabilized, inscriptions… — a lock keyed on those would change its
        # answer under the players mid-session. Pin the contract: locks only
        # listen for generated Region categoricals the overlay never touches.
        from puzzles.generators import _LOCK_KEY_CANDIDATES
        assert set(_LOCK_KEY_CANDIDATES) == {
            "weather", "terrain", "faction_control"}


class TestPuzzleRenewal:
    def test_epoch_changes_name_and_content_deterministically(self):
        node = generate_node_hierarchy(seed=42, max_depth=2).children[0]
        p0a, p0b = build_puzzle(node, 0), build_puzzle(node, 0)
        p1a, p1b = build_puzzle(node, 1), build_puzzle(node, 1)
        assert p0a.name == p0b.name and p0a.answer == p0b.answer
        assert p1a.name == p1b.name and p1a.answer == p1b.answer
        assert p1a.name != p0a.name
        assert "Renewal 1" in p1a.name

    def test_decay_on_a_solved_node_rearms_it(self):
        seed = 301
        node = SpatialNode("Rearm-11", "Region",
                           properties={"danger_level": 4})
        # Not solved yet: decay does NOT re-arm.
        bus = wire_world_handlers(CausalityBus(), seed)
        bus.emit(node, EventKind.DANGER_ALERT, {})
        assert persistence.count_rearms_by_node(seed) == {}

        # Solve, then decay again: the puzzle re-arms exactly once.
        persistence.record_mutation(seed, node.name, "PUZZLE_SOLVED", "Ada",
                                    {"puzzle": "P"})
        bus.emit(node, EventKind.DANGER_ALERT, {})
        assert persistence.count_rearms_by_node(seed) == {node.name: 1}
        # Further decay without a new solve does not stack rearms.
        bus.emit(node, EventKind.DANGER_ALERT, {})
        assert persistence.count_rearms_by_node(seed) == {node.name: 1}

    def test_renewed_puzzle_starts_unsolved_in_the_engine(self):
        seed = 302
        root = generate_node_hierarchy(seed=seed, max_depth=2)
        target = root.children[0]
        base = build_puzzle(target, 0)
        persistence.record_mutation(seed, target.name, "PUZZLE_SOLVED", "Ada",
                                    {"puzzle": base.name})
        persistence.record_mutation(seed, target.name, "PUZZLE_REARM", None,
                                    {"trigger": "DANGER_ALERT"})
        engine = PuzzleEngine(seed=seed)
        engine.attach_puzzles(root, persistence.count_rearms_by_node(seed))
        renewed = engine.puzzle_for(target)
        assert "Renewal 1" in renewed.name
        assert persistence.get_puzzle_solve(seed, target.name,
                                            renewed.name) is None


class TestPersonaActs:
    def _tick_until(self, seed, predicate, personas, tries=25):
        rng = random.Random(11)
        for _ in range(tries):
            summary = heartbeat.run_tick(seed=seed, rng=rng, pace=0.0)
            if summary["persona"] in personas and predicate(summary):
                return summary
        return None

    def test_destabilizers_emit_real_decay(self):
        clear_rooms()
        s = self._tick_until(
            303, lambda s: s.get("act", "").startswith("destabilized"),
            personas={"destabilizer"})
        assert s is not None, "no destabilizer act within 25 ticks"
        muts = persistence.get_mutations(303, limit=300)
        kinds = {m["type"] for m in muts}
        assert kinds & {"DANGER_ALERT", "STRUCTURAL_CHANGE"}

    def test_tenders_and_scholars_perform_verbs(self):
        clear_rooms()
        s = self._tick_until(
            304, lambda s: s.get("act") and not s["act"].startswith("destab"),
            personas={"tender", "scholar"})
        assert s is not None, "no tending act within 25 ticks"
        acts = [m for m in persistence.get_mutations(304, limit=300)
                if m["type"] == "SCALE_ACT"]
        assert acts and acts[0]["data"].get("agent")


class TestVerbCharacter:
    def test_flavor_carries_the_nodes_own_aspect(self):
        node = generate_node_hierarchy(seed=42, max_depth=1)
        from multiverse.verbs import VERBS, apply_verb
        changed, flavor = apply_verb(node, VERBS[node.level], token="t")
        assert changed
        clause = node.properties["aspect"].split(";")[0].strip().rstrip(".")
        assert clause[1:] in flavor  # woven in (capitalized first letter)

    def test_two_nodes_same_verb_read_differently(self):
        root = generate_node_hierarchy(seed=42, max_depth=3)
        from multiverse.verbs import VERBS, apply_verb
        regions = [n for n in _walk(root, []) if n.level == "Galaxy"]
        flavors = set()
        for n in regions[:2]:
            _, flavor = apply_verb(n, VERBS["Galaxy"], token="t")
            flavors.add(flavor)
        assert len(flavors) == len(regions[:2])


class TestVoiceSelfKnowledge:
    def test_presentation_line_matches_state(self):
        from consciousness import _presentation_line
        calm = SpatialNode("V-11", "Room", properties={})
        line = _presentation_line(calm)
        assert "paneled walls" in line and "quiet consonance" in line
        hot = SpatialNode("V-12", "Region",
                          properties={"danger_level": 9})
        assert "looming half-step" in _presentation_line(hot)
        safe = SpatialNode("V-13", "Region",
                           properties={"danger_level": 9, "stabilized": True})
        assert "bright, floating" in _presentation_line(safe)

    def test_image_prompt_carries_the_aspect(self):
        from server.imageprompt import assemble_prompt
        node = generate_node_hierarchy(seed=42, max_depth=1)
        prompt = assemble_prompt(node.level, node.name, node.properties, [], 0)
        assert node.properties["aspect"] in prompt
