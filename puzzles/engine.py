# puzzles/engine.py

import copy
import random
from typing import Callable, List

from multiverse.node import SpatialNode
from puzzles.data import (
    BIOME_CLUES, DEFAULT_POOL, GALAXY_SHAPE_CLUES,
    LEVEL_POOLS, PARTICLE_TYPE_CLUES,
)
from puzzles.types import Puzzle, PuzzleKind, PuzzleResult


# ── Dynamic puzzle generators (use node property values) ───────────────────

def _make_multiverse_anagram(props: dict) -> Puzzle:
    theme = props.get("theme", "entropy")
    scrambled = "".join(sorted(theme.upper()))
    return Puzzle(
        name="The Theme Anagram",
        kind=PuzzleKind.ANAGRAM,
        prompt=(
            f"Five themes shape my fold: entropy, expansion, paradox, "
            f"recursion, stillness. Mine, scrambled: {scrambled}. Name it."
        ),
        answer=theme,
        hints=[f"It begins with '{theme[0]}'.",
               f"It has {len(theme)} letters."],
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


def _make_galaxy_riddle(props: dict) -> Puzzle:
    shape = props.get("shape", "spiral")
    prompt, answer = GALAXY_SHAPE_CLUES.get(
        shape,
        (f"Name the form this galaxy takes: {shape}.", shape),
    )
    return Puzzle(
        name=f"The {shape.title()} Form",
        kind=PuzzleKind.RIDDLE,
        prompt=prompt,
        answer=answer,
        hints=["The answer is a single shape word.",
               f"It has {len(shape)} letters."],
    )


def _make_planetary_system_logic(props: dict) -> Puzzle:
    count = int(props.get("planet_count", 4))
    half = count // 2
    return Puzzle(
        name="The Halved Orbit",
        kind=PuzzleKind.LOGIC,
        prompt=(
            f"I bind {count} world(s). If half were torn from orbit "
            f"(rounded down), how many would remain?"
        ),
        answer=str(half),
        hints=[f"Floor-divide {count} by 2.",
               f"{count} // 2 = {half}"],
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


def _make_room_navigation(props: dict) -> Puzzle:
    exits = int(props.get("exits", 2))
    answer_n = min(3, exits) if exits >= 1 else 1
    return Puzzle(
        name="The Widdershins Door",
        kind=PuzzleKind.NAVIGATION,
        prompt=(
            f"This chamber has {exits} exit(s). Walk widdershins from the "
            "first; the third leads home — or the last, if there are fewer "
            "than three. Which exit number?"
        ),
        answer=str(answer_n),
        hints=[f"There are {exits} doors.",
               f"min(3, {exits}) = {answer_n}"],
    )


def _make_object_logic(props: dict) -> Puzzle:
    weight = float(props.get("weight_kg", 1.0))
    quartered = round(weight / 4, 2)
    return Puzzle(
        name="The Quartered Mass",
        kind=PuzzleKind.LOGIC,
        prompt=(
            f"I weigh {weight} kg. Halve me, then halve me again. "
            "What is my mass, to two decimal places?"
        ),
        answer=str(quartered),
        hints=[f"Halving twice is dividing by 4.",
               f"{weight} / 4 = {quartered}"],
    )


def _make_molecule_logic(props: dict) -> Puzzle:
    bonds = int(props.get("bond_count", 4))
    electrons = bonds * 2
    return Puzzle(
        name="The Bond Count",
        kind=PuzzleKind.LOGIC,
        prompt=(
            f"I am held together by {bonds} covalent bond(s). Each bond "
            "shares two electrons. How many electrons in total are shared?"
        ),
        answer=str(electrons),
        hints=[f"Multiply {bonds} by 2.",
               f"{bonds} × 2 = {electrons}"],
    )


def _make_atom_logic(props: dict) -> Puzzle:
    z = int(props.get("atomic_number", 1))
    return Puzzle(
        name="The Neutral Count",
        kind=PuzzleKind.LOGIC,
        prompt=(
            f"My atomic number is {z}. In my neutral state, each electron "
            "balances a proton. How many electrons do I carry?"
        ),
        answer=str(z),
        hints=["Atomic number = proton count.",
               f"In a neutral atom, electron count = proton count = {z}."],
    )


def _make_subatomic_riddle(props: dict) -> Puzzle:
    ptype = props.get("particle_type", "proton")
    prompt, answer = PARTICLE_TYPE_CLUES.get(
        ptype,
        (f"Name the particle: {ptype}.", ptype),
    )
    return Puzzle(
        name=f"The {ptype.title()} Trace",
        kind=PuzzleKind.RIDDLE,
        prompt=prompt,
        answer=answer,
        hints=["The answer is a single particle name.",
               f"It has {len(ptype)} letters."],
    )


# ── Puzzle selector ────────────────────────────────────────────────────────

# Dispatch table: each level resolves to a generator that reads node
# properties and returns a fresh Puzzle. All 11 levels are covered; the
# static `LEVEL_POOLS` remain a fallback for unknown levels or nodes
# missing the expected properties (handled inside each generator's
# `props.get(...)` defaults).
_LEVEL_DYNAMIC: dict[str, Callable[[dict], Puzzle]] = {
    "Multiverse":        _make_multiverse_anagram,
    "Universe":          _make_universe_logic,
    "Galaxy":            _make_galaxy_riddle,
    "Planetary System":  _make_planetary_system_logic,
    "Planet":            _make_planet_riddle,
    "Region":            _make_region_lock,
    "Room":              _make_room_navigation,
    "Object":            _make_object_logic,
    "Molecule":          _make_molecule_logic,
    "Atom":              _make_atom_logic,
    "SubatomicParticle": _make_subatomic_riddle,
}


def _make_puzzle_for_node(node: SpatialNode, rng: random.Random) -> Puzzle:
    """Generate a level-appropriate puzzle for the given node.

    All 11 canonical levels have a dynamic generator. Unknown levels
    (e.g. test fixtures) fall back to the static `LEVEL_POOLS`.
    """
    gen = _LEVEL_DYNAMIC.get(node.level)
    if gen is not None:
        return gen(node.properties)

    pool = LEVEL_POOLS.get(node.level, DEFAULT_POOL)
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
