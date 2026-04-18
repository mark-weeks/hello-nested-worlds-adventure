# hello-nested-worlds-adventure

A procedural multiverse simulation engine with autonomous agents and escape-room puzzles.

---

## What it does

Generates a recursive world hierarchy — Multiverse down to SubatomicParticle — and lets you run agents through it or discover and solve puzzles embedded in the world.

---

## Quick start

```bash
# Print the generated world tree
python main.py world

# Run an agent through the world and print its traversal log
python main.py agent

# Find and interactively play puzzles in the world
python main.py puzzles
```

All commands accept `--seed INT` for reproducible runs. Use `--help` on any subcommand for options:

```bash
python main.py world --help
python main.py agent --name "Recon" --danger-threshold 4
python main.py --seed 7 world --depth 6 --min-breadth 1 --max-breadth 3
```

---

## Architecture

### Spatial hierarchy

10 nested levels, each with level-specific metadata:

```
Multiverse → Universe → Galaxy → Planet → Region → Room → Object → Molecule → Atom → SubatomicParticle
```

Example properties by level:

| Level | Properties |
|-------|------------|
| Multiverse | theme, age, stability |
| Planet | gravity, biome, inhabited, population, moons |
| Region | danger_level, terrain, faction_control |
| Room | has_puzzle, locked, lighting, exits |
| Atom | element, ionized, atomic_number |

### Agent system

Agents traverse the world using a finite state machine:

```
IDLE → EXPLORE → INTERACT → EXPLORE
              └──► EXIT  (dangerous region or dead-end)
```

- Avoid regions where `danger_level > threshold` (configurable)
- Interact with rooms that have puzzles or interactive objects
- Log every action with node name, level, and FSM state

### Puzzle engine

Four puzzle kinds: **Riddle**, **Cipher**, **Lock**, **Sequence**

- Each puzzle has a prompt, a canonical answer, hints, and a max-attempt limit
- `PuzzleEngine` attaches puzzles to `Room` nodes and runs them interactively
- Answers are case-insensitive and whitespace-tolerant

---

## Project structure

```
hello-nested-worlds-adventure/
├── main.py                      # CLI entry point (world / agent / puzzles)
├── multiverse/
│   ├── node.py                  # SpatialNode class
│   └── generator.py             # Procedural generation with named locations
├── agents/
│   ├── agent.py                 # Agent with FSM traversal and logging
│   └── behaviors.py             # State enum and transition logic
├── puzzles/
│   ├── types.py                 # Puzzle dataclass (kind, attempts, hints)
│   └── engine.py                # PuzzleEngine: attach, collect, run
├── tests/
│   ├── test_generator.py        # 8 tests: determinism, depth, properties
│   ├── test_agent.py            # 14 tests: FSM, avoidance, deduplication
│   └── test_puzzles.py          # 11 tests: solve, fail, hints, engine
└── docs/
    ├── CHANGELOG.md
    └── architecture/overview.md
```

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

33 tests, all passing.

---

## Development phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Scaffold spatial hierarchy and generator | Complete |
| 1.5 | Add metadata to each node | Complete |
| 2 | Agent FSM traversal and logging | Complete |
| 3 | Puzzle engine with four puzzle kinds | Complete |
| 4 | TUI, save/load, narrative arcs | Planned |

---

## License

MIT

## Author

**Mark Weeks** — [markweeks.dev](https://markweeks.dev) · [multilogue.io](https://multilogue.io)
