# puzzles/data.py — static puzzle pools and biome clue text.
# Pure data; no behaviour.  Engine logic lives in puzzles/engine.py.

from puzzles.types import Puzzle, PuzzleKind


_MULTIVERSE_PUZZLES = [
    Puzzle(
        name="The Entropy Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="In a universe that tends toward disorder, what always increases over time?",
        answer="entropy",
        hints=["It is a measure of disorder or randomness.", "The second law of thermodynamics describes it."],
    ),
    Puzzle(
        name="The Paradox Gate",
        kind=PuzzleKind.LOGIC,
        prompt="If this statement is true, then it is false. If it is false, then it is true. What is this called?",
        answer="paradox",
        hints=["A self-referential contradiction.", "Neither purely true nor false."],
    ),
    Puzzle(
        name="The Infinite Recursion",
        kind=PuzzleKind.RIDDLE,
        prompt="I contain everything that contains me. I am within myself. What concept describes my structure?",
        answer="recursion",
        hints=["A function that calls itself.", "Russian dolls are a physical analogy."],
    ),
    Puzzle(
        name="The Age Logic",
        kind=PuzzleKind.LOGIC,
        prompt="A multiverse is 13.8 billion years old. A parallel one formed 4.6 billion years later. How old is the younger multiverse?",
        answer="9.2",
        hints=["Subtract the delay from the older age.", "13.8 - 4.6 = ?"],
    ),
]

_UNIVERSE_PUZZLES = [
    Puzzle(
        name="The Physics Law",
        kind=PuzzleKind.RIDDLE,
        prompt="In a Newtonian universe, what fundamental law states that every action has an equal and opposite reaction?",
        answer="newton's third law",
        hints=["Named after Sir Isaac Newton.", "Action and reaction are equal and opposite."],
    ),
    Puzzle(
        name="The Quantum Probability",
        kind=PuzzleKind.LOGIC,
        prompt="In a Quantum universe, a particle has a 1/3 chance of being observed at each of three locations. If observed twice independently, what is the chance it appears at the same location both times?",
        answer="1/3",
        hints=["Each observation is independent.", "The probability does not change between observations."],
    ),
    Puzzle(
        name="The Expansion Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="What force is responsible for the accelerating expansion of the universe, overcoming gravity on cosmic scales?",
        answer="dark energy",
        hints=["It makes up roughly 68% of the universe.", "The opposite of gravity on large scales."],
    ),
]

_GALAXY_PUZZLES = [
    Puzzle(
        name="The Spiral Sequence",
        kind=PuzzleKind.PATTERN,
        prompt="A spiral galaxy's arms follow this star-count pattern: 2, 4, 8, 16, ?",
        answer="32",
        hints=["Each term doubles the previous.", "2^5 = ?"],
    ),
    Puzzle(
        name="The Star Density Navigation",
        kind=PuzzleKind.NAVIGATION,
        prompt="You travel from the galactic core outward: 3 sectors north, 2 sectors east, 3 sectors south. How many sectors east of the core are you?",
        answer="2",
        hints=["North and south cancel each other.", "Only the east displacement remains."],
    ),
    Puzzle(
        name="The Galactic Shape Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="I have arms that spiral outward from my center, containing billions of stars. What shape describes me?",
        answer="spiral",
        hints=["Like a pinwheel viewed from above.", "The Milky Way is an example."],
    ),
    Puzzle(
        name="The Black Hole Pattern",
        kind=PuzzleKind.PATTERN,
        prompt="A black hole's mass doubles every million years: 1M, 2M, 4M, 8M, ? solar masses.",
        answer="16m",
        hints=["Each step doubles.", "8 × 2 = ?"],
    ),
]

_PLANETARY_SYSTEM_PUZZLES = [
    Puzzle(
        name="The Orbital Sequence",
        kind=PuzzleKind.SEQUENCE,
        prompt="Arrange by distance from a yellow dwarf star (nearest first): gas giant, rocky inner, icy outer, asteroid belt",
        answer="rocky inner asteroid belt gas giant icy outer",
        hints=["Rocky planets form closest to the stellar heat.", "Ice cannot survive too close to a star."],
    ),
    Puzzle(
        name="The Habitable Zone Logic",
        kind=PuzzleKind.LOGIC,
        prompt="A planetary system has 8 planets. If 3 are too hot and 4 are too cold, how many lie in the habitable zone?",
        answer="1",
        hints=["Total planets = hot + cold + habitable.", "8 - 3 - 4 = ?"],
    ),
    Puzzle(
        name="The Binary Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="In a binary star system, a planet orbits both suns. What shape is its orbital path called?",
        answer="figure eight",
        hints=["It traces a path around both stars.", "The shape resembles the number 8."],
    ),
    Puzzle(
        name="The Star Type Logic",
        kind=PuzzleKind.LOGIC,
        prompt="A red dwarf burns cooler than a yellow dwarf, which burns cooler than a blue giant. Rank them hottest to coolest.",
        answer="blue giant yellow dwarf red dwarf",
        hints=["Blue is the hottest stellar colour.", "Red is the coolest."],
    ),
]

