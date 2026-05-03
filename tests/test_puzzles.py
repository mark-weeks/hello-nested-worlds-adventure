import pytest
from puzzles.types import Puzzle, PuzzleKind, PuzzleResult
from puzzles.engine import PuzzleEngine
from multiverse.generator import generate_node_hierarchy


def make_puzzle(**kwargs):
    defaults = dict(
        name="Test Puzzle",
        kind=PuzzleKind.RIDDLE,
        prompt="What is 1+1?",
        answer="2",
        hints=["It's a small number.", "Greater than one."],
        max_attempts=3,
    )
    defaults.update(kwargs)
    return Puzzle(**defaults)


class TestPuzzleTypes:
    def test_correct_answer_solves(self):
        p = make_puzzle()
        result = p.attempt("2")
        assert result == PuzzleResult.SOLVED
        assert p.solved

    def test_case_insensitive(self):
        p = make_puzzle(answer="echo")
        assert p.attempt("Echo") == PuzzleResult.SOLVED

    def test_whitespace_stripped(self):
        p = make_puzzle(answer="echo")
        assert p.attempt("  echo  ") == PuzzleResult.SOLVED

    def test_wrong_answer_increments_attempts(self):
        p = make_puzzle()
        p.attempt("wrong")
        assert p.attempts == 1
        assert p.result == PuzzleResult.UNSOLVED

    def test_exceeds_max_attempts_fails(self):
        p = make_puzzle(max_attempts=2)
        p.attempt("wrong")
        result = p.attempt("also wrong")
        assert result == PuzzleResult.FAILED
        assert p.failed

    def test_no_attempt_after_solved(self):
        p = make_puzzle()
        p.attempt("2")
        result = p.attempt("2")
        assert result == PuzzleResult.SOLVED
        assert p.attempts == 1  # second attempt was ignored

    def test_hint_after_first_wrong(self):
        p = make_puzzle(hints=["Hint 1", "Hint 2"])
        p.attempt("wrong")
        assert p.hint() == "Hint 1"

    def test_no_hint_before_attempt(self):
        p = make_puzzle(hints=["Hint 1"])
        assert p.hint() is None


class TestPuzzleEngine:
    def test_attach_and_collect(self):
        # Puzzles are assigned at every level, so any depth works
        root = generate_node_hierarchy(seed=42, max_depth=3, min_breadth=2, max_breadth=2)
        engine = PuzzleEngine(seed=42)
        engine.attach_puzzles(root)
        puzzles = engine.collect_puzzles(root)
        assert len(puzzles) > 0

    def test_puzzles_at_all_levels(self):
        # One node per level; every node must receive a puzzle
        root = generate_node_hierarchy(seed=42, max_depth=11, min_breadth=1, max_breadth=1)
        engine = PuzzleEngine(seed=42)
        count = engine.attach_puzzles(root)
        puzzles = engine.collect_puzzles(root)
        assert count == 11
        assert len(puzzles) == 11

    def test_region_lock_uses_danger_level(self):
        root = generate_node_hierarchy(seed=42, max_depth=6, min_breadth=1, max_breadth=1)
        engine = PuzzleEngine(seed=42)
        engine.attach_puzzles(root)

        # Walk down to the Region node (index 5 in the chain)
        node = root
        for _ in range(5):
            node = node.children[0]
        assert node.level == "Region"

        puzzle = node.properties["puzzle"]
        danger = node.properties["danger_level"]
        assert puzzle.kind == PuzzleKind.LOCK
        assert puzzle.answer == str(danger * 2)

    def test_attached_puzzles_are_puzzle_instances(self):
        root = generate_node_hierarchy(seed=42, max_depth=7, min_breadth=2, max_breadth=2)
        engine = PuzzleEngine(seed=1)
        engine.attach_puzzles(root)
        puzzles = engine.collect_puzzles(root)
        for p in puzzles:
            assert isinstance(p, Puzzle)

    def test_attach_is_idempotent(self):
        root = generate_node_hierarchy(seed=42, max_depth=7, min_breadth=2, max_breadth=2)
        engine = PuzzleEngine(seed=1)
        engine.attach_puzzles(root)
        count1 = len(engine.collect_puzzles(root))
        engine.attach_puzzles(root)
        count2 = len(engine.collect_puzzles(root))
        assert count1 == count2


# ── Dynamic puzzle generators (one per level) ──────────────────────────────


from multiverse.node import SpatialNode  # noqa: E402  — keep test imports tidy
from puzzles.engine import _make_puzzle_for_node  # noqa: E402
import random as _random  # noqa: E402


