import argparse
import secrets
from pathlib import Path

import persistence
from agents.agent import Agent
from multiverse.generator import BREADTH_ENVELOPE, generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.utils import count_nodes, find_node
from puzzles.engine import PuzzleEngine


def cmd_world(args):
    root = generate_node_hierarchy(seed=args.seed, max_depth=args.depth)
    print(root)
    node_count = count_nodes(root)
    persistence.save_world(args.seed, node_count, args.depth,
                           *BREADTH_ENVELOPE)
    print(f"[Saved: seed={args.seed}, {node_count} nodes]")


def cmd_agent(args):
    root = generate_node_hierarchy(seed=args.seed)
    agent = Agent(name=args.name, danger_threshold=args.danger_threshold)

    saved = persistence.load_agent_memory(args.name, args.seed)
    if saved:
        agent.memory = saved["visited_ids"]
        print(f"[Memory restored: {len(agent.memory)} nodes previously known]")

    agent.traverse(root, max_nodes=args.max_nodes)
    print(agent.report())

    events = [
        {"node": e.node_name, "level": e.level, "state": e.state.name, "action": e.action}
        for e in agent.log
    ]
    persistence.save_agent_run(args.name, args.seed, agent.fresh_count, events)
    persistence.save_agent_memory(args.name, args.seed, agent.memory, events[-100:])
    print(f"[Memory saved: {len(agent.memory)} total nodes known]")


def cmd_puzzles(args):
    from puzzles.types import PuzzleResult

    root = generate_node_hierarchy(seed=args.seed)
    engine = PuzzleEngine(seed=args.seed)
    engine.attach_puzzles(root)
    puzzles = engine.collect_puzzles(root)

    if not puzzles:
        print("No puzzles found in this world. Try a different seed.")
        return

    limit = max(1, args.limit)
    print(f"Found {len(puzzles)} puzzle(s) in this world; "
          f"playing the first {min(limit, len(puzzles))} "
          f"(--limit to change, 'skip' to pass, Ctrl-D to stop).\n")
    for puzzle in puzzles[:limit]:
        result = engine.run_puzzle(puzzle)
        persistence.save_puzzle_result(args.seed, puzzle.name, result.name, puzzle.attempts)
        if result == PuzzleResult.UNSOLVED and puzzle.attempts == 0:
            # The player walked away without a single guess (EOF/quit) —
            # stop the tour instead of marching through every remaining node.
            break


def cmd_history(args):
    worlds = persistence.list_worlds()
    if not worlds:
        print("No worlds saved yet. Run the 'world' or 'agent' command to generate some.")
        return
    print(f"{'Seed':>8}  {'Created':>20}  {'Nodes':>8}  {'Depth':>6}")
    print("-" * 50)
    for w in worlds:
        print(
            f"{w['seed']:>8}  {w['created_at']:>20}"
            f"  {str(w['node_count'] or '?'):>8}  {str(w['max_depth'] or '?'):>6}"
        )
        for r in persistence.get_agent_runs(w["seed"]):
            print(f"          agent '{r['agent_name']}' — {r['nodes_visited']} nodes  ({r['started_at']})")
        for p in persistence.get_puzzle_results(w["seed"], limit=5):
            print(f"          puzzle '{p['puzzle_name']}' — {p['result'].lower()}"
                  f" in {p['attempts']} attempt(s)  ({p['recorded_at']})")

    memories = persistence.list_agent_memories()
    if memories:
        print("\nAgent memory:")
        print(f"  {'Agent':>16}  {'Seed':>8}  {'Known nodes':>12}  {'Last seen':>20}")
        print("  " + "-" * 62)
        for m in memories:
            print(f"  {m['agent_name']:>16}  {m['world_seed']:>8}  {m['node_count']:>12}  {m['updated_at']:>20}")


