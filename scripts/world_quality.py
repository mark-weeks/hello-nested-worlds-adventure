#!/usr/bin/env python3
"""Audit or rank unborn worlds against the pre-launch quality gate.

Examples:
  python scripts/world_quality.py --seed 382
  python scripts/world_quality.py --candidates 512 --top 10
  python scripts/world_quality.py --candidates 512 --top 10 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from multiverse.generator import DEFAULT_WORLD_SEED  # noqa: E402
from multiverse.quality import audit_world  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--seed", type=int, default=DEFAULT_WORLD_SEED,
                      help=f"audit one seed (default: {DEFAULT_WORLD_SEED})")
    mode.add_argument("--candidates", type=int,
                      help="rank seeds 1 through N")
    parser.add_argument("--top", type=int, default=10,
                        help="number of candidates to show (default: 10)")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON")
    return parser


def _line(result: dict) -> str:
    status = "PASS" if result["passed"] else "FAIL"
    metrics = result["metrics"]
    return (
        f"{status} seed={result['seed']} score={result['comparison_score']:.4f} "
        f"nodes={result['node_count']} readable={metrics['readable_name_ratio']:.2%} "
        f"names={metrics['unique_base_name_ratio']:.2%} "
        f"siblings={metrics['sibling_signature_ratio']:.2%} "
        f"categories={metrics['categorical_coverage_ratio']:.2%} "
        f"branching={metrics['branching_coverage_ratio']:.2%}"
    )


def main() -> int:
    args = _parser().parse_args()
    if args.candidates is not None:
        if args.candidates < 1:
            raise SystemExit("--candidates must be at least 1")
        results = [audit_world(seed) for seed in range(1, args.candidates + 1)]
        # Equal-quality worlds prefer the smaller payload: cheaper to birth,
        # transmit, render, and keep active without sacrificing experience.
        results.sort(key=lambda item: (
            item["passed"], item["comparison_score"], -item["node_count"]
        ), reverse=True)
        shown = results[:max(1, args.top)]
        payload: object = {
            "candidate_count": args.candidates,
            "passing_count": sum(item["passed"] for item in results),
            "top": shown,
        }
    else:
        payload = audit_world(args.seed)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.candidates is not None:
        print(f"{payload['passing_count']}/{payload['candidate_count']} candidates pass")
        for result in payload["top"]:
            print(_line(result))
    else:
        print(_line(payload))
        for name in payload["sample_names"]:
            print(f"  {name}")
        for failure in payload["failures"]:
            print(f"  - {failure}")
    if args.candidates is not None:
        return 0 if payload["passing_count"] else 1
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
