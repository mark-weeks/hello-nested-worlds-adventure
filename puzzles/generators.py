# puzzles/generators.py
#
# Per-node puzzle generation for the eleven canonical scales.
#
# Design goals (see docs/design/game-design.md and the pre-beta puzzle review):
#
#   * Non-trivial. The answer is never printed in the prompt, never spelled out
#     in a hint, and never a bare value the node already ships in its /world
#     properties. Anagrams and Caesar ciphers hide the answer behind a
#     transform the player must reverse; sequences hide it behind a rule the
#     player must infer.
#   * Fair, never a wall. Every puzzle carries graduated hints (theme → shape →
#     first letter), released one per wrong attempt, so a stuck player is always
#     guided toward the answer without being handed it. Harder scales get MORE
#     attempts and an extra hint, not fewer.
#   * A difficulty curve. Players descend from the Multiverse to the subatomic,
#     so difficulty rises with depth: short words / small shifts / gentle rules
#     up top, longer words / larger shifts / trickier rules at the bottom.
#   * Per-node unique. Selection is seeded from the node's own identity, so each
#     node gets its own reproducible puzzle instead of every Room re-serving the
#     same three. Reproducible = co-op safe: everyone standing on a node sees
#     the same puzzle, and a rebuilt world regenerates it identically.
#
# The generator is a pure function of (node identity, node properties). It does
# not touch the network or the RNG the caller happens to hold — it derives its
# own deterministic RNG from the node name.
from __future__ import annotations

import copy
import hashlib
import random
import re
from typing import Callable

from multiverse.node import SpatialNode
from puzzles.data import LEVEL_POOLS
from puzzles.types import Puzzle, PuzzleKind


# ── Difficulty tiers ─────────────────────────────────────────────────────────
# One integer per scale, rising with depth. Drives word length, the cipher
# shift range, the numeric-sequence rules offered, attempts, and hint count.

LEVEL_DIFFICULTY: dict[str, int] = {
    "Multiverse":        1,
    "Universe":          1,
    "Galaxy":            1,
    "Planetary System":  2,
    "Planet":            2,
    "Region":            2,
    "Room":              3,
    "Object":            3,
    "Molecule":          3,
    "Atom":              4,
    "SubatomicParticle": 4,
}

# Attempts scale with difficulty so a harder puzzle isn't also a stingier one.
_ATTEMPTS_BY_DIFFICULTY = {1: 3, 2: 4, 3: 4, 4: 5}


# ── Scale-themed word banks ──────────────────────────────────────────────────
# Concept words for each scale, used by the anagram and cipher families. They
# are *concepts* evocative of the scale, deliberately NOT the enumerated values
# the world generator stores as node properties (theme, biome, shape,
# element, particle_type, …) — and any word that does happen to collide with a
# given node's properties is filtered out at selection time, so the answer can
# never be read straight out of the /world payload.

_WORD_BANKS: dict[str, list[str]] = {
    "Multiverse": [
        "cosmos", "origin", "genesis", "infinity", "expanse", "manifold",
        "fractal", "aether", "continuum", "abyss", "singularity", "unity",
    ],
    "Universe": [
        "gravity", "vacuum", "matter", "energy", "physics", "quantum",
        "stellar", "cosmic", "constant", "spacetime", "inertia", "radiation",
    ],
    "Galaxy": [
        "nebula", "quasar", "pulsar", "cluster", "corona", "stardust",
        "radiance", "eclipse", "supernova", "vortex", "halo", "filament",
    ],
    "Planetary System": [
        "eclipse", "solstice", "meridian", "aphelion", "satellite", "comet",
        "perigee", "celestial", "orbit", "resonance", "transit", "libration",
    ],
    "Planet": [
        "horizon", "glacier", "canyon", "monsoon", "aurora", "erosion",
        "sediment", "equator", "plateau", "estuary", "savanna", "crater",
    ],
    "Region": [
        "frontier", "outpost", "ravine", "citadel", "expanse", "wilds",
        "borderland", "escarpment", "marshland", "highland", "clearing",
        "hinterland",
    ],
    "Room": [
        "chamber", "lantern", "threshold", "alcove", "corridor", "mosaic",
        "archway", "sanctum", "cloister", "vestibule", "rafters", "hearth",
    ],
    "Object": [
        "artifact", "mechanism", "obsidian", "filament", "lattice", "pendant",
        "talisman", "engraving", "cogwork", "inlay", "reliquary", "ornament",
    ],
    "Molecule": [
        "covalent", "isotope", "polymer", "catalyst", "solvent", "reagent",
        "valence", "hydroxyl", "compound", "chirality", "monomer", "enzyme",
    ],
    "Atom": [
        "electron", "nucleus", "orbital", "neutron", "proton", "valence",
        "fission", "shielding", "isotope", "spectrum", "ionize", "quanta",
    ],
    "SubatomicParticle": [
        "neutrino", "positron", "graviton", "fermion", "lepton", "hadron",
        "photon", "boson", "gluon", "meson", "antiquark", "spinor",
    ],
}