_PLANET_PUZZLES = [
    Puzzle(
        name="The Tundra Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="I am a biome where permafrost lies beneath the surface and few trees survive. What am I?",
        answer="tundra",
        hints=["Found near the poles.", "Permanently frozen subsoil."],
    ),
    Puzzle(
        name="The Jungle Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="I am a biome of dense canopy and high rainfall, teeming with the greatest biodiversity on any world. What am I?",
        answer="jungle",
        hints=["Tropical and very wet.", "Also called rainforest."],
    ),
    Puzzle(
        name="The Desert Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="I receive less than 250mm of rainfall per year. Despite heat by day, I freeze at night. What biome am I?",
        answer="desert",
        hints=["Camels and cacti thrive here.", "Sand and rock dominate."],
    ),
    Puzzle(
        name="The Ocean World",
        kind=PuzzleKind.RIDDLE,
        prompt="A planet entirely covered in water has no landmass. What single word describes this world's biome?",
        answer="ocean",
        hints=["Think of the biome name.", "Water, water everywhere."],
    ),
    Puzzle(
        name="The Volcanic Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="I am a biome shaped by constant eruptions, where lava flows create and destroy terrain. What am I?",
        answer="volcanic",
        hints=["Hot springs and lava fields dominate.", "Magma is the key feature."],
    ),
]

_ROOM_PUZZLES = [
    Puzzle(
        name="The Shifted Message",
        kind=PuzzleKind.CIPHER,
        prompt="Decode this Caesar-3 cipher: HQWHU WKH YDXOW",
        answer="enter the vault",
        hints=["Each letter is shifted by 3.", "Shift each letter back by 3 positions."],
    ),
    Puzzle(
        name="The Four-Digit Lock",
        kind=PuzzleKind.LOCK,
        prompt="The code is the sum of the first four primes.",
        answer="17",
        hints=["The first four primes are 2, 3, 5, 7.", "Add them together."],
        max_attempts=5,
    ),
    Puzzle(
        name="The Silent Guardian",
        kind=PuzzleKind.RIDDLE,
        prompt="I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?",
        answer="echo",
        hints=["Think of sound.", "It bounces back."],
    ),
    Puzzle(
        name="The Directional Trial",
        kind=PuzzleKind.NAVIGATION,
        prompt="You enter a corridor facing north. You turn right, walk forward, then turn left, walk forward. What direction are you now facing?",
        answer="north",
        hints=["Right from north is east.", "Left from east is north again."],
    ),
    Puzzle(
        name="The Return Path",
        kind=PuzzleKind.NAVIGATION,
        prompt="From the entrance: go north, then east, then south. What single direction returns you to the start?",
        answer="west",
        hints=["Track your position step by step.", "You ended up one step east of where you started."],
    ),
    Puzzle(
        name="The Paradox Box",
        kind=PuzzleKind.RIDDLE,
        prompt="I have cities but no houses, mountains but no trees, water but no fish. What am I?",
        answer="map",
        hints=["You can hold the whole world in your hands.", "It's flat."],
    ),
]

_OBJECT_PUZZLES = [
    Puzzle(
        name="The Scrambled Gate",
        kind=PuzzleKind.ANAGRAM,
        prompt="Unscramble these letters to find what connects worlds: LATPRO",
        answer="portal",
        hints=["It is a doorway between places.", "Six letters. Starts with P."],
    ),
    Puzzle(
        name="The Hidden Force",
        kind=PuzzleKind.ANAGRAM,
        prompt="Unscramble to reveal a fundamental force: YTGVIAR",
        answer="gravity",
        hints=["It pulls things together across every scale.", "Seven letters. Shapes every planet."],
    ),
    Puzzle(
        name="The Crystal Cipher",
        kind=PuzzleKind.CIPHER,
        prompt="A crystal terminal displays encoded text: FUBVWDO. Decode this Caesar-3 cipher.",
        answer="crystal",
        hints=["Each letter is shifted forward by 3.", "Shift back by 3 to reveal the material."],
    ),
    Puzzle(
        name="The Metal Anagram",
        kind=PuzzleKind.ANAGRAM,
        prompt="Unscramble this material found in ancient mechanisms: LATEM",
        answer="metal",
        hints=["Used in tools and armor.", "Five letters, rearranged."],
    ),
    Puzzle(
        name="The Stone Cipher",
        kind=PuzzleKind.CIPHER,
        prompt="The rune stone bears a Caesar-3 cipher: VWRQH",
        answer="stone",
        hints=["Each letter shifted forward by 3.", "Shift back by 3."],
    ),
]

