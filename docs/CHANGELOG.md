# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

### Added
- **Interactive interface** (`interface/`): `run_session()` brings the world to life as a playable terminal session. Three interaction modes in a single REPL:
  - *Spatial* — navigate the hierarchy with `go <N>` / `up`; each scale level rendered in a distinct ANSI colour
  - *Conversational* — `speak [message]` routes to the consciousness module (Claude); unrecognised input is forwarded as a speak message
  - *Ambient* — `observe` runs an agent traversal from the current node with live causal-event output (node name, event kind, dampened strength bar)
  - `map` prints an ASCII subtree (3 levels deep); `puzzle` drops into the puzzle engine at the current location
- **`play` CLI subcommand** (`main.py`): `python main.py play [--depth N] [--min-breadth N] [--max-breadth N]`
- **16 interface tests** (`tests/test_interface.py`): formatting, navigation, ambient mode, puzzle integration


### Changed
- **Project renamed** to *Nested Worlds Adventure* (`pyproject.toml`, CLI, server banner, README)
- **Planetary System** added between Galaxy and Planet in the 11-level hierarchy (`multiverse/generator.py`); includes star_type, planet_count, habitable_zone, and asteroid_belt properties
- **Self-preservation** replaces "danger avoidance" throughout the agent system: `should_avoid` renamed to `should_preserve`, log messages changed from "avoided" to "withdrew", CLI help updated
- **Puzzle engine** expanded with four new `PuzzleKind` variants: `PATTERN`, `LOGIC`, `ANAGRAM`, `NAVIGATION` — each with multiple puzzle instances
- Default `max_depth` updated to 11 to match the expanded 11-level hierarchy



### Vision
Reframed as a shared persistent multiverse for simultaneous human and AI participation. Core new systems identified: node consciousness (Claude-powered voice layer), causality engine (cross-scale propagation), persistence (world state database), server (real-time API), and interface (generative visual layer). README and architecture docs updated to reflect new direction. New module directories scaffolded.

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