def cmd_play(args):
    import interface
    name = args.name.strip() if args.name else None
    if name:
        from consciousness import WANDERER_CAST
        if name.lower() in {n.lower() for n in WANDERER_CAST}:
            # CLI play writes to the same permanent chronicle as everyone else;
            # a reserved cast name would impersonate an agent there (world
            # covenant). Reject it here too. (ADR-004 §7 / reserved-names.)
            raise SystemExit(
                f"'{name}' is a reserved world name (the wandering cast) — "
                "choose another with --name.")
    interface.run_session(
        seed=args.seed,
        depth=args.depth,
        player_name=name,
    )


def cmd_serve(args):
    import server
    server.run(host=args.host, port=args.port)


def cmd_backup(args):
    target = Path(args.to).expanduser()
    persistence.backup_to(target)
    size_kb = target.stat().st_size // 1024
    print(f"Backup written: {target} ({size_kb} KB)")


def cmd_restore(args):
    source = Path(getattr(args, "from")).expanduser()
    if not args.yes:
        print(f"This OVERWRITES the live world database with {source}.")
        print("Everything recorded since that backup will be lost.")
        answer = input("Type 'restore' to proceed: ").strip().lower()
        if answer != "restore":
            print("Aborted — nothing was changed.")
            return
    counts = persistence.restore_from(source)
    print(f"Restored from {source}")
    print(f"  chronicle events: {counts['events_before']} -> "
          f"{counts['events_after']}")
    print("Restart the server so in-memory state matches the restored "
          "world (production: `fly machine restart <id>`).")


def cmd_redact(args):
    if args.find is not None:
        rows = persistence.find_mutations_by_text(args.find,
                                                  world_seed=args.seed)
        if not rows:
            print("No chronicle rows match.")
            return
        print(f"{'id':>8}  {'recorded':<20}  {'type':<15}  {'seed':>6}  "
              f"{'player':<16}  content")
        print("-" * 110)
        for r in rows:
            snippet = "; ".join(
                f"{k}={v}" for k, v in r["data"].items()
                if isinstance(v, str))[:48]
            print(f"{r['id']:>8}  {r['at']:<20}  {r['type']:<15}  "
                  f"{r['seed']:>6}  {(r['player'] or '—'):<16}  {snippet}")
        print("\nApply with: python main.py redact --id <id> "
              "[--scrub-name] [--reason '...']")
        return

    if not args.yes:
        print(f"This tombstones the human-authored text of chronicle row "
              f"{args.id} (the row, its event type, and its actor identity "
              f"are kept).")
        answer = input("Type 'redact' to proceed: ").strip().lower()
        if answer != "redact":
            print("Aborted — nothing was changed.")
            return
    summary = persistence.redact_mutation(args.id, scrub_name=args.scrub_name,
                                          reason=args.reason)
    if summary is None:
        raise SystemExit(f"no chronicle row has id {args.id}")
    fields = ", ".join(summary["fields"]) or "(no free-text fields present)"
    print(f"Redacted row {summary['id']} — {summary['type']} at "
          f"{summary['node']} (world {summary['seed']})")
    print(f"  fields tombstoned: {fields}")
    if summary["name_scrubbed"]:
        print("  display name scrubbed (actor_identity retained)")


def invite_share_url(key: str, name: str, base: str = "<BASE>") -> str:
    """Build the invite URL to hand a tester.

    Lands on `/` (the D3 explorer): it wires the full core loop — speak to
    nodes, solve puzzles, observe agents — and reads ?key= and ?name= from the
    URL. `/app` (React+Pixi) is now also feature-complete (speak + puzzle
    panels), but `/` is the no-WebGL-dependency default so the invite works on
    any device on the first click.
    """
    from urllib.parse import quote
    return f"{base}/?key={key}&name={quote(name)}"


