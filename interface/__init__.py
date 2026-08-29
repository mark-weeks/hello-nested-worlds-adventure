from __future__ import annotations

import time

import causality
import persistence
from causality import CausalityBus, EventKind
from causality.wiring import (
    record_origin_event, record_verb_act, wire_world_handlers,
)
from multiverse import store, wrap
from multiverse.generator import DEFAULT_WORLD_SEED
from multiverse.node import SpatialNode
from multiverse.utils import (
    apply_property_overrides, apply_ripple_scores, display_name, node_address,
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
    # Display layer: the readable phrase is what a player sees; the node's
    # address (its path digits) gets its own line in `look`, and the full
    # canonical name stays the identity everywhere data is keyed.
    return f"{_style(node)}{node.level}: {display_name(node.name)}{_RESET}"


def _divider(width: int = 60) -> str:
    return _DIM + "─" * width + _RESET


def _print_breadcrumb(stack: list[SpatialNode]) -> None:
    path = " → ".join(f"{_style(n)}{display_name(n.name)}{_RESET}" for n in stack)
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
    address = node_address(node.name)
    if address is not None:
        # The address field: the node's path from the root, kept visible
        # without riding the display name.
        print(f"  {_DIM}address{_RESET}  ⌖ {address}")
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
    elif wrap.wraps_inward(node):
        # The wrap passage (ADR-008): below the particle is the whole.
        print("\n  1 path(s) deeper:")
        print(f"  [1] {_DIM}{wrap.DESCENT_PASSAGE}{_RESET}")
    else:
        print(f"\n  {_DIM}(leaf node — no deeper paths){_RESET}")
    if wrap.wraps_outward(node) and node.parent is None:
        print(f"\n  {_DIM}Above, {wrap.ASCENT_PASSAGE} (type 'up').{_RESET}")


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
        print(f"  {style}{display_name(n.name):<30}{_RESET}  {kind:<22}  {bar}  {strength:.2f}")
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


def _play_puzzle(node: SpatialNode, seed: int,
                 player_name: str | None = None) -> None:
    engine = PuzzleEngine(seed=seed)
    engine.attach_puzzles(node, persistence.count_rearms_by_node(seed))
    puzzle = engine.puzzle_for(node)
    if puzzle is None:
        print("  No puzzle here.")
        return
    result = engine.run_puzzle(puzzle)

    # A CLI solve is a real solve: it persists and cascades exactly like a
    # browser solve. The origin settles immediately; the rest of the cascade
    # rides the causal queue and arrives ring by ring (fired by the server's
    # causal pump), so the consequence travels outward over real time.
    # The solve is recorded under the session's required --name (ADR-004 §7:
    # no session writes an unknown presence into the permanent chronicle) —
    # a nameless PUZZLE_SOLVED row would open seals and count as human
    # progress while being attributable to no one.
    if result == PuzzleResult.SOLVED:
        from causality.staging import stage_cascade
        persistence.save_puzzle_result(seed, puzzle.name, result.name, puzzle.attempts)
        # record=False below: this row is the canonical origin record. It
        # carries the origin event's strength and its material consequence,
        # computed against the live overlay under the write lock — row,
        # delta, and overlay change commit as one transaction.
        record_origin_event(
            seed, node, EventKind.PUZZLE_SOLVED, {"puzzle": puzzle.name},
            player_name=player_name, actor_identity=player_name)
        bus = wire_world_handlers(CausalityBus(), seed, record=False)
        bus.emit(node, EventKind.PUZZLE_SOLVED, {"puzzle": puzzle.name})
        staged = stage_cascade(seed, node, EventKind.PUZZLE_SOLVED,
                               {"puzzle": puzzle.name})
        print(f"  {_DIM}The place settles. {staged} consequence(s) are "
              f"already traveling outward.{_RESET}")
    elif result == PuzzleResult.FAILED:
        persistence.record_mutation(
            seed, node.name, "PUZZLE_FAILED", player_name,
            {"puzzle": puzzle.name}, actor_identity=player_name)


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
    base_props = dict(node.properties)
    changed, flavor = apply_verb(node, verb, token)
    matures = 0.0
    if changed:
        from multiverse.verbs import maturation_note, maturation_seconds
        matures = maturation_seconds(node.level)
        if matures > 0:
            flavor += maturation_note(matures)
    print(f"\n  {_BOLD}{verb.name}{_RESET} — {flavor}\n")
    if not changed:
        return
    # Local play has no credential; the display name is the identity.
    # record=False below: this row is the canonical origin record and
    # carries the origin event's strength.
    if matures > 0:
        # Deep time: the change is planted, not applied — it rides the
        # maturation queue and its delta is chronicled when it lands.
        persistence.enqueue_verb_maturation(
            seed, node.name, verb.name, changed, player_name, matures)
        persistence.record_mutation(
            seed, node.name, "SCALE_ACT", player_name,
            {"verb": verb.name, "changed": changed,
             "matures_in": int(matures)},
            actor_identity=player_name,
            strength=causality.ORIGIN_STRENGTH)
    else:
        # One transaction: the attributed SCALE_ACT row + overlay change,
        # the verb's transition re-derived against the live overlay under
        # the lock (the delta column carries what changed).
        record_verb_act(
            seed, node, verb, token, base_props, {"verb": verb.name},
            player_name=player_name, actor_identity=player_name)
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
            hinge=wrap.is_hinge(seed, node.name),
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


def run_session(seed: int = DEFAULT_WORLD_SEED, depth: int = 6,
                player_name: str | None = None) -> None:
    """Launch an interactive terminal session in the nested worlds."""
    print(f"\n{_BOLD}Enfolded: Nested World Adventure{_RESET}")
    print(f"{_DIM}seed={seed}  depth={depth}{_RESET}")
    print("Generating world…", end=" ", flush=True)
    root = store.world_tree(seed=seed, max_depth=depth)
    # Hydrate the world's persisted evolution: what other participants have
    # done here — ripple pressure and property changes — is already true
    # when a CLI player arrives.
    apply_ripple_scores(root, persistence.load_ripple_scores(seed))
    apply_property_overrides(root, persistence.load_node_property_overrides(seed))
    print("done.\n")
    print(f"Type {_BOLD}help{_RESET} to see available commands.\n")

    _session_crossings.clear()  # each session's first crossing gets the line
    stack: list[SpatialNode] = [root]
    _print_look(stack[-1])

    while True:
        try:
            raw = input(f"\n{_style(stack[-1])}{display_name(stack[-1].name)}>{_RESET} ").strip()
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
                # The wrap passage (ADR-008): ascending beyond the root
                # lands at the world's one hinge particle.
                _wrap_ascend(stack, seed, player_name=player_name)

        elif cmd in ("map", "m"):
            print()
            _print_map(stack[-1])

        elif cmd in ("speak", "s"):
            msg = rest or "Describe yourself to a traveler who has just arrived."
            _speak_to(stack[-1], msg, seed=seed, player_name=player_name)

        elif cmd in ("observe", "o"):
            _ambient_mode(stack[-1], seed)

        elif cmd in ("puzzle", "p"):
            _play_puzzle(stack[-1], seed, player_name=player_name)

        elif cmd in ("act", "a"):
            _do_scale_verb(stack[-1], seed, player_name=player_name)

        elif cmd in ("go", "g"):
            if not rest.isdigit():
                print("  Usage: go <N>")
                continue
            _descend(stack, int(rest), seed, player_name=player_name)

        elif cmd.isdigit():
            _descend(stack, int(cmd), seed, player_name=player_name)

        else:
            # Typing the scale's own verb ("mend" at an Object, "observe"
            # at a particle…) performs it; anything else is speech.
            from multiverse.verbs import verb_for_level
            _verb = verb_for_level(stack[-1].level)
            if _verb is not None and cmd == _verb.name and not rest:
                _do_scale_verb(stack[-1], seed, player_name=player_name)
            else:
                _speak_to(stack[-1], raw, seed=seed, player_name=player_name)


# The authored crossing lines are spoken once per session per direction —
# after the first crossing, the passage is simply a way you know.
_session_crossings: set[str] = set()


def _announce_crossing(direction: str, line: str) -> None:
    if direction not in _session_crossings:
        _session_crossings.add(direction)
        print(f"\n  {line}")


def _wrap_descend(stack: list[SpatialNode], seed: int,
                  player_name: str | None = None) -> None:
    """Cross the wrap inward: below this particle is the whole.

    The transit runs through the standard seal gate like every other
    move (trivially open — nothing seals the root — but the routing is
    the rule, not an optimization).
    """
    from puzzles.gates import seal_check
    root = stack[0]
    if seal_check(seed, root, current_name=stack[-1].name) is not None:
        print("  The way holds shut.")  # unreachable while nothing seals the root
        return
    del stack[1:]
    # A crossing is a move like any other in the chronicle (ADR-008):
    # recorded only after the gate passes and the landing succeeds, so
    # CLI crossings leave the same permanent trace browser crossings do.
    persistence.record_mutation(seed, root.name, "PLAYER_MOVE", player_name,
                                {}, actor_identity=player_name)
    _announce_crossing("inward", wrap.DESCENT_LINE)
    _print_breadcrumb(stack)
    _print_look(stack[-1])


def _wrap_ascend(stack: list[SpatialNode], seed: int,
                 player_name: str | None = None) -> None:
    """Cross the wrap outward: beyond the root is the hinge particle.

    The hinge's lineage is unsealed by the liveness invariant (its
    selection excludes any lineage under a locked Room), but the transit
    still runs through the standard seal gate — a hinge must never
    become a wormhole past a lock, whatever the world becomes.
    """
    from puzzles.gates import seal_check
    hinge = wrap.hinge_name(seed)
    target = store.resolve_node_by_name(seed, hinge)
    if target is None:  # pragma: no cover — the pin names a born node
        print("  The way beyond is closed.")
        return
    seal = seal_check(seed, target, current_name=stack[-1].name)
    if seal is not None:
        print("  The way beyond is sealed.")
        print(f"  {seal['prompt']}")
        return
    # The hinge lives at full depth; deepen the session's view if it
    # doesn't reach that far yet (a deeper view of the same one world).
    digits = hinge.rpartition("-")[2]
    root = stack[0]

    def _walk_to_hinge(from_root: SpatialNode) -> list[SpatialNode] | None:
        chain = [from_root]
        for d in digits[1:]:
            children = chain[-1].children
            idx = int(d) - 1
            if not 0 <= idx < len(children):
                return None
            chain.append(children[idx])
        return chain

    chain = _walk_to_hinge(root)
    if chain is None:
        root = store.world_tree(seed=seed, max_depth=len(digits))
        apply_ripple_scores(root, persistence.load_ripple_scores(seed))
        apply_property_overrides(root,
                                 persistence.load_node_property_overrides(seed))
        chain = _walk_to_hinge(root)
        if chain is None:  # pragma: no cover — the pin names a born node
            print("  The way beyond is closed.")
            return
    stack[:] = chain
    # Recorded only after the gate passed and the landing succeeded —
    # a refused or unresolvable crossing leaves no trace (ADR-008).
    persistence.record_mutation(seed, hinge, "PLAYER_MOVE", player_name,
                                {}, actor_identity=player_name)
    _announce_crossing("outward", wrap.ASCENT_LINE)
    _print_breadcrumb(stack)
    _print_look(stack[-1])


def _descend(stack: list[SpatialNode], n: int, seed: int,
             player_name: str | None = None) -> None:
    node = stack[-1]
    if not node.children:
        if wrap.wraps_inward(node) and n == 1:
            _wrap_descend(stack, seed, player_name=player_name)
            return
        print("  No deeper paths from here.")
        return
    idx = n - 1
    if not (0 <= idx < len(node.children)):
        print(f"  No path {n}. Choose 1–{len(node.children)}.")
        return
    child = node.children[idx]
    # Sealed passages: a locked Room bars entry until its current puzzle
    # is solved — the same gate every client meets (puzzles/gates). The
    # key is spoken from the threshold, so the attempt happens right here.
    from puzzles.gates import seal_check
    seal = seal_check(seed, child, current_name=node.name)
    if seal is not None:
        print(f"  {_style(child)}{display_name(child.name)}{_RESET} is sealed.")
        print(f"  {seal['prompt']}")
        print("  You may speak the key from the threshold:")
        _play_puzzle(child, seed, player_name=player_name)
        if seal_check(seed, child, current_name=node.name) is not None:
            return  # still sealed — the threshold holds
        print("  The way opens.")
    stack.append(child)
    _print_breadcrumb(stack)
    _print_look(stack[-1])
