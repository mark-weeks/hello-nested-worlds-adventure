# puzzles/engine.py

import copy
import random
from typing import Callable, List

from multiverse.node import SpatialNode
from puzzles.data import DEFAULT_POOL, LEVEL_POOLS
from puzzles.generators import CANONICAL_LEVELS, build_puzzle, node_rng
from puzzles.types import Puzzle, PuzzleKind, PuzzleResult


# ── Puzzle selector ────────────────────────────────────────────────────────


def _make_puzzle_for_node(node: SpatialNode, rng: random.Random) -> Puzzle:
    """Generate a fair, non-leaking, node-unique puzzle for `node`.

    The eleven canonical scales are handled by `puzzles.generators.build_puzzle`,
    which seeds its own choice from the node's identity (so the puzzle is
    reproducible for co-op and differs from its neighbours), tunes difficulty to
    the scale, and never leaks the answer into the prompt, the hints, or the
    node's shipped /world properties. `rng` is accepted for backward
    compatibility but not used on the canonical path — selection is a pure
    function of node identity.

    A genuinely unknown level (e.g. a bare test fixture) has no word bank, so it
    falls back to the static `LEVEL_POOLS`, chosen deterministically from the
    node's own RNG rather than the caller's advancing one.
    """
    if node.level in CANONICAL_LEVELS:
        return build_puzzle(node)

    pool = LEVEL_POOLS.get(node.level, DEFAULT_POOL)
    return copy.deepcopy(node_rng(node).choice(pool))


# ── Engine ─────────────────────────────────────────────────────────────────

class PuzzleEngine:
    def __init__(self, seed: int = 0):
        self._rng = random.Random(seed)
        # Puzzles live in the ENGINE, keyed by node name — never inside
        # node.properties. A Puzzle stored on the node leaked its answer
        # everywhere properties surface: the CLI `look` dump, the /world
        # payload, and (worst) the consciousness system prompt, where the
        # node's own persona could be asked to reveal the solution.
        self._by_node: dict[str, Puzzle] = {}

    def attach_puzzles(self, root: SpatialNode) -> int:
        count = 0
        if root.name not in self._by_node:
            self._by_node[root.name] = _make_puzzle_for_node(root, self._rng)
            count += 1
        for child in root.children:
            count += self.attach_puzzles(child)
        return count

    def puzzle_for(self, node: SpatialNode) -> Puzzle | None:
        """The puzzle attached to exactly this node, if any."""
        return self._by_node.get(node.name)

    def collect_puzzles(self, root: SpatialNode) -> List[Puzzle]:
        results: List[Puzzle] = []
        p = self._by_node.get(root.name)
        if p:
            results.append(p)
        for child in root.children:
            results.extend(self.collect_puzzles(child))
        return results

    def run_puzzle(self, puzzle: Puzzle) -> PuzzleResult:
        print(f"\n=== {puzzle.name} ({puzzle.kind.name}) ===")
        print(puzzle.prompt)

        while puzzle.result == PuzzleResult.UNSOLVED:
            remaining = puzzle.max_attempts - puzzle.attempts
            try:
                guess = input(
                    f"Your answer ({remaining} attempt(s) left, or 'skip'): "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                # Walking away must never crash the session.
                print("\n(You step away, the puzzle unsolved.)")
                break
            if not guess:
                continue  # a stray Enter is not an attempt
            if guess.lower() in ("skip", "quit"):
                print("(You leave the puzzle for another traveler.)")
                break
            result = puzzle.attempt(guess)
            hint = puzzle.hint()

            if result == PuzzleResult.SOLVED:
                print("Correct!")
            elif result == PuzzleResult.FAILED:
                print(f"Failed. The answer was: {puzzle.answer}")
            else:
                print("Wrong." + (f" Hint: {hint}" if hint else ""))

        return puzzle.result