def cmd_invite(args):
    action = args.invite_action
    if action == "mint":
        from consciousness import WANDERER_CAST
        name = args.name.strip()
        if not name:
            raise SystemExit("A registered name must not be empty.")
        if name.lower() in {n.lower() for n in WANDERER_CAST}:
            raise SystemExit(
                f"'{name}' is a reserved world name (the wandering cast) — "
                "choose another.")
        key = "nw_" + secrets.token_hex(16)
        try:
            persistence.mint_invite_key(key, name=name, note=args.note)
        except persistence.NameUnavailable as exc:
            # ADR-004 §7: every player's name is unique. Fail friendly.
            raise SystemExit(f"{exc} — choose another name.")
        print(f"Minted invite for {name}:")
        print(f"  key: {key}")
        if args.note:
            print(f"  note: {args.note}")
        print(f"\nShare the URL: {invite_share_url(key, name)}")
    elif action == "list":
        rows = persistence.list_invite_keys(include_revoked=args.all)
        if not rows:
            print("No invite keys issued yet.")
            return
        print(f"{'Name':<20}  {'Key':<36}  {'Created':<20}  {'Last used':<20}  Status")
        print("-" * 110)
        for r in rows:
            status = "revoked" if r["revoked_at"] else "active"
            last = r["last_used_at"] or "—"
            print(f"{r['name']:<20}  {r['key']:<36}  {r['created_at']:<20}  {last:<20}  {status}")
    elif action == "revoke":
        ok = persistence.revoke_invite_key(args.key)
        if ok:
            print(f"Revoked: {args.key}")
        else:
            print(f"No active key matched: {args.key}")
    else:  # pragma: no cover — argparse already constrains this
        raise SystemExit(f"unknown invite action: {action}")


def cmd_speak(args):
    try:
        import consciousness
    except ImportError:
        print("The worlds are silent — install the 'anthropic' package to hear them.")
        return

    root = generate_node_hierarchy(seed=args.seed)
    target = find_node(root, args.node) if args.node else root
    if target is None:
        print(f"Node '{args.node}' not found in seed={args.seed}. Run 'world' to see available nodes.")
        return

    print(f"\n[{target.level}: {target.name}]")
    history = persistence.get_node_history(args.seed, target.name)
    try:
        response = consciousness.speak(
            target, args.message, history=history,
            ripple_score=persistence.get_ripple_score(args.seed, target.name),
        )
        print(response)
        # Symmetry with every other surface: speaking leaves a trace, and
        # both sides of the exchange become node memory.
        persistence.record_mutation(
            args.seed, target.name, "PLAYER_SPEAK", None,
            {"message": args.message[:128], "reply": response[:200]},
        )
    except Exception:
        # In-fiction silence — never an SDK error at the player.
        print(consciousness.fallback_voice(target))
        print("(The voices need ANTHROPIC_API_KEY to wake.)")


