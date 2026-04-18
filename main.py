# main.py

import argparse
from multiverse.generator import generate_node_hierarchy
from agents.agent import Agent
from puzzles.engine import PuzzleEngine


def cmd_world(args):
    root = generate_node_hierarchy(
        seed=args.seed,
        max_depth=args.depth,
        min_breadth=args.min_breadth,
        max_breadth=args.max_breadth,
    )
    print(root)


def cmd_agent(args):
    root = generate_node_hierarchy(seed=args.seed)
    agent = Agent(name=args.name, danger_threshold=args.danger_threshold)
    agent.traverse(root, max_nodes=args.max_nodes)
    print(agent.report())


def cmd_puzzles(args):
    root = generate_node_hierarchy(seed=args.seed)
    engine = PuzzleEngine(seed=args.seed)
    engine.attach_puzzles(root)
    puzzles = engine.collect_puzzles(root)

    if not puzzles:
        print("No puzzles found in this world. Try a different seed.")
        return

    print(f"Found {len(puzzles)} puzzle(s) in this world.\n")
    for puzzle in puzzles:
        engine.run_puzzle(puzzle)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="hello-nested-worlds-adventure: multiverse simulation engine",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    sub = parser.add_subparsers(dest="command", required=True)

    # world subcommand
    p_world = sub.add_parser("world", help="Generate and print the world hierarchy")
    p_world.add_argument("--depth", type=int, default=10, help="Max hierarchy depth (default: 10)")
    p_world.add_argument("--min-breadth", type=int, default=1, dest="min_breadth")
    p_world.add_argument("--max-breadth", type=int, default=3, dest="max_breadth")
    p_world.set_defaults(func=cmd_world)

    # agent subcommand
    p_agent = sub.add_parser("agent", help="Run an agent traversal of the world")
    p_agent.add_argument("--name", type=str, default="Scout", help="Agent name (default: Scout)")
    p_agent.add_argument("--danger-threshold", type=int, default=6, dest="danger_threshold",
                         help="Avoid regions with danger_level above this (default: 6)")
    p_agent.add_argument("--max-nodes", type=int, default=50, dest="max_nodes",
                         help="Max nodes to visit (default: 50)")
    p_agent.set_defaults(func=cmd_agent)

    # puzzles subcommand
    p_puzzles = sub.add_parser("puzzles", help="Find and play puzzles in the world")
    p_puzzles.set_defaults(func=cmd_puzzles)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