# A short noun phrase per scale, used to frame the first (conceptual) hint
# without naming the answer.
_THEME_LABEL: dict[str, str] = {
    "Multiverse":        "a cosmic concept",
    "Universe":          "a term from physics",
    "Galaxy":            "something seen among the stars",
    "Planetary System":  "a term of orbital mechanics",
    "Planet":            "a feature of a world's surface or sky",
    "Region":            "a word for wild or bordered land",
    "Room":              "a part of an interior space",
    "Object":            "a made or found thing",
    "Molecule":          "a term from chemistry",
    "Atom":              "an atomic term",
    "SubatomicParticle": "a particle-physics term",
}


# ── Deterministic per-node RNG ───────────────────────────────────────────────

def node_rng(node: SpatialNode) -> random.Random:
    """A random.Random seeded from the node's identity.

    Keyed on the node NAME (unique within a world and stable across rebuilds),
    not on properties or traversal order, so the puzzle is a pure function of
    which node this is — reproducible for co-op and unchanged when the server
    rebuilds the tree, yet different from its neighbours.
    """
    digest = hashlib.sha256(f"{node.level}:{node.name}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _property_values(node: SpatialNode) -> set[str]:
    """Lower-cased string forms of the node's own property values, so a chosen
    answer can be screened against everything the /world payload reveals."""
    out: set[str] = set()
    for v in node.properties.values():
        if isinstance(v, Puzzle):  # the attached puzzle itself, once set
            continue
        out.add(str(v).strip().lower())
    return out


def _pick_word(node: SpatialNode, rng: random.Random) -> str:
    """Choose a themed word for this node that does NOT appear in its shipped
    properties or in the node's own name (both surface in the /world payload and
    the prompt, so either would hand the answer away)."""
    bank = _WORD_BANKS.get(node.level, [])
    forbidden = _property_values(node)
    name = node.name.lower()
    candidates = [
        w for w in bank
        if w.lower() not in forbidden and w.lower() not in name
    ] or [w for w in bank if w.lower() not in name] or bank
    return rng.choice(candidates)


def _answer_leaks(puzzle: Puzzle, node: SpatialNode) -> bool:
    """True if the answer is recoverable without solving — as a standalone token
    in the prompt or any hint (e.g. the node name happened to contain it, or a
    numeric answer collided with the name's index), or as a shipped property."""
    ans = puzzle.answer.lower()

    def toks(s: str) -> set[str]:
        return set(re.findall(r"[a-z0-9.]+", s.lower()))

    if ans in _property_values(node):
        return True
    if ans in toks(puzzle.prompt):
        return True
    return any(ans in toks(h) for h in puzzle.hints)


# ── Puzzle families ──────────────────────────────────────────────────────────
# Each returns a fully-formed Puzzle. The answer is always the plaintext concept
# or the computed number — never printed in the prompt.

def _make_anagram(node: SpatialNode, rng: random.Random, difficulty: int) -> Puzzle:
    word = _pick_word(node, rng)
    letters = list(word.upper())
    # Scramble to something that is not the original spelling.
    for _ in range(12):
        rng.shuffle(letters)
        if "".join(letters).lower() != word:
            break
    scrambled = "".join(letters)
    hints = [
        f"It is {_THEME_LABEL.get(node.level, 'a word')}.",
        f"It has {len(word)} letters.",
        f"It begins with '{word[0]}'.",
    ]
    if difficulty >= 3:
        # Harder scales get an extra, later giveaway so the puzzle stays fair.
        hints.append(f"The first two letters are '{word[0]}' and '{word[1]}'.")
    return Puzzle(
        name=f"The Jumbled {node.level} Word",
        kind=PuzzleKind.ANAGRAM,
        prompt=(f"Fragments recovered at {node.name} spell {_THEME_LABEL.get(node.level, 'a word')}, "
                f"their order lost: {scrambled}. Restore the word."),
        answer=word,
        hints=hints,
        max_attempts=_ATTEMPTS_BY_DIFFICULTY[difficulty],
    )


def _make_cipher(node: SpatialNode, rng: random.Random, difficulty: int) -> Puzzle:
    word = _pick_word(node, rng)
    # Larger shift range with depth; never 0 (that would print the plaintext).
    max_shift = {1: 3, 2: 5, 3: 7, 4: 9}[difficulty]
    shift = rng.randint(1, max_shift)
    cipher = "".join(
        chr((ord(c) - ord("a") + shift) % 26 + ord("a")) for c in word
    ).upper()
    hints = [
        f"It is {_THEME_LABEL.get(node.level, 'a word')}, written in a shifted alphabet.",
        f"Each letter was moved forward by {shift}; move it back by {shift}.",
        f"It begins with '{word[0]}'.",
    ]
    if difficulty >= 3:
        hints.append(f"It has {len(word)} letters and ends with '{word[-1]}'.")
    return Puzzle(
        name=f"The {node.level} Inscription",
        kind=PuzzleKind.CIPHER,
        prompt=(f"An inscription at {node.name}, each letter turned forward through "
                f"the alphabet: {cipher}. Read what it says."),
        answer=word,
        hints=hints,
        max_attempts=_ATTEMPTS_BY_DIFFICULTY[difficulty],
    )


def _make_sequence(node: SpatialNode, rng: random.Random, difficulty: int) -> Puzzle:
    """A numeric pattern whose next term must be inferred. The answer (the next
    term) is never shown, and the rule is only hinted, not stated up front."""
    if difficulty <= 1:
        # Gentle: arithmetic step or simple doubling.
        if rng.random() < 0.5:
            start = rng.randint(1, 6)
            step = rng.randint(2, 5)
            seq = [start + step * i for i in range(4)]
            nxt = seq[-1] + step
            rule_hint = "The gap between terms never changes."
            last_hint = f"Add {step} to {seq[-1]}."
        else:
            start = rng.randint(1, 3)
            seq = [start * (2 ** i) for i in range(4)]
            nxt = seq[-1] * 2
            rule_hint = "Each term is a multiple of the one before it."
            last_hint = f"Double {seq[-1]}."
    elif difficulty <= 3:
        # Medium: geometric with a larger ratio, or squares.
        if rng.random() < 0.5:
            start = rng.randint(1, 4)
            ratio = rng.randint(2, 3)
            seq = [start * (ratio ** i) for i in range(4)]
            nxt = seq[-1] * ratio
            rule_hint = "Each term grows by the same factor."
            last_hint = f"Multiply {seq[-1]} by {ratio}."
        else:
            base = rng.randint(1, 4)
            seq = [(base + i) ** 2 for i in range(4)]
            nxt = (base + 4) ** 2
            rule_hint = "These are perfect squares of consecutive numbers."
            last_hint = f"Square {base + 4}."
    else:
        # Hard: Fibonacci-like additive, or triangular numbers.
        if rng.random() < 0.5:
            a, b = rng.randint(1, 4), rng.randint(1, 5)
            seq = [a, b]
            while len(seq) < 5:
                seq.append(seq[-1] + seq[-2])
            nxt = seq[-1] + seq[-2]
            rule_hint = "Each term is built from the two that came before it."
            last_hint = f"Add {seq[-2]} and {seq[-1]}."
        else:
            start = rng.randint(1, 4)
            seq, total = [], 0
            n = start
            for _ in range(5):
                total += n
                seq.append(total)
                n += 1
            nxt = total + n
            rule_hint = "The running total climbs by one more each step."
            last_hint = f"Add {n} to {seq[-1]}."
    shown = ", ".join(str(x) for x in seq)
    hints = [rule_hint, "Work out the rule from term to term, then extend it once.", last_hint]
    return Puzzle(
        name=f"The {node.level} Progression",
        kind=PuzzleKind.PATTERN,
        prompt=(f"A pattern pulses through {node.name}: {shown}, ? "
                f"What number comes next?"),
        answer=str(nxt),
        hints=hints,
        max_attempts=_ATTEMPTS_BY_DIFFICULTY[difficulty],
    )


def _clean_pool_puzzles(level: str, node: SpatialNode) -> list[Puzzle]:
    """Static-pool puzzles for `level` that are safe to reuse: the answer must
    not appear in the prompt or any hint, and must not be a value the node
    already ships in its properties."""
    forbidden = _property_values(node)
    out: list[Puzzle] = []
    for p in LEVEL_POOLS.get(level, []):
        a = p.answer.lower()
        if a in p.prompt.lower():
            continue
        if any(a in h.lower() for h in p.hints):
            continue
        if a in forbidden:
            continue
        out.append(p)
    return out


def _make_riddle(node: SpatialNode, rng: random.Random, difficulty: int) -> Puzzle | None:
    """Reuse a hand-written static-pool riddle/cipher/pattern for this scale,
    de-leaked and selected per node. Returns None if the pool has nothing
    usable, so the caller can fall back to a generated family."""
    usable = _clean_pool_puzzles(node.level, node)
    if not usable:
        return None
    chosen = copy.deepcopy(rng.choice(usable))
    # Give it the same fair attempt budget as generated puzzles at this tier.
    chosen.max_attempts = max(chosen.max_attempts, _ATTEMPTS_BY_DIFFICULTY[difficulty])
    return chosen


# ── Selector ─────────────────────────────────────────────────────────────────

# Which families each difficulty tier draws from, and their relative weights.
# Ciphers only appear once there's a little depth; deeper scales lean on the
# harder transforms. Riddles are offered everywhere they exist.
_FAMILY_WEIGHTS: dict[int, list[tuple[str, int]]] = {
    1: [("anagram", 3), ("sequence", 2), ("riddle", 3)],
    2: [("anagram", 3), ("cipher", 2), ("sequence", 2), ("riddle", 3)],
    3: [("anagram", 2), ("cipher", 3), ("sequence", 3), ("riddle", 2)],
    4: [("anagram", 2), ("cipher", 4), ("sequence", 3), ("riddle", 2)],
}

_FAMILY_FN: dict[str, Callable[[SpatialNode, random.Random, int], Puzzle | None]] = {
    "anagram":  _make_anagram,
    "cipher":   _make_cipher,
    "sequence": _make_sequence,
    "riddle":   _make_riddle,
}


def build_puzzle(node: SpatialNode) -> Puzzle:
    """Generate this node's puzzle: fair, non-leaking, difficulty-tuned to the
    scale, and unique to the node. Deterministic in the node's identity."""
    rng = node_rng(node)
    difficulty = LEVEL_DIFFICULTY.get(node.level, 2)
    families = list(_FAMILY_WEIGHTS.get(difficulty, _FAMILY_WEIGHTS[2]))

    # Try families in a node-seeded weighted-random order; the first that yields
    # a non-leaking puzzle wins. A family can decline (`riddle` on an empty/leaky
    # pool) or be rejected here if its answer happens to surface in the prompt —
    # e.g. the node name coincides with a numeric sequence answer.
    names = [n for n, _ in families]
    weights = [w for _, w in families]
    while names:
        pick = rng.choices(range(len(names)), weights=weights, k=1)[0]
        family = names.pop(pick)
        weights.pop(pick)
        puzzle = _FAMILY_FN[family](node, rng, difficulty)
        if puzzle is not None and not _answer_leaks(puzzle, node):
            return puzzle

    # Every scale has a word bank and `_pick_word` already excludes any word in
    # the node's name or properties, so an anagram of a picked word cannot leak
    # (the answer appears only scrambled). Guaranteed-clean fallback.
    return _make_anagram(node, rng, difficulty)
