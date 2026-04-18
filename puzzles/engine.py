# puzzles/engine.py

import random
from typing import List, Optional
from multiverse.node import SpatialNode
from puzzles.types import Puzzle, PuzzleKind, PuzzleResult

_RIDDLES = [
    Puzzle(
        name="The Silent Guardian",
        kind=PuzzleKind.RIDDLE,
        prompt="I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?",
        answer="echo",
        hints=["Think of sound.", "It bounces back."],
    ),
    Puzzle(
        name="The Endless Stair",
        kind=PuzzleKind.RIDDLE,
        prompt="The more you take, the more you leave behind. What am I?",
        answer="footsteps",
        hints=["Think of what you leave as you walk.", "Not a physical object."],
    ),
    Puzzle(
        name="The Paradox Box",
        kind=PuzzleKind.RIDDLE,
        prompt="I have cities but no houses, mountains but no trees, water but no fish. What am I?",
        answer="map",
        hints=["You can hold the whole world in your hands.", "It's flat."],
    ),
]

_CIPHER_PUZZLES = [
    Puzzle(
        name="The Shifted Message",
        kind=PuzzleKind.CIPHER,
        prompt="Decode this Caesar-3 cipher: HQWHU WKH YDXOW",
        answer="enter the vault",
        hints=["Each letter is shifted by 3.", "Shift each letter back by 3 positions."],
    ),
]

_LOCK_PUZZLES = [
    Puzzle(
        name="The Four-Digit Lock",
        kind=PuzzleKind.LOCK,
        prompt="The code is the sum of the first four primes.",
        answer="17",
        hints=["The first four primes are 2, 3, 5, 7.", "Add them together."],
        max_attempts=5,
    ),
]

_SEQUENCE_PUZZLES = [
    Puzzle(
        name="The Elemental Order",
        kind=PuzzleKind.SEQUENCE,
        prompt="Arrange these in order of atomic number (lowest first): Fe, H, O, C",
        answer="h c o fe",
        hints=["Atomic numbers: H=1, C=6, O=8, Fe=26.", "Separate with spaces."],
    ),
]

_ALL_PUZZLES = _RIDDLES + _CIPHER_PUZZLES + _LOCK_PUZZLES + _SEQUENCE_PUZZLES


class PuzzleEngine:
    def __init__(self, seed: int = 0):
        self._rng = random.Random(seed)
        self._active: Optional[Puzzle] = None

    def attach_puzzles(self, root: SpatialNode) -> int:
        count = 0
        self._attach(root, count_ref := [0])
        return count_ref[0]

    def _attach(self, node: SpatialNode, count_ref: list):
        if node.properties.get("has_puzzle") and "puzzle" not in node.properties:
            import copy
            node.properties["puzzle"] = copy.deepcopy(self._rng.choice(_ALL_PUZZLES))
            count_ref[0] += 1
        for child in node.children:
            self._attach(child, count_ref)

    def collect_puzzles(self, root: SpatialNode) -> List[Puzzle]:
        results = []
        self._collect(root, results)
        return results

    def _collect(self, node: SpatialNode, results: list):
        p = node.properties.get("puzzle")
        if p:
            results.append(p)
        for child in node.children:
            self._collect(child, results)

    def run_puzzle(self, puzzle: Puzzle) -> PuzzleResult:
        print(f"\n=== {puzzle.name} ({puzzle.kind.name}) ===")
        print(puzzle.prompt)

        while puzzle.result == PuzzleResult.UNSOLVED:
            remaining = puzzle.max_attempts - puzzle.attempts
            guess = input(f"Your answer ({remaining} attempt(s) left): ").strip()
            result = puzzle.attempt(guess)
            hint = puzzle.hint()

            if result == PuzzleResult.SOLVED:
                print("Correct!")
            elif result == PuzzleResult.FAILED:
                print(f"Failed. The answer was: {puzzle.answer}")
            else:
                print("Wrong." + (f" Hint: {hint}" if hint else ""))

        return puzzle.result
