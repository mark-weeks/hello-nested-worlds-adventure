#!/usr/bin/env python3
"""Audit the unborn launch world's puzzle ecology.

Examples:
  python scripts/puzzle_quality.py
  python scripts/puzzle_quality.py --seed 382 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from multiverse.generator import DEFAULT_WORLD_SEED  # noqa: E402
from puzzles.quality import audit_puzzles  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_WORLD_SEED,
                        help=f"world seed to audit (default: {DEFAULT_WORLD_SEED})")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON")
    args = parser.parse_args()
    result = audit_puzzles(args.seed)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if result["passed"] else "FAIL"
        metrics = result["metrics"]
        print(
            f"{status} seed={result['seed']} puzzles={result['puzzle_count']} "
            f"decode={metrics['decode_family_ratio']:.2%} "
            f"world-reading={metrics['world_reading_family_ratio']:.2%} "
            f"prompts={metrics['unique_prompt_ratio']:.2%} "
            f"answers={metrics['unique_answer_ratio']:.2%} "
            f"largest-family={metrics['largest_family_ratio']:.2%}"
        )
        for family, count in result["family_counts"].items():
            print(f"  {family}: {count}")
        for failure in result["failures"]:
            print(f"  - {failure}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
