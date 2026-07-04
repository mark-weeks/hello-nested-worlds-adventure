from __future__ import annotations

import time

import causality
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.utils import build_depth_map
from puzzles.engine import PuzzleEngine
from agents.agent import Agent

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"

_LEVEL_STYLES: dict[str, str] = {
    "Multiverse":        "\033[1;97m",
    "Universe":          "\033[1;36m",
    "Galaxy":            "\033[1;34m",
    "Planetary System":  "\033[1;35m",
    "Planet":            "\033[1;32m",
    "Region":            "\033[1;33m",
    "Room":              "\033[1;31m",
    "Object":            "\033[0;37m",
    "Molecule":          "\033[0;36m",
    "Atom":              "\033[0;34m",
    "SubatomicParticle": "\033[0;35m",
}


def _style(node: SpatialNode) -> str:
    return _LEVEL_STYLES.get(node.level, "")


def _fmt(node: SpatialNode) -> str:
    return f"{_style(node)}{node.level}: {node.name}{_RESET}"


def _divider(width: int = 60) -> str:
    return _DIM + "─" * width + _RESET


def _print_breadcrumb(stack: list[SpatialNode]) -> None:
    path = " → ".join(f"{_style(n)}{n.name}{_RESET}" for n in stack)
    print(f"\n{_divider()}")
    print(f"  {path}")
    print(_divider())


def _print_look(node: SpatialNode) -> None:
    print(f"\n{_fmt(node)}")
    if node.properties:
        for k, v in node.properties.items():
            print(f"  {_DIM}{k}{_RESET}  {v}")
    if node.children:
        print(f"\n  {len(node.children)} path(s) deeper:")
        for i, child in enumerate(node.children, 1):
            print(f"  [{i}] {_fmt(child)}")
    else:
        print(f"\n  {_DIM}(leaf node — no deeper paths){_RESET}")


def _print_map(node: SpatialNode, prefix: str = "", is_last: bool = True,
               depth: int = 0, max_depth: int = 3) -> None:
    connector = ("└─ " if is_last else "├─ ") if depth > 0 else ""
    print(f"{prefix}{connector}{_fmt(node)}")
    if not node.children:
        return
    child_prefix = (prefix + ("   " if is_last else "│  ")) if depth > 0 else ""
    if depth < max_depth:
        for i, child in enumerate(node.children):
            _print_map(child, child_prefix, i == len(node.children) - 1, depth + 1, max_depth)
    else:
        count = len(node.children)
        print(f"{child_prefix}└─ {_DIM}… ({count} child{'ren' if count != 1 else ''}){_RESET}")


_AMBIENT_DAMPENING = causality.DAMPENING


def _ambient_mode(node: SpatialNode) -> None:
    print(f"\n{_DIM}Entering ambient observation. An agent moves through the world…{_RESET}\n")
    print(f"  {'Node':<30}  {'Event':<22}  {'Strength'}")
    print(f"  {_DIM}{'─'*30}  {'─'*22}  {'─'*20}{_RESET}")

    depth_map = build_depth_map(node)

    def _handler(n: SpatialNode, event: causality.CausalEvent) -> None:
        style = _LEVEL_STYLES.get(n.level, "")
        kind = event.kind.name.replace("_", " ").lower()
        depth = depth_map.get(n.id, 0)
        strength = _AMBIENT_DAMPENING ** depth
        filled = max(1, round(strength * 20))
        bar = "█" * filled + _DIM + "░" * (20 - filled) + _RESET
        print(f"  {style}{n.name:<30}{_RESET}  {kind:<22}  {bar}  {strength:.2f}")
        time.sleep(0.04)

    bus = causality.CausalityBus()
    bus.register_handler(_handler)
    agent = Agent(name="Observer", danger_threshold=7, bus=bus)
    agent.traverse(node, max_nodes=40)
    print(f"\n{_DIM}Observer visited {len(agent.visited)} node(s). Press Enter to continue.{_RESET}")
    input()


