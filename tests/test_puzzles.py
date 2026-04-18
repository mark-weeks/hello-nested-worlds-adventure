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
        # max_depth=7 ensures Room nodes (level index 5) are generated, which carry has_puzzle
        root = generate_node_hierarchy(seed=42, max_depth=7, min_breadth=2, max_breadth=2)
        engine = PuzzleEngine(seed=42)
        engine.attach_puzzles(root)
        puzzles = engine.collect_puzzles(root)
        assert len(puzzles) > 0

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
