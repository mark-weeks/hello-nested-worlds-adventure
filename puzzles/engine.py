# puzzles/engine.py

import copy
import random
from typing import List

from multiverse.node import SpatialNode
from puzzles.data import BIOME_CLUES, DEFAULT_POOL, LEVEL_POOLS
from puzzles.types import Puzzle, PuzzleKind, PuzzleResult


# ── Dynamic puzzle generators (use node property values) ───────────────────

def _make_region_lock(props: dict) -> Puzzle:
    danger = props.get("danger_level", 5)
    code = str(danger * 2)
    return Puzzle(
        name="The Danger Gate",
        kind=PuzzleKind.LOCK,
        prompt="The security barrier requires the emergency multiplier code. Threat level doubled grants access.",
        answer=code,
        hints=[f"The danger level here is {danger}.", f"Multiply {danger} by 2."],
        max_attempts=5,
    )


def _make_universe_logic(props: dict) -> Puzzle:
    ratio = props.get("dark_matter_ratio", 0.27)
    pct = round((1.0 - ratio) * 100)
    return Puzzle(
        name="The Dark Matter Fraction",
        kind=PuzzleKind.LOGIC,
        prompt=f"This universe has a dark matter ratio of {ratio}. What whole percentage of its content is NOT dark matter?",
        answer=str(pct),
        hints=[f"Subtract {round(ratio * 100)}% from 100%.", f"100 - {round(ratio * 100)} = {pct}"],
    )


def _make_planet_riddle(props: dict) -> Puzzle:
    biome = props.get("biome", "temperate")
    prompt, answer = BIOME_CLUES.get(
        biome,
        (f"Name the biome that covers this world: {biome}.", biome),
    )
    return Puzzle(
        name=f"The {biome.title()} World",
        kind=PuzzleKind.RIDDLE,
        prompt=prompt,
        answer=answer,
        hints=[f"Think about the climate of a {biome} environment.", "The answer is a single biome type."],
    )


# ── Puzzle selector ────────────────────────────────────────────────────────

def _make_puzzle_for_node(node: SpatialNode, rng: random.Random) -> Puzzle:
    """Select or generate a level-appropriate puzzle for the given node."""
    level = node.level
    props = node.properties

    if level == "Region":
        return _make_region_lock(props)

    if level == "Universe":
        return _make_universe_logic(props)

    if level == "Planet":
        return _make_planet_riddle(props)

    pool = LEVEL_POOLS.get(level, DEFAULT_POOL)
    return copy.deepcopy(rng.choice(pool))


# ── Engine ─────────────────────────────────────────────────────────────────

class PuzzleEngine:
    def __init__(self, seed: int = 0):
        self._rng = random.Random(seed)

    def attach_puzzles(self, root: SpatialNode) -> int:
        count = 0
        if "puzzle" not in root.properties:
            root.properties["puzzle"] = _make_puzzle_for_node(root, self._rng)
            count += 1
        for child in root.children:
            count += self.attach_puzzles(child)
        return count

    def collect_puzzles(self, root: SpatialNode) -> List[Puzzle]:
        results: List[Puzzle] = []
        p = root.properties.get("puzzle")
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
