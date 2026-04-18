# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

### Added
- **Enriched generator** (`multiverse/generator.py`): named locations (e.g. "Kethara", "Verdant Hollow"), variable branching (`min_breadth`/`max_breadth`), and richer level-specific properties (biome, faction control, particle spin, etc.)
- **Agent system** (`agents/`): `Agent` class with FSM traversal (`Idle → Explore → Interact → Exit`), danger-avoidance logic, interaction detection, and structured traversal logs
- **Puzzle engine** (`puzzles/`): `Puzzle` type with four kinds (Riddle, Cipher, Lock, Sequence), attempt tracking, hints, and `PuzzleEngine` for attaching/collecting puzzles from the world graph
- **Test suite** (`tests/`): 33 pytest tests covering generator determinism, agent FSM transitions, avoidance, puzzle solving, and engine idempotency
- **CLI** (`main.py`): `argparse`-based interface with three subcommands: `world`, `agent`, `puzzles`

---

## [Phase 1.5] — 2025-09-13

### Added
- Metadata generation for `SpatialNode` objects by level (gravity, element, danger_level, etc.)

## [Phase 1] — 2025-09-13

### Added
- `SpatialNode` class with recursive children and properties dict
- `generate_node_hierarchy()` with seed-based deterministic generation
- 10-level spatial hierarchy: Multiverse → … → SubatomicParticle
- Project folder structure: `multiverse/`, `agents/`, `puzzles/`, `docs/`