def _gen(level: str, **props) -> Puzzle:
    node = SpatialNode(name=f"Test-{level}", level=level, properties=props)
    return _make_puzzle_for_node(node, _random.Random(0))


class TestMultiverseAnagram:
    def test_kind_and_answer(self):
        p = _gen("Multiverse", theme="entropy")
        assert p.kind == PuzzleKind.ANAGRAM
        assert p.answer == "entropy"

    def test_prompt_includes_scrambled_letters(self):
        p = _gen("Multiverse", theme="paradox")
        scrambled = "".join(sorted("paradox".upper()))
        assert scrambled in p.prompt


class TestGalaxyRiddle:
    def test_kind_and_answer(self):
        p = _gen("Galaxy", shape="spiral")
        assert p.kind == PuzzleKind.RIDDLE
        assert p.answer == "spiral"

    def test_unknown_shape_falls_back(self):
        # An unknown shape should still produce a usable puzzle whose answer
        # is the shape itself.
        p = _gen("Galaxy", shape="cruller")
        assert p.answer == "cruller"


class TestPlanetarySystemLogic:
    def test_kind_and_halved_count(self):
        p = _gen("Planetary System", planet_count=8)
        assert p.kind == PuzzleKind.LOGIC
        assert p.answer == "4"

    def test_odd_count_floors(self):
        p = _gen("Planetary System", planet_count=7)
        assert p.answer == "3"


class TestRoomNavigation:
    def test_kind_and_clamp(self):
        p = _gen("Room", exits=4)
        assert p.kind == PuzzleKind.NAVIGATION
        assert p.answer == "3"  # min(3, 4)

    def test_two_exits_returns_two(self):
        p = _gen("Room", exits=2)
        assert p.answer == "2"

    def test_one_exit_returns_one(self):
        p = _gen("Room", exits=1)
        assert p.answer == "1"


class TestObjectLogic:
    def test_kind_and_quartered(self):
        p = _gen("Object", weight_kg=8.0)
        assert p.kind == PuzzleKind.LOGIC
        assert p.answer == "2.0"

    def test_decimal_weight_rounds_to_two_places(self):
        p = _gen("Object", weight_kg=10.0)
        assert p.answer == "2.5"


class TestMoleculeLogic:
    def test_kind_and_electron_count(self):
        p = _gen("Molecule", bond_count=4)
        assert p.kind == PuzzleKind.LOGIC
        assert p.answer == "8"


class TestAtomLogic:
    def test_kind_and_proton_count(self):
        p = _gen("Atom", atomic_number=26)
        assert p.kind == PuzzleKind.LOGIC
        assert p.answer == "26"


class TestSubatomicRiddle:
    def test_kind_and_answer(self):
        p = _gen("SubatomicParticle", particle_type="electron")
        assert p.kind == PuzzleKind.RIDDLE
        assert p.answer == "electron"

    def test_unknown_particle_falls_back(self):
        p = _gen("SubatomicParticle", particle_type="muon")
        assert p.answer == "muon"


class TestAllElevenLevelsDynamic:
    """Every canonical level should resolve to a dynamic generator, not a
    pool fallback. The generators all produce uniquely-named puzzles, so
    the cleanest check is that the names appear in the dynamic-name set."""

    DYNAMIC_NAMES = {
        "The Theme Anagram",
        "The Dark Matter Fraction",
        # Galaxy + Planet + SubatomicParticle templates: name varies by
        # property, so we match on prefix instead.
    }
    DYNAMIC_NAME_PREFIXES = ("The ", )  # all dynamic puzzles start with "The "

    def test_one_node_per_level_uses_dynamic_generator(self):
        from agents.agent import Agent  # noqa: F401  — generation triggers tree
        root = generate_node_hierarchy(seed=42, max_depth=11,
                                       min_breadth=1, max_breadth=1)
        engine = PuzzleEngine(seed=42)
        engine.attach_puzzles(root)
        puzzles = engine.collect_puzzles(root)
        assert len(puzzles) == 11
        # Every dynamic generator names its puzzle starting with "The ".
        # Static pool entries also begin with "The " in many cases, so we
        # additionally require the name doesn't appear in any LEVEL_POOLS
        # entry — meaning the puzzle came from a generator, not a pool.
        from puzzles.data import LEVEL_POOLS
        pool_names = {p.name for puzzles_list in LEVEL_POOLS.values()
                      for p in puzzles_list}
        for puzzle in puzzles:
            assert puzzle.name not in pool_names, (
                f"{puzzle.name!r} matches a static pool entry — expected dynamic"
            )
