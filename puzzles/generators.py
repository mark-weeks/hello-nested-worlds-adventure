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
#     guided toward the answer without being handed it. Harder puzzles get MORE
#     attempts and an extra hint, not fewer.
#   * Difficulty is per-node, not per-scale. Traversal is non-linear — players
#     drop in at any node and move up or down, exploring continuously with no
#     "reach the bottom" goal — so difficulty is drawn per node and spread across
#     the full range at every scale, rather than rising with depth. Scale sets a
#     puzzle's flavour (its themed vocabulary), never how hard it is.
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


# ── Difficulty: a property of the puzzle, not the scale ──────────────────────
# Traversal is non-linear — players drop in at any node and move up or down,
# with no "reach the bottom" goal, so continuous exploration is the point.
# Difficulty therefore is NOT a function of depth (a depth curve would wall a
# player who drops into a deep scale, make challenge yo-yo as they wander up and
# down, and smuggle in a false "reach the subatomic and you're done" goal).
# Instead each node draws its own difficulty (1 gentle … 4 hard), seeded from
# its identity and spread across the whole range at every scale. Scale still
# shapes a puzzle's flavour — its themed vocabulary and register — but never
# makes one scale harder than another. Difficulty drives the cipher shift range,
# the numeric-sequence rules offered, the number of attempts, and the hint count.

CANONICAL_LEVELS: tuple[str, ...] = (
    "Multiverse", "Universe", "Galaxy", "Planetary System", "Planet",
    "Region", "Room", "Object", "Molecule", "Atom", "SubatomicParticle",
)

_MAX_DIFFICULTY = 4

# Attempts scale with difficulty so a harder puzzle isn't also a stingier one.
_ATTEMPTS_BY_DIFFICULTY = {1: 3, 2: 4, 3: 4, 4: 5}


def node_difficulty(node: SpatialNode) -> int:
    """This node's puzzle difficulty (1..4).

    Seeded from the node's identity — so it is stable, co-op-safe, and
    reproducible across world rebuilds — and deliberately independent of the
    node's scale, so any given scale carries the full spread of difficulties.
    """
    digest = hashlib.sha256(
        f"difficulty:{node.level}:{node.name}".encode("utf-8")
    ).digest()
    return 1 + digest[0] % _MAX_DIFFICULTY


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

# Second-generation vocabulary: each level's bank grew from 12 to 30 so a
# player who has solved a few puzzles hasn't memorized the level's answer
# key (measured before this expansion: 141 distinct answers across a full
# 3,174-node world — "superposition" answered 410 nodes).
_WORD_BANKS["Multiverse"] += [
    "eternity", "recursion", "membrane", "totality", "emergence", "plenum",
    "lattice", "threshold", "symmetry", "archetype", "confluence", "prism",
    "resonance", "substrate", "horizon", "myriad", "nexus", "immanence",
]
_WORD_BANKS["Universe"] += [
    "entropy", "photon", "redshift", "curvature", "plasma", "graviton",
    "momentum", "particle", "fusion", "velocity", "expansion", "spectrum",
    "isotropy", "relativity", "neutrino", "horizon", "quark", "field",
]
_WORD_BANKS["Galaxy"] += [
    "spiral", "barred", "magnetar", "cepheid", "parallax", "accretion",
    "starlight", "redgiant", "blazar", "darklane", "luminosity", "spur",
    "globular", "voidward", "tidal", "bulge", "perseus", "cartwheel",
]
_WORD_BANKS["Planetary System"] += [
    "ecliptic", "azimuth", "perihelion", "syzygy", "conjunction", "kepler",
    "lagrange", "barycenter", "occultation", "retrograde", "apogee", "node",
    "epicycle", "almanac", "gibbous", "waning", "zenith", "nadir",
]
_WORD_BANKS["Planet"] += [
    "tundra", "caldera", "isthmus", "archipelago", "permafrost", "delta",
    "steppe", "fumarole", "geyser", "moraine", "atoll", "badlands",
    "tectonic", "monolith", "silt", "brine", "downpour", "thermals",
]
_WORD_BANKS["Region"] += [
    "foothills", "crossroads", "palisade", "bulwark", "heath", "fenland",
    "bramble", "hollow", "ridgeline", "waystation", "cairn", "thicket",
    "boundary", "overlook", "backcountry", "sprawl", "enclave", "reaches",
]
_WORD_BANKS["Room"] += [
    "balustrade", "cornice", "pantry", "scullery", "atrium", "gallery",
    "wainscot", "transom", "rotunda", "annex", "landing", "parapet",
    "casement", "lintel", "colonnade", "antechamber", "stairwell", "niche",
]
_WORD_BANKS["Object"] += [
    "astrolabe", "sundial", "bellows", "crucible", "gimbal", "sextant",
    "tumbler", "escapement", "amulet", "phylactery", "stylus", "tessera",
    "orrery", "windlass", "hasp", "ferrule", "diadem", "censer",
]
_WORD_BANKS["Molecule"] += [
    "benzene", "peptide", "ligand", "dimer", "aldehyde", "ester",
    "titration", "colloid", "emulsion", "sublimate", "distill", "anhydride",
    "racemic", "zwitterion", "micelle", "lipid", "buffer", "adduct",
]
_WORD_BANKS["Atom"] += [
    "cathode", "anode", "excited", "decay", "halflife", "lanthanide",
    "covalence", "photoelectric", "rydberg", "balmer", "shell", "dopant",
    "scintilla", "tracer", "moderator", "capture", "emission", "bombard",
]
_WORD_BANKS["SubatomicParticle"] += [
    "chirality", "strangeness", "tachyon", "axion", "parity", "isospin",
    "muon", "tauon", "wavefunction", "entangle", "tunneling", "condensate",
    "annihilate", "virtual", "colorcharge", "helicity", "soliton", "braneworld",
]

