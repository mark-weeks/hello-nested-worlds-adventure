import argparse

import persistence
from agents.agent import Agent
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.utils import _count_nodes, _find_node
from puzzles.engine import PuzzleEngine


def cmd_world(args):
    root = generate_node_hierarchy(
        seed=args.seed,
        max_depth=args.depth,
        min_breadth=args.min_breadth,
        max_breadth=args.max_breadth,
    )
    print(root)
    node_count = _count_nodes(root)
    persistence.save_world(args.seed, node_count, args.depth, args.min_breadth, args.max_breadth)
    print(f"[Saved: seed={args.seed}, {node_count} nodes]")


def cmd_agent(args):
    root = generate_node_hierarchy(seed=args.seed)
    agent = Agent(name=args.name, danger_threshold=args.danger_threshold)
    agent.traverse(root, max_nodes=args.max_nodes)
    print(agent.report())
    events = [
        {"node": e.node_name, "level": e.level, "state": e.state.name, "action": e.action}
        for e in agent.log
    ]
    persistence.save_agent_run(args.name, args.seed, len(agent.visited), events)
    print(f"[Run saved: {len(agent.visited)} nodes visited]")


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
        persistence.save_puzzle_result(args.seed, puzzle.name, puzzle.result.name, puzzle.attempts)


def cmd_history(args):
    worlds = persistence.list_worlds()
    if not worlds:
        print("No worlds saved yet. Run the 'world' or 'agent' command to generate some.")
        return
    print(f"{'Seed':>8}  {'Saved':>20}  {'Nodes':>8}  {'Depth':>6}")
    print("-" * 50)
    for w in worlds:
        print(
            f"{w['seed']:>8}  {w['created_at']:>20}"
            f"  {str(w['node_count'] or '?'):>8}  {str(w['max_depth'] or '?'):>6}"
        )
        for r in persistence.get_agent_runs(w["seed"]):
            print(f"          agent '{r['agent_name']}' — {r['nodes_visited']} nodes  ({r['started_at']})")


def cmd_play(args):
    import interface
    interface.run_session(
        seed=args.seed,
        depth=args.depth,
        min_breadth=args.min_breadth,
        max_breadth=args.max_breadth,
    )


def cmd_serve(args):
    import server
    server.run(host=args.host, port=args.port)


def cmd_speak(args):
    try:
        import consciousness
    except ImportError:
        print("Consciousness module requires: pip install anthropic")
        return

    root = generate_node_hierarchy(seed=args.seed)
    target = _find_node(root, args.node) if args.node else root
    if target is None:
        print(f"Node '{args.node}' not found in seed={args.seed}. Run 'world' to see available nodes.")
        return

    print(f"\n[{target.level}: {target.name}]")
    try:
        print(consciousness.speak(target, args.message))
    except Exception as e:
        print(f"Error: {e}")
        print("Ensure ANTHROPIC_API_KEY is set in your environment.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Nested Worlds Adventure: shared persistent multiverse simulation",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_world = sub.add_parser("world", help="Generate and print the world hierarchy")
    p_world.add_argument("--depth", type=int, default=10, help="Max hierarchy depth (default: 10)")
    p_world.add_argument("--min-breadth", type=int, default=1, dest="min_breadth")
    p_world.add_argument("--max-breadth", type=int, default=3, dest="max_breadth")
    p_world.set_defaults(func=cmd_world)

    p_agent = sub.add_parser("agent", help="Run an agent traversal of the world")
    p_agent.add_argument("--name", type=str, default="Scout", help="Agent name (default: Scout)")
    p_agent.add_argument("--danger-threshold", type=int, default=6, dest="danger_threshold",
                         help="Self-preservation threshold: withdraw from nodes with danger_level above this (default: 6)")
    p_agent.add_argument("--max-nodes", type=int, default=50, dest="max_nodes",
                         help="Max nodes to visit (default: 50)")
    p_agent.set_defaults(func=cmd_agent)

    p_puzzles = sub.add_parser("puzzles", help="Find and play puzzles in the world")
    p_puzzles.set_defaults(func=cmd_puzzles)

    p_history = sub.add_parser("history", help="Show saved worlds and agent runs")
    p_history.set_defaults(func=cmd_history)

    p_play = sub.add_parser("play", help="Start an interactive session in the world")
    p_play.add_argument("--depth", type=int, default=6, help="Max hierarchy depth (default: 6)")
    p_play.add_argument("--min-breadth", type=int, default=1, dest="min_breadth")
    p_play.add_argument("--max-breadth", type=int, default=3, dest="max_breadth")
    p_play.set_defaults(func=cmd_play)

    p_serve = sub.add_parser("serve", help="Start the REST API server")
    p_serve.add_argument("--host", type=str, default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    p_serve.set_defaults(func=cmd_serve)

    p_speak = sub.add_parser("speak", help="Speak to a node using Claude consciousness")
    p_speak.add_argument("--node", type=str, default=None,
                         help="Node name to address (default: root of world)")
    p_speak.add_argument(
        "--message",
        type=str,
        default="Describe yourself to a traveler who has just arrived.",
        help="Message to send to the node",
    )
    p_speak.set_defaults(func=cmd_speak)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