def _play_puzzle(node: SpatialNode, seed: int) -> None:
    engine = PuzzleEngine(seed=seed)
    engine.attach_puzzles(node)
    puzzles = engine.collect_puzzles(node)
    engine.run_puzzle(puzzles[0])


def _speak_to(node: SpatialNode, message: str, seed: int = 0) -> None:
    try:
        import consciousness
    except ImportError:
        print(f"\n  {_DIM}Consciousness module requires: pip install anthropic{_RESET}\n")
        return
    print(f"\n{_fmt(node)} responds…\n")
    try:
        history = []
        if seed:
            import persistence
            history = persistence.get_node_history(seed, node.name)
        response = consciousness.speak(node, message, history=history)
        print(f"  {response}\n")
        if seed:
            import persistence
            persistence.record_mutation(
                seed, node.name, "PLAYER_SPEAK", None, {"message": message[:128]},
            )
    except Exception as exc:
        print(f"  Error: {exc}\n  Ensure ANTHROPIC_API_KEY is set.\n")


_HELP = f"""
  {_BOLD}Commands{_RESET}
  ──────────────────────────────────────────────
  look  /  l            describe current location
  go <N>  /  <N>        descend into child node N
  up  /  u              return to parent
  map  /  m             show local map (3 levels deep)
  speak [msg]  /  s     speak to this node via Claude
  observe  /  o         watch an agent traverse from here
  puzzle  /  p          find and play a puzzle here
  help  /  h            show this help
  quit  /  q            exit the session
  {_DIM}(unrecognised input is sent as a speak message){_RESET}
"""


def run_session(seed: int = 42, depth: int = 6,
                min_breadth: int = 1, max_breadth: int = 3) -> None:
    """Launch an interactive terminal session in the nested worlds."""
    print(f"\n{_BOLD}Enfolded: Nested World Adventure{_RESET}")
    print(f"{_DIM}seed={seed}  depth={depth}  breadth={min_breadth}–{max_breadth}{_RESET}")
    print("Generating world…", end=" ", flush=True)
    root = generate_node_hierarchy(
        seed=seed, max_depth=depth,
        min_breadth=min_breadth, max_breadth=max_breadth,
    )
    print("done.\n")
    print(f"Type {_BOLD}help{_RESET} to see available commands.\n")

    stack: list[SpatialNode] = [root]
    _print_look(stack[-1])

    while True:
        try:
            raw = input(f"\n{_style(stack[-1])}{stack[-1].name}>{_RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nFarewell.")
            break

        if not raw:
            continue

        parts = raw.split(None, 1)
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "q", "exit"):
            print("Farewell.")
            break

        elif cmd in ("help", "h"):
            print(_HELP)

        elif cmd in ("look", "l"):
            _print_breadcrumb(stack)
            _print_look(stack[-1])

        elif cmd in ("up", "u"):
            if len(stack) > 1:
                stack.pop()
                _print_breadcrumb(stack)
                _print_look(stack[-1])
            else:
                print("  You are at the root of the multiverse.")

        elif cmd in ("map", "m"):
            print()
            _print_map(stack[-1])

        elif cmd in ("speak", "s"):
            msg = rest or "Describe yourself to a traveler who has just arrived."
            _speak_to(stack[-1], msg, seed=seed)

        elif cmd in ("observe", "o"):
            _ambient_mode(stack[-1])

        elif cmd in ("puzzle", "p"):
            _play_puzzle(stack[-1], seed)

        elif cmd in ("go", "g"):
            if not rest.isdigit():
                print("  Usage: go <N>")
                continue
            _descend(stack, int(rest))

        elif cmd.isdigit():
            _descend(stack, int(cmd))

        else:
            _speak_to(stack[-1], raw, seed=seed)


def _descend(stack: list[SpatialNode], n: int) -> None:
    node = stack[-1]
    if not node.children:
        print("  No deeper paths from here.")
        return
    idx = n - 1
    if 0 <= idx < len(node.children):
        stack.append(node.children[idx])
        _print_breadcrumb(stack)
        _print_look(stack[-1])
    else:
        print(f"  No path {n}. Choose 1–{len(node.children)}.")