def _accept_seed(subparser: argparse.ArgumentParser) -> None:
    """Let --seed appear after the subcommand too (`main.py world --seed 7`),
    not only before it. SUPPRESS keeps the subcommand flag from clobbering a
    globally supplied value with its own default."""
    subparser.add_argument("--seed", type=int, default=argparse.SUPPRESS,
                           help="RNG seed (default: 42)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Enfolded: Nested World Adventure — shared persistent multiverse simulation",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_world = sub.add_parser("world", help="Generate and print the world hierarchy")
    _accept_seed(p_world)
    p_world.add_argument("--depth", type=int, default=11, help="Max hierarchy depth (default: 11)")
    p_world.set_defaults(func=cmd_world)

    p_agent = sub.add_parser("agent", help="Run an agent traversal of the world")
    _accept_seed(p_agent)
    p_agent.add_argument("--name", type=str, default="Scout", help="Agent name (default: Scout)")
    p_agent.add_argument("--danger-threshold", type=int, default=6, dest="danger_threshold",
                         help="Self-preservation threshold: withdraw from nodes with danger_level above this (default: 6)")
    p_agent.add_argument("--max-nodes", type=int, default=50, dest="max_nodes",
                         help="Max nodes to visit (default: 50)")
    p_agent.set_defaults(func=cmd_agent)

    p_puzzles = sub.add_parser("puzzles", help="Find and play puzzles in the world")
    _accept_seed(p_puzzles)
    p_puzzles.add_argument("--limit", type=int, default=10,
                           help="How many puzzles to play this run (default: 10)")
    p_puzzles.set_defaults(func=cmd_puzzles)

    p_history = sub.add_parser("history", help="Show saved worlds, agent runs, and puzzle results")
    p_history.set_defaults(func=cmd_history)

    p_play = sub.add_parser("play", help="Start an interactive session in the world")
    _accept_seed(p_play)
    p_play.add_argument("--depth", type=int, default=6, help="Max hierarchy depth (default: 6)")
    p_play.add_argument("--name", type=str, default=None,
                        help="Your explorer name — nodes will remember you by it")
    p_play.set_defaults(func=cmd_play)

    p_serve = sub.add_parser("serve", help="Start the REST API server")
    p_serve.add_argument("--host", type=str, default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    p_serve.set_defaults(func=cmd_serve)

    p_backup = sub.add_parser("backup",
        help="Write an online snapshot of the SQLite store to a target path")
    p_backup.add_argument("--to", type=str, required=True,
                          help="Target file path (parent dirs are created)")
    p_backup.set_defaults(func=cmd_backup)

    p_restore = sub.add_parser(
        "restore",
        help="Restore the live world database from a backup file")
    p_restore.add_argument("--from", type=str, required=True, dest="from",
                           metavar="PATH",
                           help="Backup file to restore (made by `backup`)")
    p_restore.add_argument("--yes", action="store_true",
                           help="Skip the interactive confirmation")
    p_restore.set_defaults(func=cmd_restore)

    p_redact = sub.add_parser(
        "redact",
        help="Tombstone abusive text in a chronicle row (content-level; "
             "the event, its type, and its actor identity are preserved)")
    group = p_redact.add_mutually_exclusive_group(required=True)
    group.add_argument("--find", type=str, metavar="TEXT",
                       help="List rows whose content or display name "
                            "contains TEXT (read-only search step)")
    group.add_argument("--id", type=int,
                       help="Chronicle row id to redact (from --find or "
                            "the /chronicle cursor)")
    p_redact.add_argument("--seed", type=int, default=None,
                          help="Restrict --find to one world")
    p_redact.add_argument("--scrub-name", action="store_true",
                          help="Also null the display name (for names that "
                               "are themselves the abuse)")
    p_redact.add_argument("--reason", type=str, default=None,
                          help="Short operator note stored on the row")
    p_redact.add_argument("--yes", action="store_true",
                          help="Skip the interactive confirmation")
    p_redact.set_defaults(func=cmd_redact)

    p_invite = sub.add_parser("invite",
        help="Manage per-user beta invite keys (mint / list / revoke)")
    invite_sub = p_invite.add_subparsers(dest="invite_action", required=True)

    p_invite_mint = invite_sub.add_parser("mint",
        help="Mint a new invite key for a named tester")
    p_invite_mint.add_argument("--name", type=str, required=True,
                               help="Tester name (must be unique per cohort)")
    p_invite_mint.add_argument("--note", type=str, default=None,
                               help="Optional free-text note (e.g. 'alpha cohort')")
    p_invite_mint.set_defaults(func=cmd_invite)

    p_invite_list = invite_sub.add_parser("list", help="List issued invite keys")
    p_invite_list.add_argument("--all", action="store_true",
                               help="Include revoked keys (default: active only)")
    p_invite_list.set_defaults(func=cmd_invite)

    p_invite_revoke = invite_sub.add_parser("revoke",
        help="Revoke an invite key (irreversible)")
    p_invite_revoke.add_argument("key", type=str, help="The key string to revoke")
    p_invite_revoke.set_defaults(func=cmd_invite)

    p_speak = sub.add_parser("speak", help="Speak to a node using Claude consciousness")
    _accept_seed(p_speak)
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
