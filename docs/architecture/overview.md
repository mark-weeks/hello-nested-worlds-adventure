# Architecture Overview

## Components

### `multiverse/` — World Generation

- **`node.py`** — `SpatialNode(name, level, children, properties)`: the core recursive data structure. Each node holds level-specific metadata and an ordered list of children.
- **`generator.py`** — `generate_node_hierarchy(seed, max_depth, min_breadth, max_breadth)`: builds the full tree deterministically. Named locations are sampled per level from curated pools; branching factor is randomized within bounds per node.

### `agents/` — Agent System

- **`behaviors.py`** — `State` enum (`IDLE`, `EXPLORE`, `INTERACT`, `EXIT`) and pure `transition(state, node)` function. Also exposes `should_avoid` and `should_interact` predicates.
- **`agent.py`** — `Agent` dataclass. Holds traversal state, a visited-node set, and a structured log. `traverse(root, max_nodes)` walks the tree depth-first, applying FSM transitions and recording actions.

**FSM transitions:**

```
IDLE ──► EXPLORE ──► INTERACT ──► EXPLORE
                 │
                 └──► EXIT  (dangerous node or dead-end locked room)
```

### `puzzles/` — Puzzle Engine

- **`types.py`** — `Puzzle` dataclass with `kind` (`RIDDLE`, `CIPHER`, `LOCK`, `SEQUENCE`), `attempt(guess)`, `hint()`, and result tracking (`UNSOLVED`, `SOLVED`, `FAILED`).
- **`engine.py`** — `PuzzleEngine`: attaches puzzle instances to `Room` nodes that carry `has_puzzle=True`; collects them back; provides `run_puzzle()` for interactive CLI play.

### `main.py` — CLI Entry Point

Three subcommands:

| Command | Description |
|---------|-------------|
| `python main.py world` | Print the generated world hierarchy |
| `python main.py agent` | Run an agent traversal and print its log |
| `python main.py puzzles` | Find and interactively play puzzles in the world |

All subcommands accept `--seed` for reproducibility.

### `tests/` — Test Suite

33 pytest tests across three modules:

- `test_generator.py` — determinism, breadth/depth bounds, property schemas
- `test_agent.py` — FSM transitions, avoidance, visit deduplication, report format
- `test_puzzles.py` — solve/fail/hint logic, case insensitivity, engine idempotency

## Data Flow

```
generate_node_hierarchy(seed)
        │
        ▼
    SpatialNode tree
        │
        ├──► Agent.traverse()  ──► AgentLog[]  ──► Agent.report()
        │
        └──► PuzzleEngine.attach_puzzles()
                    │
                    ▼
             PuzzleEngine.collect_puzzles()
                    │
                    ▼
             PuzzleEngine.run_puzzle()  ──► PuzzleResult
```
