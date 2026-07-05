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