# Fused-compound vocabulary for ciphers: two evocative parts joined into a
# word that has never been written before (~500 combinations per level).
# A cipher is decoded mechanically — shift each letter back — so the answer
# needn't be a dictionary word; it just has to be unambiguous. This is the
# task-15 name-synthesis treatment applied to the answer space.
_COMPOUND_A: dict[str, list[str]] = {
    "Multiverse":        ["void", "ever", "dream", "fold", "true", "deep", "first", "silent", "veiled", "primal", "hollow", "endless", "woven", "shining", "unborn", "quiet", "sunder", "twin", "far", "inner", "aether", "myriad"],
    "Universe":          ["dark", "light", "cold", "prime", "iron", "slow", "vast", "faint", "early", "late", "hidden", "bare", "burnt", "sharp", "still", "spent", "young", "heavy", "swift", "pale", "raw", "spun"],
    "Galaxy":            ["star", "dust", "arm", "core", "rim", "halo", "ember", "frost", "ash", "silver", "amber", "shade", "ghost", "wheel", "drift", "ring", "cinder", "glass", "night", "storm", "milk", "opal"],
    "Planetary System":  ["sun", "moon", "orbit", "ring", "tide", "dawn", "dusk", "belt", "twin", "wander", "iron", "ice", "gas", "storm", "far", "near", "swift", "still", "gold", "pale", "red", "blue"],
    "Planet":            ["salt", "stone", "rain", "cloud", "river", "ridge", "shore", "wind", "moss", "sand", "snow", "reef", "root", "ember", "fog", "clay", "tide", "leaf", "bone", "iron", "dew", "loam"],
    "Region":            ["mist", "thorn", "fen", "briar", "elder", "hound", "raven", "willow", "granite", "harrow", "winter", "summer", "black", "gray", "red", "lost", "last", "broken", "silent", "north", "outer", "deep"],
    "Room":              ["dust", "oak", "brass", "candle", "shadow", "velvet", "ivory", "cedar", "amber", "silver", "quiet", "cold", "warm", "old", "worn", "hidden", "locked", "long", "low", "high", "bare", "dim"],
    "Object":            ["clock", "key", "mirror", "chain", "blade", "coin", "lens", "bell", "cage", "knot", "seal", "hinge", "thread", "shard", "wax", "ink", "bone", "glass", "iron", "gold", "salt", "ash"],
    "Molecule":          ["chain", "ring", "bond", "twist", "branch", "helix", "sheet", "cage", "knot", "cross", "double", "triple", "long", "short", "left", "right", "open", "closed", "free", "fixed", "polar", "inert"],
    "Atom":              ["spin", "shell", "charge", "cloud", "core", "wave", "pulse", "flash", "ghost", "twin", "half", "whole", "bright", "faint", "bound", "free", "heavy", "light", "noble", "base", "keen", "raw"],
    "SubatomicParticle": ["flux", "phase", "spin", "wave", "field", "path", "pair", "loop", "knot", "sea", "foam", "veil", "point", "cloud", "drift", "flick", "ghost", "mirror", "shadow", "twin", "null", "prime"],
}
_COMPOUND_B: dict[str, list[str]] = {
    "Multiverse":        ["weave", "spire", "gate", "song", "root", "seam", "tide", "veil", "loom", "birth", "fold", "hush", "brink", "sleep", "wake", "turn", "pulse", "bloom", "rift", "call", "well", "arc"],
    "Universe":          ["field", "wake", "shear", "burst", "well", "arc", "flow", "pull", "spin", "drift", "glow", "seam", "storm", "veil", "husk", "span", "birth", "fall", "wind", "knot", "beam", "web"],
    "Galaxy":            ["reach", "spiral", "shoal", "veil", "crown", "spur", "lane", "gyre", "bloom", "swarm", "tail", "song", "field", "gate", "well", "seam", "coil", "spray", "wake", "fall", "arc", "run"],
    "Planetary System":  ["path", "dance", "chord", "clock", "sweep", "lock", "step", "chase", "veil", "song", "wheel", "loom", "arc", "fall", "rise", "count", "pull", "watch", "ring", "drift", "tilt", "turn"],
    "Planet":            ["fall", "reach", "spine", "field", "brow", "flats", "run", "wash", "gate", "break", "bed", "line", "song", "veil", "crest", "hollow", "sweep", "burn", "drift", "mouth", "step", "vein"],
    "Region":            ["march", "watch", "gate", "moor", "vale", "cross", "ward", "wood", "fall", "reach", "hold", "run", "song", "path", "field", "stone", "mark", "brook", "rise", "shade", "walk", "end"],
    "Room":              ["nook", "beam", "board", "step", "shelf", "sill", "post", "door", "vault", "frame", "panel", "floor", "hook", "seat", "arch", "grate", "ledge", "stair", "well", "screen", "latch", "rail"],
    "Object":            ["work", "ward", "wright", "charm", "guard", "twist", "face", "spine", "tooth", "heart", "eye", "hand", "tongue", "wing", "coil", "crown", "stem", "throat", "root", "edge", "core", "loop"],
    "Molecule":          ["link", "fold", "graft", "weave", "mesh", "seam", "join", "lock", "coil", "loop", "bridge", "arm", "site", "shift", "swap", "bend", "snap", "form", "pair", "stack", "path", "gate"],
    "Atom":              ["leap", "state", "well", "trap", "gap", "line", "band", "step", "jump", "glow", "song", "dance", "shift", "hum", "count", "ring", "veil", "kick", "spark", "path", "shed", "hold"],
    "SubatomicParticle": ["state", "trace", "jitter", "dance", "swap", "burst", "echo", "skip", "blink", "shiver", "twist", "hum", "leap", "split", "merge", "flip", "chase", "knot", "song", "drift", "veil", "spin"],
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


def _pick_cipher_word(node: SpatialNode, rng: random.Random,
                      difficulty: int) -> tuple[str, bool]:
    """A cipher answer: usually a fused compound this world has never
    written before ("emberveil", "spinshiver"), keeping the decoded text a
    surprise even to a player who knows the level's vocabulary. Gentle
    (difficulty-1) ciphers stay single dictionary words. Returns
    (word, is_compound)."""
    if difficulty >= 2 and rng.random() < 0.75:
        a_bank = _COMPOUND_A.get(node.level)
        b_bank = _COMPOUND_B.get(node.level)
        if a_bank and b_bank:
            forbidden = _property_values(node)
            name = node.name.lower()
            for _ in range(8):
                word = rng.choice(a_bank) + rng.choice(b_bank)
                if word not in forbidden and word not in name:
                    return word, True
    return _pick_word(node, rng), False


# Prompt dressing: one deterministic sentence drawn from what the node IS —
# its atmosphere, its condition, its danger — so a corrupted danger-9 vault
# frames its puzzle differently than a warded meadow. Never contains the
# answer (build_puzzle re-screens after dressing and strips it on collision).
_DRESS_KEYS = ("air", "weather", "sky", "glow", "membrane", "dust",
               "light_temper", "lighting", "terrain", "biome",
               "tendency", "surface", "geometry", "material", "shape")


def _dress(node: SpatialNode, rng: random.Random) -> str:
    props = node.properties or {}
    clauses: list[str] = []
    for key in _DRESS_KEYS:
        if key in props and isinstance(props[key], str):
            clauses.append(f"The {key.replace('_', ' ')} here is {props[key]}.")
    danger = props.get("danger_level")
    if isinstance(danger, int) and danger >= 6 and not props.get("stabilized"):
        clauses.append(f"Danger presses at {danger} of 10; work quickly.")
    if props.get("condition") in ("damaged", "corrupted"):
        clauses.append(f"The {props['condition']} matter distorts the marks.")
    if props.get("stabilized"):
        clauses.append("A recent stillness holds; the signs sit clear.")
    if not clauses:
        return ""
    return rng.choice(clauses)


def _answer_leaks(puzzle: Puzzle, node: SpatialNode) -> bool:
    """True if the answer is recoverable without solving — as a standalone token
    in the prompt or any hint (e.g. the node name happened to contain it, or a
    numeric answer collided with the name's index), or as a shipped property."""
    ans = " ".join(puzzle.answer.lower().split())

    def toks(s: str) -> set[str]:
        return set(re.findall(r"[a-z0-9.]+", s.lower()))

    def contains_phrase(s: str) -> bool:
        return ans in " ".join(s.lower().split())

    if ans in _property_values(node):
        return True
    # Token membership is correct for single-mark answers, but a living name
    # is deliberately a multi-word phrase. Keep that crown-jewel invariant
    # mechanical too: future fiction must not be able to print a Keeper answer
    # verbatim merely because no individual token equals the whole phrase.
    if " " in ans and (
        contains_phrase(puzzle.prompt)
        or any(contains_phrase(hint) for hint in puzzle.hints)
    ):
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
        difficulty=difficulty,
    )


