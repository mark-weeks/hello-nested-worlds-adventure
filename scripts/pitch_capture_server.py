#!/usr/bin/env python3
"""Run an isolated seed-382 server for the reproducible pitch capture.

This is intentionally not a general development server.  It redirects the
materialized store to a caller-supplied temporary database, selects one real
launch-world puzzle for the cascade shot, and schedules one deterministic
ambient heartbeat in the same process so its live room broadcasts reach the
browser being captured.
"""
from __future__ import annotations

import argparse
import json
import random
import threading
import time
from pathlib import Path

import persistence
from multiverse.generator import generate_node_hierarchy
from multiverse.store import GENERATOR_VERSION
from puzzles.generators import build_puzzle


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _write_manifest(path: Path, seed: int) -> None:
    root = generate_node_hierarchy(seed=seed)
    candidates = []
    for node in _walk(root):
        if node.level != "Region":
            continue
        puzzle = build_puzzle(node)
        if puzzle.name.startswith(("The Keeper Witness", "The Ancestral Compass")):
            candidates.append((node, puzzle))
    if not candidates:
        raise RuntimeError("launch world has no world-reading Region puzzle")
    node, puzzle = candidates[0]
    path.write_text(json.dumps({
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "cascade_node": node.name,
        "cascade_level": node.level,
        "cascade_puzzle": puzzle.name,
        "cascade_puzzle_kind": puzzle.kind.name,
        "cascade_puzzle_difficulty": puzzle.difficulty,
        "cascade_answer": puzzle.answer,
    }, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--heartbeat-summary", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8299)
    parser.add_argument("--heartbeat-delay", type=float, default=25.0)
    args = parser.parse_args()

    # Redirect before the first persistence operation.  The capture may solve
    # puzzles and leave agent traces, but all of it lives in this disposable DB.
    persistence._DB_PATH = args.database
    # This capture is provenance for the selected launch world, not whichever
    # local-development default a future branch happens to choose.
    seed = 382
    _write_manifest(args.manifest, seed)

    from server import heartbeat

    # The production pump checks every five seconds.  Pitch capture preserves
    # the same durable queue and dampening physics while polling it faster so a
    # ring-by-ring GIF does not take a minute to record.
    heartbeat._PUMP_INTERVAL = 0.4

    def demo_heartbeat() -> None:
        time.sleep(args.heartbeat_delay)
        summary = heartbeat.run_tick(
            seed=seed,
            rng=random.Random(2),  # Tessera, reproducibly
            max_nodes=10,
            pace=0.8,
        )
        args.heartbeat_summary.write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )

    threading.Thread(target=demo_heartbeat, daemon=True,
                     name="pitch-heartbeat").start()

    import server
    server.run(host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