_MOLECULE_PUZZLES = [
    Puzzle(
        name="The Bond Pattern",
        kind=PuzzleKind.PATTERN,
        prompt="A molecule gains bonds in this pattern: 1, 2, 4, 8, ? How many bonds come next?",
        answer="16",
        hints=["Each step doubles the bond count.", "8 × 2 = ?"],
    ),
    Puzzle(
        name="The Compound Sequence",
        kind=PuzzleKind.SEQUENCE,
        prompt="Arrange by complexity, simplest first: polymer, monomer, atom, subatomic particle",
        answer="subatomic particle atom monomer polymer",
        hints=["Start with the smallest building block.", "Particles → atoms → monomers → polymers."],
    ),
    Puzzle(
        name="The Covalent Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="I am the type of molecular bond formed when atoms share electrons equally. What am I?",
        answer="covalent",
        hints=["Neither atom gives up an electron entirely.", "Carbon-carbon bonds are of this type."],
    ),
    Puzzle(
        name="The Organic Pattern",
        kind=PuzzleKind.PATTERN,
        prompt="Carbon atoms in a chain: methane (1C), ethane (2C), propane (3C), butane (4C), ? (5C).",
        answer="pentane",
        hints=["The prefix 'pent' means five.", "Alkane chain with five carbons."],
    ),
]

_ATOM_PUZZLES = [
    Puzzle(
        name="The Gold Anagram",
        kind=PuzzleKind.ANAGRAM,
        prompt="Unscramble the element name: LDOG",
        answer="gold",
        hints=["Its symbol is Au.", "Precious and shiny."],
    ),
    Puzzle(
        name="The Hydrogen Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="I am the lightest element in the periodic table, symbol H. What is my name?",
        answer="hydrogen",
        hints=["Most abundant element in the universe.", "H₂O contains two of me."],
    ),
    Puzzle(
        name="The Ion Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="When an atom loses an electron, it gains a positive charge. What is such an atom called?",
        answer="cation",
        hints=["The opposite is an anion.", "Cat-ion → positive charge."],
    ),
    Puzzle(
        name="The Iron Anagram",
        kind=PuzzleKind.ANAGRAM,
        prompt="Unscramble to reveal an element used in steel: NOIR",
        answer="iron",
        hints=["Its symbol is Fe.", "Magnetic and abundant in planetary cores."],
    ),
]

_SUBATOMIC_PUZZLES = [
    Puzzle(
        name="The Quantum Paradox",
        kind=PuzzleKind.RIDDLE,
        prompt="In quantum mechanics, a particle can be in two states simultaneously until observed. What is this phenomenon called?",
        answer="superposition",
        hints=["Schrödinger's cat illustrates this.", "Observation collapses the wave function."],
    ),
    Puzzle(
        name="The Spin Logic",
        kind=PuzzleKind.LOGIC,
        prompt="An entangled particle pair must have opposite spins. If particle A measures 'up', what spin will particle B show?",
        answer="down",
        hints=["Entanglement means opposite correlated states.", "Up and down are the two options."],
    ),
    Puzzle(
        name="The Electron Riddle",
        kind=PuzzleKind.RIDDLE,
        prompt="I am the subatomic particle with charge -1 and negligible mass, orbiting the nucleus. What am I?",
        answer="electron",
        hints=["Found in the electron cloud.", "Negative charge carrier."],
    ),
    Puzzle(
        name="The Quark Logic",
        kind=PuzzleKind.LOGIC,
        prompt="A proton is made of two up quarks and one down quark. A neutron has two down quarks and one up quark. Which particle has more up quarks?",
        answer="proton",
        hints=["Proton: u, u, d. Neutron: d, d, u.", "Count the up quarks in each."],
    ),
]


LEVEL_POOLS = {
    "Multiverse":        _MULTIVERSE_PUZZLES,
    "Universe":          _UNIVERSE_PUZZLES,
    "Galaxy":            _GALAXY_PUZZLES,
    "Planetary System":  _PLANETARY_SYSTEM_PUZZLES,
    "Planet":            _PLANET_PUZZLES,
    "Room":              _ROOM_PUZZLES,
    "Object":            _OBJECT_PUZZLES,
    "Molecule":          _MOLECULE_PUZZLES,
    "Atom":              _ATOM_PUZZLES,
    "SubatomicParticle": _SUBATOMIC_PUZZLES,
}

DEFAULT_POOL = _ROOM_PUZZLES


BIOME_CLUES = {
    "tundra":     ("I am a biome of frozen ground and sparse vegetation found near the poles. What am I?", "tundra"),
    "jungle":     ("I am a dense, rainy biome bursting with life and towering canopy. What am I?", "jungle"),
    "desert":     ("I receive almost no rain but sear with heat by day and freeze at night. What am I?", "desert"),
    "ocean":      ("I cover an entire world with water, with no dry land anywhere. What biome am I?", "ocean"),
    "volcanic":   ("Lava flows define my landscape; eruptions constantly reshape me. What am I?", "volcanic"),
    "temperate":  ("I have four seasons and moderate rainfall, neither too hot nor too cold. What biome am I?", "temperate"),
    "irradiated": ("Intense radiation from a nearby pulsar has scorched my surface bare. What biome am I?", "irradiated"),
}