def _make_cipher(node: SpatialNode, rng: random.Random, difficulty: int) -> Puzzle:
    word, is_compound = _pick_cipher_word(node, rng, difficulty)
    # Larger shift range with depth; never 0 (that would print the plaintext).
    max_shift = {1: 3, 2: 5, 3: 7, 4: 9}[difficulty]
    shift = rng.randint(1, max_shift)
    cipher = "".join(
        chr((ord(c) - ord("a") + shift) % 26 + ord("a")) for c in word
    ).upper()
    theme = ("two words of this scale, fused into one"
             if is_compound else _THEME_LABEL.get(node.level, "a word"))
    hints = [
        f"It is {theme}, written in a shifted alphabet.",
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
        difficulty=difficulty,
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
        difficulty=difficulty,
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


# Keys a LOCK may listen for: generated Region categoricals that the
# property overlay never mutates, so the answer is stable for the life of
# the world (a danger_level key would change under the players mid-session).
_LOCK_KEY_CANDIDATES = ("weather", "terrain", "faction_control")


# Generated categorical readings that the property overlay never rewrites.
# The two world-reading families below deliberately use only this allow-list:
# their answers must remain stable after players act on a node.  Mutable keys
# such as stability, condition, danger_level, and stabilized do not belong
# here, even when their birth values are strings.
_ANCESTRAL_READING_KEYS: dict[str, tuple[str, ...]] = {
    "Multiverse": ("theme", "membrane"),
    "Universe": ("laws_of_physics", "dominant_faction", "light_temper"),
    "Galaxy": ("shape", "dust"),
    "Planetary System": ("star_type",),
    "Planet": ("biome", "sky"),
    "Region": ("terrain", "faction_control", "weather"),
    "Room": ("lighting", "air"),
    "Object": ("material", "surface"),
    "Molecule": ("compound_type", "geometry"),
    "Atom": ("element", "glow"),
}


def _ancestors(node: SpatialNode) -> list[SpatialNode]:
    """The node's enclosing places, ordered outermost to innermost."""
    out: list[SpatialNode] = []
    current = node.parent
    while current is not None:
        out.append(current)
        current = current.parent
    out.reverse()
    return out


def _living_name(node: SpatialNode) -> str:
    """A node's human-readable name without its path-identity suffix."""
    base, separator, suffix = node.name.rpartition("-")
    if separator and suffix.isdigit():
        return base.strip().lower()
    return node.name.strip().lower()


def _edge_marks(value: str) -> str:
    """First and last alphanumeric marks of a categorical reading."""
    letters = re.findall(r"[a-z0-9]", value.lower())
    return "" if not letters else letters[0] + letters[-1]


# ── KEEPER WITNESS: readable names become gameplay ──────────────────────────
# A node's three-word living name is not decorative filler: it is a memorable
# landmark. Ancestor names deliberately remain visible in both clients so the
# world stays orientable. Gentle witnesses reward recognizing one landmark;
# hard witnesses preserve that visibility but compose a new phrase from two or
# three of them, so a 3- or 4-star answer is never UI text that can be copied
# whole. The family uses only the ancestor chain, which the materialized-store
# resolver reconstructs for every node, so a full tree and a directly resolved
# node always grow the same puzzle.

_NAME_WORD_ORDINALS = ("first", "second", "third", "fourth", "fifth")


def _keeper_mark(node: SpatialNode, rng: random.Random) -> tuple[str, str] | None:
    """Return one living-name word and its human-readable ordinal."""
    words = _living_name(node).split()
    if not words:
        return None
    index = rng.randrange(len(words))
    if len(words) == 1:
        ordinal = "only"
    elif index < len(_NAME_WORD_ORDINALS):
        ordinal = _NAME_WORD_ORDINALS[index]
    else:
        ordinal = f"word {index + 1}"
    return words[index], ordinal


def _make_keeper_witness(node: SpatialNode, rng: random.Random,
                         difficulty: int) -> Puzzle | None:
    ancestors = _ancestors(node)
    if not ancestors:
        return None
    nearby = ancestors[-min(3, len(ancestors)):]

    if difficulty <= 2:
        # One-star witnesses use the nearest enclosure; two-star witnesses can
        # ask the player to read as many as three folds outward.
        keeper = nearby[-1] if difficulty == 1 else nearby[
            rng.randrange(len(nearby))
        ]
        answer = _living_name(keeper)
        if not answer:
            return None
        folds = len(ancestors) - ancestors.index(keeper)
        fold_word = "fold" if folds == 1 else "folds"
        prompt = (
            f"{node.name} remembers a place that holds it. Climb "
            f"{folds} {fold_word} to its enclosing {keeper.level}. "
            "Return with that place's living name — the words "
            "before its lineage mark."
        )
        hints = [
            f"Travel outward until the scale reads {keeper.level}.",
            "Its living name is everything before the dash and digits.",
            f"The first word begins with '{answer[0]}'.",
        ]
    else:
        mark_count = 2 if difficulty == 3 else 3
        if len(nearby) < mark_count:
            return None
        keepers = sorted(
            rng.sample(nearby, mark_count),
            key=ancestors.index,
        )
        marks: list[str] = []
        readings: list[str] = []
        for keeper in keepers:
            mark = _keeper_mark(keeper, rng)
            if mark is None:
                return None
            word, ordinal = mark
            marks.append(word)
            readings.append(
                f"at the {keeper.level}, keep the {ordinal} word of its "
                "living name"
            )
        answer = " ".join(marks)
        route = "; then ".join(readings)
        prompt = (
            f"{node.name} is held by a constellation of keepers. Read "
            f"outward in outer-to-inner order: {route}. Speak those "
            f"{mark_count} words as one phrase."
        )
        hints = [
            "The ancestor tree keeps every landmark visible; read the named "
            "scales in the order given.",
            "Strip each dash and lineage digits before counting its words.",
            f"The first gathered word begins with '{answer[0]}'.",
        ]

    return Puzzle(
        name=f"The Keeper Witness of the {node.level}",
        kind=PuzzleKind.NAVIGATION,
        prompt=prompt,
        answer=answer,
        hints=hints,
        max_attempts=_ATTEMPTS_BY_DIFFICULTY[difficulty],
        difficulty=difficulty,
    )


# ── ANCESTRAL COMPASS: two scales held in mind ──────────────────────────────
# The compass is a small piece of multi-hop reasoning: read one immutable
# categorical at each of two enclosing scales, take the edge letters of each,
# and keep them in outer-to-inner order.  The four-letter result is compact to
# enter but can only be derived by engaging with this particular world's
# properties; it is not a reusable answer-key word.

def _make_ancestral_compass(node: SpatialNode, rng: random.Random,
                            difficulty: int) -> Puzzle | None:
    candidates: list[tuple[SpatialNode, str, str]] = []
    for holder in _ancestors(node):
        keys = [
            key for key in _ANCESTRAL_READING_KEYS.get(holder.level, ())
            if isinstance(holder.properties.get(key), str)
            and len(_edge_marks(holder.properties[key])) == 2
        ]
        if keys:
            key = keys[rng.randrange(len(keys))]
            candidates.append((holder, key, holder.properties[key]))
    if len(candidates) < 2:
        return None
    left_index, right_index = sorted(rng.sample(range(len(candidates)), 2))
    outer, outer_key, outer_value = candidates[left_index]
    inner, inner_key, inner_value = candidates[right_index]
    answer = _edge_marks(outer_value) + _edge_marks(inner_value)
    return Puzzle(
        name=f"The Ancestral Compass of the {node.level}",
        kind=PuzzleKind.LOGIC,
        prompt=(f"Two enclosing scales set the compass at {node.name}. At "
                f"the {outer.level}, read its {outer_key.replace('_', ' ')}; "
                "keep that reading's first and last letter. Then, at the "
                f"{inner.level}, do the same with its "
                f"{inner_key.replace('_', ' ')}. Join the four marks in "
                "that outer-to-inner order."),
        answer=answer,
        hints=[
            f"The first pair comes from the {outer.level}; the second from "
            f"the {inner.level}.",
            "Ignore spaces and punctuation; each reading contributes only "
            "its two edge letters.",
            f"The first mark is '{answer[0]}'.",
        ],
        max_attempts=_ATTEMPTS_BY_DIFFICULTY[difficulty],
        difficulty=difficulty,
    )


# ── ENFOLD: the nesting itself as puzzle content ─────────────────────────────
# The cosmic scales get the mirror of the LOCK. A LOCK makes you look UP
# ("the key is written in the place that holds you"); an ENFOLD makes you
# think about what a cosmic node IS — a container of containers — and
# about your own position inside the fold. Every answer derives from the
# node's NAME alone (its path suffix encodes its whole lineage), so the
# puzzle is a pure function of node identity like every other family, and
# solving one teaches the world's deepest structural secret: names are
# maps.

_ENFOLD_LEVELS = ("Multiverse", "Universe", "Galaxy", "Planetary System")

# Total scale count, mirrored from multiverse.generator.LEVELS (imported
# lazily below to keep this module free of a hard multiverse.generator
# dependency at import time).
_TOTAL_SCALES = 11

_ENFOLD_CHILD_WORD = {
    "Multiverse":       "universes",
    "Universe":         "galaxies",
    "Galaxy":           "systems",
    "Planetary System": "worlds",
}


# ── LINEAGE: the enfolding, traveled ─────────────────────────────────────────
# Deep nodes look UP through their whole fold. The answer is an acrostic
# sigil assembled from the enclosing scales — the first letters of the
# region's weather, the world's biome, the galaxy's shape — readable only
# by traveling your own lineage and holding three scales in mind at once.
# All three source keys are generated categoricals the overlay never
# mutates, so a sigil is stable for the life of the world; and every node
# (resolver-built included) carries its full parent chain, so the family
# is a pure function of node identity.

_LINEAGE_LEVELS = ("Object", "Molecule")
_LINEAGE_SOURCES = (            # (level, property, spoken label)
    ("Region", "weather", "the weather of the region that holds it"),
    ("Planet", "biome", "the biome of the world beneath that"),
    ("Galaxy", "shape", "the shape of the galaxy over everything"),
)


def _make_lineage(node: SpatialNode, rng: random.Random,
                  difficulty: int) -> Puzzle | None:
    ancestors: dict[str, SpatialNode] = {}
    n = node.parent
    while n is not None:
        ancestors[n.level] = n
        n = n.parent
    letters, labels = [], []
    for level, key, label in _LINEAGE_SOURCES:
        holder = ancestors.get(level)
        value = holder.properties.get(key) if holder is not None else None
        if not isinstance(value, str) or not value:
            return None  # lineage incomplete — another family serves
        letters.append(value.strip()[0].lower())
        labels.append(label)
    answer = "".join(letters)
    return Puzzle(
        name=f"The Lineage Sigil of the {node.level}",
        kind=PuzzleKind.LOCK,
        prompt=(f"{node.name} is sealed by its whole lineage. Three marks "
                f"open it — the first letter of {labels[0]}, of {labels[1]}, "
                f"and of {labels[2]}. Speak the three-letter sigil."),
        answer=answer,
        hints=[
            "Every scale that enfolds this place has left one mark on it.",
            "Climb: region, then world, then galaxy — read one word at each.",
            f"The first mark is '{letters[0]}'.",
        ],
        max_attempts=_ATTEMPTS_BY_DIFFICULTY[difficulty],
        difficulty=difficulty,
    )


# ── BOND: the middle scale looks up one step ─────────────────────────────────
# An atom's puzzle is chemistry: name the thing that binds it. The answer
# is a property of the MOLECULE that holds it — geometry or compound type,
# both generated categoricals the overlay never mutates — the LOCK idea at
# the scale where "the place that holds you" is a lattice.

_BOND_KEYS = (("geometry", "geometry"), ("compound_type", "compound nature"))


def _make_bond(node: SpatialNode, rng: random.Random,
               difficulty: int) -> Puzzle | None:
    if node.level != "Atom" or node.parent is None:
        return None
    molecule = node.parent
    own_values = _property_values(node)
    usable = [(key, label) for key, label in _BOND_KEYS
              if isinstance(molecule.properties.get(key), str)
              and molecule.properties[key].strip().lower() not in own_values]
    if not usable:
        return None
    key, label = usable[rng.randrange(len(usable))]
    answer = molecule.properties[key].strip().lower()
    return Puzzle(
        name=f"The Bond of the {node.level}",
        kind=PuzzleKind.LOCK,
        prompt=(f"{node.name} does not float free — a lattice holds it. "
                f"Name the {label} of the molecule it is bound into, and "
                "the bond will answer."),
        answer=answer,
        hints=[
            f"The molecule that holds this atom is {molecule.name}.",
            f"Step up one scale and read its {label}.",
            f"It begins with '{answer[0]}'.",
        ],
        max_attempts=_ATTEMPTS_BY_DIFFICULTY[difficulty],
        difficulty=difficulty,
    )


def _make_enfold(node: SpatialNode, rng: random.Random,
                 difficulty: int) -> Puzzle | None:
    suffix = node.name.rpartition("-")[2]
    if not suffix.isdigit():
        return None
    depth = len(suffix)
    forms: list[tuple[str, str, str, list[str]]] = []

    enclosures = depth - 1
    within = _TOTAL_SCALES - depth
    ordinal = suffix[-1]

    if enclosures > 0:
        forms.append((
            "The Enfolding Count",
            f"Every place is held. Count the scales that enfold {node.name}, "
            "from the whole of everything down to the one whose skin "
            "touches it. How many hold it?",
            str(enclosures),
            ["Start from the largest thing there is and step inward.",
             "A name carries its whole lineage — read what follows the dash.",
             "Count the digits after the dash, then subtract this place itself."],
        ))
    if within > 0:
        forms.append((
            "The Depth Within",
            f"Within {node.name} the folding continues — worlds inside "
            "worlds, down to the smallest indivisible grain. How many "
            "scales lie enfolded beneath this one?",
            str(within),
            ["Eleven scales run from the whole of everything to the "
             "smallest particle.",
             "Count how many of them are smaller than this place.",
             "Eleven, minus every scale from here upward."],
        ))
    if depth > 1:
        child_word = _ENFOLD_CHILD_WORD.get(node.level, "children")
        forms.append((
            "The Fold Ordinal",
            f"Of all the {child_word} its holder keeps, which one is "
            f"{node.name}? Speak its number.",
            ordinal,
            ["Position in the fold is written where everything else is.",
             "The last step of the lineage is the newest one.",
             "Read the final digit after the dash."],
        ))
    if not forms:
        return None
    name, prompt, answer, hints = forms[rng.randrange(len(forms))]
    return Puzzle(
        name=f"{name} of the {node.level}",
        kind=PuzzleKind.NAVIGATION,
        prompt=prompt,
        answer=answer,
        hints=hints,
        max_attempts=_ATTEMPTS_BY_DIFFICULTY[difficulty],
        difficulty=difficulty,
    )


def _make_lock(node: SpatialNode, rng: random.Random,
               difficulty: int) -> Puzzle | None:
    """A travel-key lock: the answer is a property of the node that HOLDS
    this one — readable in plain sight one scale up, not guessable here.

    This is the mechanic that makes the `locked` trait real: a locked Room
    sends the player back out to its Region to learn something about where
    they are. Deliberately knowledge-of-the-world, not word-decoding.
    Returns None when the node isn't locked or has no suitable keeper.
    """
    if not node.properties.get("locked") or node.parent is None:
        return None
    parent = node.parent
    own_values = _property_values(node)
    keys = [k for k in _LOCK_KEY_CANDIDATES
            if isinstance(parent.properties.get(k), str)
            and parent.properties[k].strip().lower() not in own_values]
    if not keys:
        return None
    key = rng.choice(keys)
    answer = parent.properties[key].strip().lower()
    key_label = key.replace("_", " ")
    hints = [
        f"The keeper is {parent.name} — the {parent.level} that holds this place.",
        f"Stand in the keeper and read its {key_label}.",
        f"It begins with '{answer[0]}'.",
    ]
    return Puzzle(
        name=f"The Sealed {node.level}",
        kind=PuzzleKind.LOCK,
        prompt=(f"{node.name} is sealed. The lock listens for a truth about "
                f"the {parent.level.lower()} that holds it: speak its "
                f"{key_label}, and the way opens."),
        answer=answer,
        hints=hints,
        max_attempts=_ATTEMPTS_BY_DIFFICULTY[difficulty],
        difficulty=difficulty,
    )


def _make_riddle(node: SpatialNode, rng: random.Random, difficulty: int) -> Puzzle | None:
    """Reuse a hand-written static-pool riddle/cipher/pattern for this scale,
    de-leaked and selected per node. Returns None if the pool has nothing
    usable, so the caller can fall back to a generated family."""
    usable = _clean_pool_puzzles(node.level, node)
    if not usable:
        return None
    # Hand-written riddles are a tiny pool (3-6 per level) serving thousands
    # of nodes — unthrottled they repeat hundreds of times across a full
    # world (measured: one riddle answered 410 nodes). Decline in proportion
    # to pool size so riddles stay rare hand-crafted treats; the caller
    # falls through to a generated family.
    if rng.random() > min(1.0, len(usable) / 24):
        return None
    chosen = copy.deepcopy(rng.choice(usable))
    # Give it the same fair attempt budget as generated puzzles at this tier.
    chosen.max_attempts = max(chosen.max_attempts, _ATTEMPTS_BY_DIFFICULTY[difficulty])
    chosen.difficulty = difficulty
    return chosen


# ── CAUSAL AUGURY (ADR-010): the world's dynamics as puzzle content ─────────
# The world-reading families teach structure; the Augury teaches DYNAMICS:
# predict how a disturbance rising from this node carries through its
# enclosing scales, under the law of the sky it climbs. The answer is the
# engine's own forecast (causality/forecast.py — pinned equivalent to the
# live bus), so solving one is a real act of understanding the physics.
#
# Election is a seed-pure hash BEFORE the weighted draw (the lock branch's
# pattern): elected nodes serve the Augury; everyone else falls through
# byte-identically to the puzzle they serve today. Every decline path runs
# before any rng consumption, so an elected node the family cannot serve
# (no law, Inverted flip, a cry that never sounds, no valid form) also
# falls through byte-identically.

_AUGURY_LEVELS = ("Region", "Room", "Object", "Molecule", "Atom",
                  "SubatomicParticle")
# ~10% of the inhabited scales; tuned against the ecology gate (ADR-010).
_AUGURY_ELECTION_RATE = 0.10

# Authored temperament lines — hint 1 teaches the law's character in the
# world's voice. Inverted is deliberately absent: the family declines there
# (flip sends the live act into children the ancestor chain cannot see, and
# on the staged both-arm path flip is a no-op — nothing Inverted to teach).
_LAW_TEMPERAMENT: dict[str, str] = {
    "Newtonian":     "Newtonian skies are strict: every step dims the cry "
                     "hard, and it dies young.",
    "Quantum":       "Quantum skies may let the cry pass a scale in "
                     "silence, undimmed, and sound beyond it.",
    "Fractal":       "Fractal skies are self-similar: every second step "
                     "keeps the cry's full voice.",
    "Probabilistic": "Probabilistic skies draw their own dimming — but the "
                     "same cry always draws the same.",
    "Recursive":     "Recursive skies echo: every third step returns the "
                     "cry at full voice.",
    "Viscous":       "Viscous skies carry the cry far, but slowly.",
    "Crystalline":   "Crystalline skies favor the climb: the lattice "
                     "transmits upward well.",
    "Tidal":         "Tidal skies surge and ebb: the dimming alternates "
                     "strong and weak.",
    "Threadbare":    "Threadbare skies are lossy: a step may simply fray, "
                     "and the cry ends there.",
    "Palindromic":   "Palindromic skies keep a mirrored rhythm: the "
                     "dimming reads the same forwards and back.",
    "Slow light":    "Slow-light skies dim the cry steadily; only the news "
                     "of it travels at a crawl.",
}


def _augury_elected(node: SpatialNode) -> bool:
    digest = hashlib.sha256(
        f"augury-election:{node.level}:{node.name}".encode("utf-8")).digest()
    return (int.from_bytes(digest[:8], "big") / 2**64) < _AUGURY_ELECTION_RATE


def _make_causal_augury(node: SpatialNode, rng: random.Random,
                        difficulty: int) -> Puzzle | None:
    from causality.forecast import up_arm_forecast
    from causality.laws import law_for

    law = law_for(node)
    if law is None or law.flip or law.name not in _LAW_TEMPERAMENT:
        return None
    forecast = up_arm_forecast(node)
    terminus = forecast.terminus
    if terminus is None:
        return None  # the cry never sounds — nothing to predict here

    universe = next((a for a in _ancestors(node) if a.level == "Universe"),
                    None)
    if universe is None:
        return None

    # The first scale where the cry rings undimmed — as loud as at the
    # step before (a factor-1.0 hop; the Fractal sky's signature).
    rung = forecast.rung
    echo = next((rung[i] for i in range(1, len(rung))
                 if rung[i].strength == rung[i - 1].strength), None)

    # Valid question forms for THIS node's forecast, difficulty-shaped:
    # gentle auguries count the reach; harder ones name the terminus; the
    # hardest read the echo where one exists. All decline paths are above —
    # from here on rng consumption is safe.
    forms = ["reach"] if difficulty == 1 else (
        ["reach", "terminus"] if difficulty == 2 else (
            ["terminus", "echo"] if echo is not None else ["terminus"]))
    form = forms[rng.randrange(len(forms))]

    temperament = _LAW_TEMPERAMENT[law.name]
    if difficulty <= 2:
        sky = f"This sky keeps {law.name} law."
    else:
        sky = (f"The sky over everything here is {_living_name(universe)}; "
               "its law is written on it, for those who climb and read.")

    if form == "reach":
        answer = str(len(rung))
        prompt = (
            f"A cry rises from {node.name}, climbing the fold. {sky} "
            "Judge how far it carries: count the enclosing scales in "
            "which it still sounds before it fades, and answer with that "
            "count."
        )
        hints = [
            temperament,
            "Each enclosing scale dims the cry by its sky's law; below a "
            "twentieth of its birth voice, it is silence.",
            f"The count has {len(answer)} digit(s).",
        ]
    elif form == "terminus":
        if terminus.node.level == "Universe":
            # Naming the universe in the prompt would print the answer.
            sky = f"This sky keeps {law.name} law."
        answer = _living_name(terminus.node)
        prompt = (
            f"A cry rises from {node.name}, climbing the fold toward the "
            f"whole. {sky} Judge where it dies: return with the living "
            "name of the LAST enclosing scale in which it sounds."
        )
        hints = [
            temperament,
            f"The last scale it sounds in is a {terminus.node.level}; its "
            "living name is the words before its lineage mark.",
            f"The first word begins with '{answer[0]}'.",
        ]
    else:
        answer = _living_name(echo.node)
        prompt = (
            f"A cry rises from {node.name}, climbing the fold. {sky} "
            "Somewhere above, the cry rings UNDIMMED — exactly as loud "
            "as at the step before. Return with the living name of the "
            "first such scale."
        )
        hints = [
            temperament,
            f"The undimmed ring sounds at a {echo.node.level}; its living "
            "name is the words before its lineage mark.",
            f"The first word begins with '{answer[0]}'.",
        ]

    return Puzzle(
        name=f"The Causal Augury of the {node.level}",
        kind=PuzzleKind.PREDICTION,
        prompt=prompt,
        answer=answer,
        hints=hints,
        max_attempts=_ATTEMPTS_BY_DIFFICULTY[difficulty],
        difficulty=difficulty,
    )


# ── Selector ─────────────────────────────────────────────────────────────────

# Which families each difficulty tier draws from, and their relative weights.
# Ciphers only appear beyond the gentlest tier.  World-reading families are
# deliberately prominent at every difficulty: transform complexity and the
# attempt budget vary, but whether the world matters does not. Riddles are
# offered everywhere a clean hand-written example exists.
_FAMILY_WEIGHTS: dict[int, list[tuple[str, int]]] = {
    1: [("anagram", 3), ("sequence", 2), ("riddle", 3),
        ("keeper", 4), ("compass", 4)],
    2: [("anagram", 3), ("cipher", 2), ("sequence", 2), ("riddle", 3),
        ("keeper", 4), ("compass", 4)],
    3: [("anagram", 2), ("cipher", 3), ("sequence", 3), ("riddle", 2),
        ("keeper", 4), ("compass", 4)],
    4: [("anagram", 2), ("cipher", 4), ("sequence", 3), ("riddle", 2),
        ("keeper", 4), ("compass", 4)],
}

_FAMILY_FN: dict[str, Callable[[SpatialNode, random.Random, int], Puzzle | None]] = {
    "anagram":  _make_anagram,
    "cipher":   _make_cipher,
    "sequence": _make_sequence,
    "riddle":   _make_riddle,
    "enfold":   _make_enfold,
    "lineage":  _make_lineage,
    "bond":     _make_bond,
    "keeper":   _make_keeper_witness,
    "compass":  _make_ancestral_compass,
}


def build_puzzle(node: SpatialNode, epoch: int = 0) -> Puzzle:
    """Generate this node's puzzle: fair, non-leaking, difficulty-tuned to the
    scale, and unique to the node. Deterministic in (node identity, epoch).

    `epoch` is the node's renewal count: when the world's entropy re-arms a
    solved node (see causality/wiring + PUZZLE_REARM), the epoch increments
    and the node grows a FRESH puzzle — new content, new name (so the
    solved-state of the old one doesn't apply), same per-node difficulty
    (difficulty is a character trait; content is what renews). Epoch 0 is
    byte-identical to the pre-renewal behavior.
    """
    rng = node_rng(node) if epoch == 0 else random.Random(int.from_bytes(
        hashlib.sha256(
            f"{node.level}:{node.name}:renewal:{epoch}".encode()).digest()[:8],
        "big"))
    difficulty = node_difficulty(node)
    families = list(_FAMILY_WEIGHTS.get(difficulty, _FAMILY_WEIGHTS[2]))
    # A locked Room has one coherent meaning: its puzzle IS the contextual
    # travel key written in the Region that holds it. The earlier weighted
    # selection left some locked doors serving generic word puzzles, and the
    # legacy static "four-digit lock" could impersonate this upgraded family.
    # The static duplicate is retired; when a keeper key exists, this path is
    # authoritative at every renewal epoch.
    if node.properties.get("locked") and node.parent is not None:
        lock = _make_lock(node, rng, difficulty)
        if lock is not None and not _answer_leaks(lock, node):
            return _finish(lock, node, rng, epoch)
    # The Causal Augury (ADR-010): a seed-pure hash elects ~10% of the
    # inhabited scales to serve the dynamics-prediction family. The whole
    # augury path runs in its own deterministic RNG domain (the generator's
    # domain-separation idiom), so EVERY rejection — a decline, or the
    # leak screen — leaves the shared draw untouched and the node falls
    # through byte-identically: the re-pin's blast radius is exactly the
    # nodes that serve the family.
    if node.level in _AUGURY_LEVELS and _augury_elected(node):
        augury_rng = random.Random(int.from_bytes(hashlib.sha256(
            f"augury-content:{node.level}:{node.name}:{epoch}".encode(
            )).digest()[:8], "big"))
        augury = _make_causal_augury(node, augury_rng, difficulty)
        if augury is not None and not _answer_leaks(augury, node):
            return _finish(augury, node, augury_rng, epoch)
    # Cosmic scales often serve an ENFOLD — the nesting itself as content
    # (the mirror of the LOCK: look into the fold instead of up out of it).
    if node.level in _ENFOLD_LEVELS:
        families.append(("enfold", 6))
    # Deep scales travel their lineage; atoms read the lattice that binds
    # them — the relational families that de-flatten the middle world.
    if node.level in _LINEAGE_LEVELS and node.parent is not None:
        families.append(("lineage", 6))
    if node.level == "Atom" and node.parent is not None:
        families.append(("bond", 6))

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
            return _finish(puzzle, node, rng, epoch)

    # Every scale has a word bank and `_pick_word` already excludes any word in
    # the node's name or properties, so an anagram of a picked word cannot leak
    # (the answer appears only scrambled). Guaranteed-clean fallback.
    return _finish(_make_anagram(node, rng, difficulty), node, rng, epoch)


def _finish(puzzle: Puzzle, node: SpatialNode, rng: random.Random,
            epoch: int) -> Puzzle:
    """Apply the node's prompt dressing and the renewal name suffix.

    Dressing weaves what the node IS into the puzzle's fiction. It is
    re-screened for answer leaks (a numeric answer could collide with a
    danger figure) and dropped, not the puzzle, on collision.
    """
    dressing = _dress(node, rng)
    if dressing:
        dressed = copy.copy(puzzle)
        dressed.prompt = f"{dressing} {puzzle.prompt}"
        if not _answer_leaks(dressed, node):
            puzzle = dressed
    if epoch > 0:
        renewed = copy.copy(puzzle)
        renewed.name = f"{puzzle.name} · Renewal {epoch}"
        puzzle = renewed
    return puzzle
