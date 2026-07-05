from __future__ import annotations

import time

import causality
import persistence
from causality import CausalityBus, EventKind
from causality.wiring import wire_world_handlers
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.utils import (
    apply_property_overrides, apply_ripple_scores, build_distance_map,
)
from puzzles.engine import PuzzleEngine
from puzzles.types import PuzzleResult
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


def _passage_tags(node: SpatialNode) -> list[str]:
    """What is worth knowing about a passage BEFORE stepping through it.

    Only non-ubiquitous, mechanically meaningful traits are tagged (every
    node has a puzzle, so that would say nothing). Mirrors the browser
    clients' passage badges.
    """
    p = node.properties
    tags: list[str] = []
    danger = p.get("danger_level")
    if isinstance(danger, int) and danger >= 7:
        tags.append(f"danger {danger}")
    if p.get("condition") == "corrupted":
        tags.append("corrupted")
    if p.get("disturbed"):
        tags.append("disturbed")
    if p.get("stabilized"):
        tags.append("stabilized")
    if node.ripple_score >= 0.3:
        tags.append("≈ pressure")
    if p.get("locked"):
        tags.append("locked")
    return tags


def _print_look(node: SpatialNode) -> None:
    from multiverse.verbs import verb_for_level

    print(f"\n{_fmt(node)}")
    if node.properties:
        for k, v in node.properties.items():
            print(f"  {_DIM}{k}{_RESET}  {v}")
    verb = verb_for_level(node.level)
    if verb is not None:
        print(f"\n  {_DIM}Here you can{_RESET} {_BOLD}{verb.name}{_RESET}"
              f" {_DIM}— {verb.tagline}{_RESET}")
    if node.children:
        print(f"\n  {len(node.children)} path(s) deeper:")
        for i, child in enumerate(node.children, 1):
            tags = _passage_tags(child)
            suffix = f"  {_DIM}— {' · '.join(tags)}{_RESET}" if tags else ""
            print(f"  [{i}] {_fmt(child)}{suffix}")
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


def _ambient_mode(node: SpatialNode, seed: int) -> None:
    print(f"\n{_DIM}Entering ambient observation. An agent moves through the world…{_RESET}\n")
    print(f"  {'Node':<30}  {'Event':<22}  {'Strength'}")
    print(f"  {_DIM}{'─'*30}  {'─'*22}  {'─'*20}{_RESET}")

    def _handler(n: SpatialNode, event: causality.CausalEvent) -> None:
        style = _LEVEL_STYLES.get(n.level, "")
        kind = event.kind.name.replace("_", " ").lower()
        # The bar shows the event's REAL propagated strength — what the
        # engine computed, not a display-side function of tree depth.
        strength = event.strength
        filled = max(1, round(strength * 20))
        bar = "█" * filled + _DIM + "░" * (20 - filled) + _RESET
        print(f"  {style}{n.name:<30}{_RESET}  {kind:<22}  {bar}  {strength:.2f}")
        time.sleep(0.04)

    # Ambient observation is part of the shared world: the observer's
    # events persist (history, ripple, effects) exactly as they do on the
    # server, so what you watched happen genuinely happened.
    bus = CausalityBus()
    bus.register_handler(_handler)
    wire_world_handlers(bus, seed)
    agent = Agent(name="Observer", danger_threshold=7, bus=bus)
    agent.traverse(node, max_nodes=40)
    print(f"\n{_DIM}Observer visited {len(agent.visited)} node(s). Press Enter to continue.{_RESET}")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


def _play_puzzle(node: SpatialNode, seed: int) -> None:
    engine = PuzzleEngine(seed=seed)
    engine.attach_puzzles(node)
    puzzle = engine.puzzle_for(node)
    if puzzle is None:
        print("  No puzzle here.")
        return
    result = engine.run_puzzle(puzzle)

    # A CLI solve is a real solve: it persists and cascades exactly like a
    # browser solve. The origin settles immediately; the rest of the cascade
    # rides the causal queue and arrives ring by ring (fired by the server's
    # causal pump), so the consequence travels outward over real time.
    if result == PuzzleResult.SOLVED:
        from causality.staging import stage_cascade
        persistence.save_puzzle_result(seed, puzzle.name, result.name, puzzle.attempts)
        # record=False below: this row is the canonical origin record.
        persistence.record_mutation(
            seed, node.name, "PUZZLE_SOLVED", None, {"puzzle": puzzle.name})
        bus = wire_world_handlers(CausalityBus(), seed, record=False)
        bus.emit(node, EventKind.PUZZLE_SOLVED, {"puzzle": puzzle.name})
        staged = stage_cascade(seed, node, EventKind.PUZZLE_SOLVED,
                               {"puzzle": puzzle.name})
        print(f"  {_DIM}The place settles. {staged} consequence(s) are "
              f"already traveling outward.{_RESET}")
    elif result == PuzzleResult.FAILED:
        persistence.record_mutation(
            seed, node.name, "PUZZLE_FAILED", None, {"puzzle": puzzle.name})


