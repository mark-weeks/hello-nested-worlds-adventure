#!/usr/bin/env python3
"""Evaluate task configurations without touching the continuing world."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse

from evals.harness import ROOT, TASKS, load_corpus, read_json, run, write_json
from evals.reporting import calibration, checked_run, compare, load_review, report, review_packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--corpus", type=Path, default=ROOT / "evals/corpus.json")
    execute = commands.add_parser("run")
    execute.add_argument("--corpus", type=Path, default=ROOT / "evals/corpus.json")
    execute.add_argument("--candidate", type=Path, default=ROOT / "evals/candidates/fixture.json")
    execute.add_argument("--output", type=Path, required=True)
    execute.add_argument("--split", choices=("development", "holdout"), default="development")
    execute.add_argument("--task", action="append", choices=TASKS)
    execute.add_argument("--repeats", type=int, default=3)
    execute.add_argument("--seed", type=int, default=0)
    execute.add_argument("--live", action="store_true")
    execute.add_argument("--max-usd", type=float)
    execute.add_argument("--max-calls", type=int)
    execute.add_argument("--brief", type=Path)
    review = commands.add_parser("review")
    review.add_argument("run", type=Path)
    review.add_argument("--corpus", type=Path)
    review.add_argument("--output", type=Path, required=True)
    summary = commands.add_parser("report")
    summary.add_argument("run", type=Path)
    summary.add_argument("--review", type=Path)
    summary.add_argument("--key", type=Path)
    paired = commands.add_parser("compare")
    paired.add_argument("baseline", type=Path)
    paired.add_argument("candidate", type=Path)
    paired.add_argument("--baseline-review", type=Path)
    paired.add_argument("--baseline-key", type=Path)
    paired.add_argument("--candidate-review", type=Path)
    paired.add_argument("--candidate-key", type=Path)
    paired.add_argument("--output", type=Path, required=True)
    calibrate = commands.add_parser("calibrate")
    calibrate.add_argument("run", type=Path)
    calibrate.add_argument("--human", type=Path, required=True)
    calibrate.add_argument("--judge", type=Path, required=True)
    calibrate.add_argument("--key", type=Path, required=True)
    calibrate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            corpus = load_corpus(args.corpus)
            print(f"{corpus['version']}: {len(corpus['cases'])} valid synthetic cases")
        elif args.command == "run":
            result = run(load_corpus(args.corpus), read_json(args.candidate), args.output,
                         split=args.split, repeats=args.repeats, seed=args.seed,
                         tasks=args.task or TASKS, live=args.live,
                         max_usd=args.max_usd, max_calls=args.max_calls,
                         brief=read_json(args.brief) if args.brief else None)
            text, data = report(result)
            (args.output / "report.md").write_text(text, encoding="utf-8")
            write_json(args.output / "summary.json", data)
            print(f"{result['status']}: {len(result['trials'])}/{result['planned_trials']} trials; {args.output}")
            return 0 if result["status"] == "completed" else 2
        elif args.command == "review":
            review_packet(checked_run(args.run), load_corpus(args.corpus or args.run.parent / "corpus.json"),
                          args.output, rubric=read_json(args.run.parent / "rubric.json"))
            print(f"Blind packet: {args.output / 'review.json'}; keep key.json separate")
        elif args.command == "report":
            result = checked_run(args.run)
            text, data = report(result, load_review(result, args.review, args.key))
            (args.run.parent / "report.md").write_text(text, encoding="utf-8")
            write_json(args.run.parent / "summary.json", data)
            print(text)
        elif args.command == "compare":
            left, right = checked_run(args.baseline), checked_run(args.candidate)
            write_json(args.output, compare(left, right,
                load_review(left, args.baseline_review, args.baseline_key),
                load_review(right, args.candidate_review, args.candidate_key)))
        elif args.command == "calibrate":
            result = checked_run(args.run)
            human = load_review(result, args.human, args.key)
            judge = load_review(result, args.judge, args.key, allow_model=True)
            if not judge or any(g["kind"] != "model" for g in judge.values()):
                raise ValueError("judge grades must identify kind=model")
            write_json(args.output, calibration(human, judge))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Evaluation stopped: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