def _do_scale_verb(node: SpatialNode, seed: int,
                   player_name: str | None = None) -> None:
    """Perform this scale's native verb — the CLI mirror of POST /act."""
    from causality.staging import stage_cascade
    from multiverse.verbs import apply_verb, verb_for_level

    verb = verb_for_level(node.level)
    if verb is None:
        print("  Nothing can be done at this scale.")
        return
    token = f"{player_name or 'traveler'}:{node.name}"
    changed, flavor = apply_verb(node, verb, token)
    print(f"\n  {_BOLD}{verb.name}{_RESET} — {flavor}\n")
    if not changed:
        return
    persistence.upsert_node_properties(seed, node.name, changed)
    # Local play has no credential; the display name is the identity.
    # record=False below: this row is the canonical origin record.
    persistence.record_mutation(
        seed, node.name, "SCALE_ACT", player_name,
        {"verb": verb.name, "changed": changed},
        actor_identity=player_name)
    payload = {"verb": verb.name}
    if player_name:
        payload["actor"] = player_name
    bus = wire_world_handlers(CausalityBus(), seed, record=False)
    bus.emit(node, EventKind.SCALE_ACT, payload)
    staged = stage_cascade(seed, node, EventKind.SCALE_ACT, payload)
    if staged:
        print(f"  {_DIM}The act echoes — {staged} consequence(s) are "
              f"traveling outward.{_RESET}\n")


def _speak_to(node: SpatialNode, message: str, seed: int = 0,
              player_name: str | None = None) -> None:
    print(f"\n{_fmt(node)} responds…\n")
    try:
        import consciousness
    except ImportError:
        print(f"  {_DIM}(The worlds are silent — install the 'anthropic' package to hear them.){_RESET}\n")
        return
    history = persistence.get_node_history(seed, node.name)
    transcript = persistence.get_player_exchanges(seed, node.name, player_name)
    try:
        response = consciousness.speak(
            node, message,
            history=history,
            transcript=transcript,
            ripple_score=persistence.get_ripple_score(seed, node.name),
        )
        print(f"  {response}\n")
        # Local sessions have no invite credential; the display name IS the
        # conversation identity (see persistence.get_player_exchanges).
        data = {"message": message[:128], "reply": response[:200]}
        if player_name:
            data["identity"] = player_name
        persistence.record_mutation(
            seed, node.name, "PLAYER_SPEAK", player_name, data,
            actor_identity=player_name,
        )
    except Exception:
        # The world goes quiet in character. Never an SDK error, never a
        # billing warning — an authored silence in the node's register.
        print(f"  {consciousness.fallback_voice(node)}\n")
        if not _speak_to._hinted:
            print(f"  {_DIM}(The voices need ANTHROPIC_API_KEY to wake.){_RESET}\n")
            _speak_to._hinted = True


_speak_to._hinted = False


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
  act  /  a             perform this scale's native verb
                        (or type the verb itself: mend, ward, kindle…)
  help  /  h            show this help
  quit  /  q            exit the session
  {_DIM}(unrecognised input is sent as a speak message){_RESET}
"""


def run_session(seed: int = 42, depth: int = 6,
                min_breadth: int = 1, max_breadth: int = 3,
                player_name: str | None = None) -> None:
    """Launch an interactive terminal session in the nested worlds."""
    print(f"\n{_BOLD}Enfolded: Nested World Adventure{_RESET}")
    print(f"{_DIM}seed={seed}  depth={depth}  breadth={min_breadth}–{max_breadth}{_RESET}")
    print("Generating world…", end=" ", flush=True)
    root = generate_node_hierarchy(
        seed=seed, max_depth=depth,
        min_breadth=min_breadth, max_breadth=max_breadth,
    )
    # Hydrate the world's persisted evolution: what other participants have
    # done here — ripple pressure and property changes — is already true
    # when a CLI player arrives.
    apply_ripple_scores(root, persistence.load_ripple_scores(seed))
    apply_property_overrides(root, persistence.load_node_property_overrides(seed))
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
            _speak_to(stack[-1], msg, seed=seed, player_name=player_name)

        elif cmd in ("observe", "o"):
            _ambient_mode(stack[-1], seed)

        elif cmd in ("puzzle", "p"):
            _play_puzzle(stack[-1], seed)

        elif cmd in ("act", "a"):
            _do_scale_verb(stack[-1], seed, player_name=player_name)

        elif cmd in ("go", "g"):
            if not rest.isdigit():
                print("  Usage: go <N>")
                continue
            _descend(stack, int(rest))

        elif cmd.isdigit():
            _descend(stack, int(cmd))

        else:
            # Typing the scale's own verb ("mend" at an Object, "observe"
            # at a particle…) performs it; anything else is speech.
            from multiverse.verbs import verb_for_level
            _verb = verb_for_level(stack[-1].level)
            if _verb is not None and cmd == _verb.name and not rest:
                _do_scale_verb(stack[-1], seed, player_name=player_name)
            else:
                _speak_to(stack[-1], raw, seed=seed, player_name=player_name)


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
