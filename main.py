import argparse
import logging
import secrets
import sys
from pathlib import Path

import persistence
from agents.agent import Agent
from multiverse import store, wrap
from multiverse.generator import BREADTH_ENVELOPE, DEFAULT_WORLD_SEED
from multiverse.utils import apply_property_overrides, count_nodes, find_node
from puzzles.engine import PuzzleEngine

_log = logging.getLogger("nested_worlds.cli")
if not _log.handlers:
    _log.addHandler(logging.NullHandler())


def cmd_world(args):
    root = store.world_tree(seed=args.seed, max_depth=args.depth)
    print(root)
    node_count = count_nodes(root)
    persistence.save_world(args.seed, node_count, args.depth,
                           *BREADTH_ENVELOPE)
    print(f"[Saved: seed={args.seed}, {node_count} nodes]")


def cmd_agent(args):
    root = store.world_tree(seed=args.seed)
    apply_property_overrides(root, persistence.load_node_property_overrides(args.seed))
    agent = Agent(name=args.name, danger_threshold=args.danger_threshold, world_seed=args.seed)

    saved = persistence.load_agent_memory(args.name, args.seed)
    if saved:
        agent.memory = saved["visited_ids"]
        agent.scan_cursor = saved.get("scan_cursor")
        print(f"[Memory restored: {len(agent.memory)} nodes previously known]")

    agent.traverse(root, max_nodes=args.max_nodes)
    print(agent.report())

    events = [
        {"node": e.node_name, "level": e.level, "state": e.state.name, "action": e.action}
        for e in agent.log
    ]
    persistence.save_agent_run(args.name, args.seed, agent.fresh_count, events)
    persistence.save_agent_memory(args.name, args.seed, agent.memory,
        ((saved or {}).get("log_entries", []) + events)[-100:])
    if agent.scan_cursor:
        persistence.save_agent_scan_cursor(args.name, args.seed, agent.scan_cursor)
    print(f"[Memory saved: {len(agent.memory)} total nodes known]")


def cmd_puzzles(args):
    from puzzles.types import PuzzleResult

    root = store.world_tree(seed=args.seed)
    apply_property_overrides(root, persistence.load_node_property_overrides(args.seed))
    engine = PuzzleEngine(seed=args.seed)
    def walk(node):
        yield node
        for child in node.children:
            yield from walk(child)
    nodes = list(walk(root))
    puzzles = nodes  # Select first; do not open every future question on a CLI preview.
    if not puzzles:
        print("No puzzles found in this world. Try a different seed.")
        return

    limit = max(1, args.limit)
    print(f"Found {len(puzzles)} puzzle(s) in this world; "
          f"playing the first {min(limit, len(puzzles))} "
          f"(--limit to change, 'skip' to pass, Ctrl-D to stop).\n")
    epochs = persistence.count_rearms_by_node(args.seed)
    for node in nodes[:limit]:
        engine.attach_puzzles(node, epochs, persist=True, recursive=False)
        puzzle = engine.puzzle_for(node)
        result = engine.run_puzzle(puzzle)
        persistence.save_puzzle_result(args.seed, puzzle.name, result.name, puzzle.attempts)
        if result == PuzzleResult.UNSOLVED and puzzle.attempts == 0:
            # The player walked away without a single guess (EOF/quit) —
            # stop the tour instead of marching through every remaining node.
            break


def cmd_situation(args):
    from persistence.situations import install
    print(f"Opened situation {install(args.seed)} in world {args.seed}. Existing instances are preserved.")


def cmd_work_report(args):
    import json
    import sqlite3
    from persistence.recovery import format_report, work_report

    try:
        report = work_report(Path(args.db) if args.db else persistence._DB_PATH,
                             seed=args.seed, limit=args.limit)
    except (ValueError, sqlite3.Error) as exc:
        raise SystemExit(f"Work report unavailable: {exc}") from exc
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else format_report(report))


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
    name = args.name.strip() if args.name else ""
    if not name:
        # CLI play writes PLAYER_SPEAK / SCALE_ACT rows into the same permanent
        # chronicle as everyone else; a nameless session would record an
        # unknown presence there. No anonymous gameplay (ADR-004 §7): require a
        # name so every recorded actor is known.
        raise SystemExit("A player name is required — pass --name <you>.")
    from server.handlers import _has_utf8_form
    if not _has_utf8_form(name):
        # An argv byte that is not UTF-8 arrives as a lone surrogate, which
        # no row can store; refuse it before a session writes anything.
        raise SystemExit("A player name must be plain text — pass --name <you>.")
    from agents.identities import canonical
    if canonical(name) is not None:
        # CLI play writes to the same permanent chronicle as everyone else;
        # a server-owned agent name (the wandering cast, Scout, Observer)
        # would impersonate an agent there (world covenant). Reject it here
        # too. (ADR-004 §7 / reserved-names, agents/identities.py.)
        raise SystemExit(
            f"'{name}' is a reserved world name (one of the world's own "
            "agents) — choose another with --name.")
    from server.moderation import name_refusal, writes_shared_chronicle
    # Local multi-world play is the operator terminal. A name is screened
    # only when this session writes the hosted canonical world.
    if writes_shared_chronicle(args.seed):
        # A registered player's name, in any spelling, would put this
        # session's rows in the chronicle under their name. Revoked names
        # stay theirs too, as minting keeps them taken.
        wanted = persistence.name_key(name)
        if any(persistence.name_key(row["name"]) == wanted
               for row in persistence.list_invite_keys(include_revoked=True)):
            raise SystemExit(
                f"'{name}' is a registered player's name — choose another "
                "with --name.")
        if not persistence.name_is_visible_text(name):
            # /register, the mint CLI and the keyless WebSocket join refuse
            # the same names: a control or invisible character, or nothing
            # visible, would put rows under a name that shows as another
            # name or as no one (ADR-004 §7: no anonymous gameplay).
            raise SystemExit("A player name must be visible text, with no "
                             "control or invisible characters — pass "
                             "--name <you>.")
        refusal = name_refusal(name)
        if refusal:
            raise SystemExit(f"'{name}' — {refusal} Use --name.")
    interface.run_session(
        seed=args.seed,
        depth=args.depth,
        player_name=name,
    )


def cmd_serve(args):
    import server
    server.run(host=args.host, port=args.port)


def cmd_models(args):
    """Print the resolved provider and model for each text task.

    The provider is the registry's (``NESTED_WORLDS_PROVIDER``, default
    ``anthropic``). ``--probe`` makes one tiny live call per distinct model
    id. It is off unless this flag is passed. Server startup, tests, and CI
    do not pass it. An unconfigured provider prints
    ``provider not configured`` and, with ``--probe``,
    ``skipped: provider not configured`` and exits 1. That path does not
    call the provider and does not echo the base URL or the key. A missing
    SDK for the selected provider exits with one line naming the optional
    extra, and does not probe. A task that would use the default, on an
    adapter that does not supply one, is a hard problem: the report is
    printed and the process exits. That line names the task variable or
    ``NESTED_WORLDS_MODEL`` for node voice, inhabitant voice, and intention.
    Moderation names only its own variable. When the selected adapter's
    ``supports_json_schema`` is false, the intent row says structured
    outputs are off and intent calls will be refused. That note is not a
    hard problem.
    """
    from consciousness import runtime
    from consciousness.model_check import (
        check_model_configuration, format_report, probe_distinct_models,
    )

    provider = runtime.get_provider()
    report = check_model_configuration(provider)
    print(_with_schema_note(format_report(report), provider))
    _print_unconfigured_hint(provider)
    if report.hard:
        raise SystemExit(report.failure_line())
    if not args.probe:
        return
    failed = False
    for result in probe_distinct_models(report):
        print(result.line())
        failed = failed or not result.accepted
    if failed:
        raise SystemExit(1)


def cmd_voice_health(args):
    """Report how the world's voice has actually answered, for the operator.

    Reads the daily voice-outcome counters every player-facing voice surface
    writes (`server.observability.voice_outcome`): answered lines and each
    kind of quiet one. Exits 1 when the window holds a failure an operator
    must fix (a provider error, a failed moderation screen, no provider slot
    within the wait, or a server with no usable voice), when the model
    configuration has a hard problem (the check `models` and the server boot
    run), or when `--probe` is passed and
    the tiny live probe fails. Limits and the kill
    switch are reported and do not fail the check. Store errors are not
    counted (the store is what failed); they reach the ERROR log and Sentry.
    Run it on the host (`fly ssh console -C "python main.py voice-health"`)
    from whatever scheduler alerts the operator.
    """
    from consciousness import runtime
    from server import guard, observability

    summary = observability.voice_outcome_summary(days=args.days)
    print(f"Voice outcomes, last {args.days} UTC day(s), today included")
    failures = 0
    if not summary:
        print("  (no voice requests recorded)")
    for day in sorted(summary):
        print(day)
        for surface in observability.VOICE_SURFACES:
            counts = summary[day].get(surface, {})
            if not counts:
                continue
            quiet = ", ".join(
                f"{reason} {counts[reason]}"
                for reason in observability.VOICE_REASONS
                if reason != "ok" and counts.get(reason))
            print(f"  {surface:<12} answered {counts.get('ok', 0):>4}"
                  + (f"   quiet: {quiet}" if quiet else ""))
            failures += sum(counts.get(r, 0) for r in observability.VOICE_FAILURES)
    used = persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, guard._utc_day())
    cap = guard._cap_for(guard.ANTHROPIC_CAP_ENV, guard._DEFAULT_ANTHROPIC_DAILY)
    print(f"voice budget today: {used}/{cap} calls")
    if guard.ai_disabled():
        print(f"kill switch: {guard.DISABLE_AI_ENV}=1 (the world is quiet on purpose)")
    ready = runtime.configured()
    print("voice provider: configured" if ready else "voice provider: NOT configured")
    problems = []
    if failures:
        problems.append(f"{failures} voice failure(s) in the window")
    if not ready and not guard.ai_disabled():
        problems.append("no usable voice provider")
    # Credentials are not enough: the same model-id check `models` and the
    # server boot run. A task without a usable model id cannot answer.
    from consciousness.model_check import (
        check_model_configuration, probe_distinct_models,
    )
    report = check_model_configuration(runtime.get_provider())
    if report.hard and not guard.ai_disabled():
        print(report.failure_line())
        problems.append("unusable model configuration")
    if args.probe:
        for result in probe_distinct_models(report):
            print(result.line())
            if not result.accepted:
                problems.append("live probe failed")
    if problems:
        raise SystemExit("voice-health: " + "; ".join(dict.fromkeys(problems)))
    print("voice-health: ok")


_SCHEMA_OFF_NOTE = "(structured outputs off - intent calls will be refused)"


def _with_schema_note(text: str, provider) -> str:
    """Mark the intent row when this adapter will refuse a schema.

    An adapter that omits ``supports_json_schema`` still accepts a schema.
    The note is not a startup failure.
    """
    supports = getattr(provider, "supports_json_schema", None)
    if not callable(supports):
        return text
    try:
        enabled = bool(supports())
    except Exception:
        return text
    if enabled:
        return text
    lines = []
    for line in text.split("\n"):
        if line.startswith("intent ") and _SCHEMA_OFF_NOTE not in line:
            line = f"{line} {_SCHEMA_OFF_NOTE}"
        lines.append(line)
    return "\n".join(lines)


def _print_unconfigured_hint(provider) -> None:
    """One neutral line when the selected adapter is not usable.

    The base URL and the key are not printed. A provider with no
    ``configured`` method is left alone.
    """
    configured = getattr(provider, "configured", None)
    if not callable(configured):
        return
    try:
        ready = bool(configured())
    except Exception:
        ready = False
    if not ready:
        print("provider not configured")


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
            mark = ""
            if r.get("provider") or r.get("resolved_model"):
                mark = (f"  [{r.get('provider') or '—'} / "
                        f"{r.get('resolved_model') or '—'}]")
            print(f"{r['id']:>8}  {r['at']:<20}  {r['type']:<15}  "
                  f"{r['seed']:>6}  {(r['player'] or '—'):<16}  {snippet}{mark}")
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
        from agents.identities import canonical
        from server.moderation import name_refusal
        from server.handlers import _has_utf8_form
        name = args.name.strip()
        if not name:
            raise SystemExit("A registered name must not be empty.")
        if len(name) > 32:
            # The cap /register applies: the name is shown in every client.
            raise SystemExit("A registered name must be 32 characters or fewer.")
        if not _has_utf8_form(name):
            # A non-UTF-8 argv byte arrives as a lone surrogate; the INSERT
            # would raise UnicodeEncodeError with a traceback.
            raise SystemExit("A registered name must be plain text.")
        if not persistence.name_is_visible_text(name):
            # /register refuses the same names (ADR-004 §7).
            raise SystemExit("A registered name must be visible text, with no "
                             "control or invisible characters.")
        if canonical(name) is not None:
            raise SystemExit(
                f"'{name}' is a reserved world name (one of the world's own "
                "agents) — choose another.")
        # Minted names are shared. --unscreened is the explicit operator
        # override for when the screen is off or the operator accepts the
        # name anyway. Reserved agent names are still refused above.
        if not getattr(args, "unscreened", False):
            refusal = name_refusal(name)
            if refusal:
                raise SystemExit(
                    f"'{name}' — {refusal} "
                    "Pass --unscreened to mint without the screen.")
        else:
            print("Name accepted without the moderation screen (--unscreened).")
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
        print("(Keys are stored hashed — this is the only time the key is "
              "shown. If it is lost, use invite rotate with its digest prefix.)")
    elif action == "list":
        rows = persistence.list_invite_keys(include_revoked=args.all)
        if not rows:
            print("No invite keys issued yet.")
            return
        # Keys are hashed at rest, so the list shows a digest prefix — enough
        # for `invite revoke <prefix>` to target the row, never a credential.
        print(f"{'Name':<20}  {'Key (hash)':<14}  {'Created':<20}  {'Last used':<20}  Status")
        print("-" * 92)
        for r in rows:
            status = "revoked" if r["revoked_at"] else "active"
            last = r["last_used_at"] or "—"
            print(f"{r['name']:<20}  {r['key'][:12] + '…':<14}  {r['created_at']:<20}  {last:<20}  {status}")
    elif action == "revoke":
        ok = persistence.revoke_invite_key(args.key)
        if ok:
            print(f"Revoked: {args.key}")
        else:
            print(f"No active key matched: {args.key}")
    elif action == "rotate":
        from persistence.participants import rotate
        key = "nw_" + secrets.token_hex(16)
        try:
            participant = rotate(args.key, key)
        except ValueError as exc:
            raise SystemExit(str(exc))
        print(f"Replaced credential for {participant['name']}; the previous key no longer works.")
        print(f"Participant, journal, profile and saved position retained: {participant['id']}")
        print(f"Share once: {invite_share_url(key, participant['name'])}")
    elif action == "create":
        # Self-service registration (ADR-004 §7): the operator shares this
        # single-use link; the PLAYER picks their own unique name at
        # /register, and redemption mints their per-user play key.
        token = "nwr_" + secrets.token_hex(16)
        persistence.create_registration_token(token, note=args.note)
        print("Created a single-use registration invite:")
        print(f"  token: {token}")
        if args.note:
            print(f"  note: {args.note}")
        print(f"\nShare the URL: <BASE>/register?invite={token}")
        print("The invitee chooses their own name there; it must be unique.")
        print("(Tokens are stored hashed — this is the only time the link is "
              "shown. If it leaks, `invite cancel` it.)")
    elif action == "tokens":
        rows = persistence.list_registration_tokens(include_spent=args.all)
        if not rows:
            print("No registration invites"
                  + ("" if args.all else " outstanding") + ".")
            return
        # Tokens are hashed at rest — the listing shows a digest prefix that
        # `invite cancel <prefix>` accepts; the sharable link is shown once
        # at `invite create` and never again.
        print(f"{'Token (hash)':<14}  {'Created':<20}  {'Status':<22}  Note")
        print("-" * 80)
        for r in rows:
            if r["redeemed_at"]:
                status = f"redeemed → {r['redeemed_name']}"
            elif r["revoked_at"]:
                status = "cancelled"
            else:
                status = "redeemable"
            print(f"{r['token'][:12] + '…':<14}  {r['created_at']:<20}  {status:<22}  "
                  f"{r['note'] or '—'}")
    elif action == "cancel":
        ok = persistence.cancel_registration_token(args.token)
        if ok:
            print(f"Cancelled: {args.token}")
        else:
            print(f"No redeemable registration invite matched: {args.token}")
    elif action == "duplicates":
        _invite_duplicates()
    else:  # pragma: no cover — argparse already constrains this
        raise SystemExit(f"unknown invite action: {action}")


def _invite_duplicates() -> None:
    """List registered names that are one name under `persistence.name_key`.

    Read-only. Registration refuses a second name with the same key, so a
    group can only come from rows written before that check or restored
    from such a backup. Revoked names are included, because they stay
    taken. A registered name whose key is a reserved name's (one of the
    world's own agents, `agents.identities.canonical`) is listed as a group
    too, under that agent's name: registration refuses it now, but a row
    written before the key dropped invisible characters can hold one
    (`Scout` + U+200B registered beside the reserved `Scout` until then).
    Each name is printed through `_shown` and as `ascii()`, so a composed
    and a decomposed spelling, or one with an invisible character, read
    differently; the digest prefix is what `invite revoke` and
    `invite rotate` accept. Exits 1 when any group exists, 0 otherwise.
    """
    from agents.identities import canonical
    groups: dict[str, list[dict]] = {}
    for row in persistence.list_invite_keys(include_revoked=True):
        groups.setdefault(persistence.name_key(row["name"]), []).append(row)
    shared = []
    for rows in groups.values():
        reserved = canonical(rows[0]["name"])  # one key, so any row answers
        if len(rows) > 1 or reserved is not None:
            shared.append((reserved, rows))
    if not shared:
        print("No two registered names share a name key, and none shares "
              "one with a reserved world name.")
        return
    print(f"{len(shared)} group(s) of registered names share a name key with "
          "each other or with a reserved world name (revoked names included):")
    for reserved, rows in shared:
        print()
        if reserved is not None:
            print(f"  {reserved:<20}  reserved: one of the world's own agents")
        for r in sorted(rows, key=lambda r: (r["created_at"], r["key"])):
            status = "revoked" if r["revoked_at"] else "active"
            print(f"  {_shown(r['name']):<20}  {ascii(r['name']):<28}  "
                  f"{r['key'][:12] + '…':<14}  {r['created_at']:<20}  {status}")
    raise SystemExit(1)


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number")
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _shown(text) -> str:
    """`text` for the operator's terminal: every non-printable character is
    written as its escape (\\x1b, \\u200b), so a control sequence held in a
    name or an older reason is shown, never emitted."""
    return "".join(c if c.isprintable()
                   else c.encode("unicode_escape").decode("ascii")
                   for c in str(text))


def _reason_arg(reason: str) -> str:
    """`--reason -` reads the reason from standard input, keeping it out of
    shell history and process arguments. One trailing newline is dropped;
    the rest is checked exactly as a reason given on the command line."""
    if reason != "-":
        return reason
    if sys.stdin.isatty():
        print("Reason (one line), then Enter and Ctrl-D:", file=sys.stderr,
              flush=True)
    try:
        reason = sys.stdin.read()
        # Under a UTF-8 or C locale, Python reads stdin with surrogateescape,
        # so undecodable bytes arrive as lone surrogates, not as an error.
        reason.encode("utf-8")
    except UnicodeError:
        raise SystemExit("The reason on standard input is not valid text; "
                         "nothing changed.")
    for newline in ("\r\n", "\n"):
        if reason.endswith(newline):
            return reason[:-len(newline)]
    return reason


def cmd_sanction(args):
    """Owner-only suspend / ban / lift / list (beta checklist G5).

    Output goes to the operator's terminal. Reasons are printed only by
    `list`; nothing here logs a reason, a name or a credential. Names and
    reasons are printed through `_shown`, so no control sequence reaches
    the terminal.
    """
    import datetime
    from persistence import sanctions
    from server.handlers import _has_utf8_form
    action = args.sanction_action
    if action in ("suspend", "ban") and not _has_utf8_form(args.player):
        # A non-UTF-8 argv byte arrives as a lone surrogate. The lookup would
        # raise UnicodeEncodeError, a ValueError, and print the codec's text.
        raise SystemExit("A player name must be plain text.")
    try:
        if action == "suspend":
            try:
                if args.days is not None:
                    duration = datetime.timedelta(days=args.days)
                else:
                    duration = datetime.timedelta(hours=args.hours)
            except OverflowError:
                # Past what a timedelta can hold, so far past the cap:
                # suspend() refuses it with the allowed-range message.
                duration = datetime.timedelta.max
            s = sanctions.suspend(args.player, duration,
                                  _reason_arg(args.reason))
            print(f"Suspended {_shown(s['name'] or s['participant'])} until "
                  f"{s['expires_at']} UTC (sanction {s['id']}).")
        elif action == "ban":
            s = sanctions.ban(args.player, _reason_arg(args.reason))
            print(f"Banned {_shown(s['name'] or s['participant'])} until lifted "
                  f"(sanction {s['id']}).")
        elif action == "lift":
            s = sanctions.lift(args.sanction_id, _reason_arg(args.reason))
            print(f"Lifted sanction {s['id']} ({s['kind']}) on "
                  f"{_shown(s['name'] or s['participant'])}.")
        elif action == "list":
            rows = sanctions.list_sanctions(include_all=args.all)
            if not rows:
                print("No sanctions recorded." if args.all
                      else "No active sanctions.")
                return
            print(f"{'ID':>4}  {'Name':<20}  {'Kind':<10}  {'Status':<8}  "
                  f"{'Since (UTC)':<19}  {'Until (UTC)':<19}  Reason")
            print("-" * 110)
            for r in rows:
                until = r["expires_at"] or "no end"
                print(f"{r['id']:>4}  {_shown(r['name'] or r['participant']):<20}  "
                      f"{r['kind']:<10}  {r['status']:<8}  {r['created_at']:<19}  "
                      f"{until:<19}  {_shown(r['reason'])}")
                if r["lifted_at"]:
                    print(f"{'':>4}  lifted {r['lifted_at']}: "
                          f"{_shown(r['lift_reason'])}")
        else:  # pragma: no cover — argparse already constrains this
            raise SystemExit(f"unknown sanction action: {action}")
    except ValueError as exc:
        raise SystemExit(str(exc))
    if action in ("suspend", "ban"):
        print("Their open sessions stop receiving the world within about 5 "
              "seconds and close within about 6 (later while a chat waits "
              "on the model provider); new requests are refused. The "
              "player is not told the reason.")


def cmd_speak(args):
    try:
        import consciousness
    except ImportError as exc:
        _log.warning("speak fallback: %s", type(exc).__name__)
        print("The worlds are silent today.")
        return

    root = store.world_tree(seed=args.seed)
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
            hinge=wrap.is_hinge(args.seed, target.name),
        )
        print(response)
        # Symmetry with every other surface: speaking leaves a trace, and
        # both sides of the exchange become node memory. Read the call
        # result before slicing; a slice is a plain str.
        persistence.record_mutation(
            args.seed, target.name, "PLAYER_SPEAK", None,
            {"message": args.message[:128], "reply": response[:200]},
            model_provider=getattr(response, "provider", None),
            resolved_model=getattr(response, "resolved_model", None),
        )
    except Exception as exc:
        _log.warning("speak fallback: %s", consciousness.runtime.failure_summary(exc))
        # In-fiction silence — never an SDK error at the player.
        print(consciousness.fallback_voice(target))


def _accept_seed(subparser: argparse.ArgumentParser) -> None:
    """Let --seed appear after the subcommand too (`main.py world --seed 7`),
    not only before it. SUPPRESS keeps the subcommand flag from clobbering a
    globally supplied value with its own default."""
    subparser.add_argument("--seed", type=int, default=argparse.SUPPRESS,
                           help=f"RNG seed (default: {DEFAULT_WORLD_SEED})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Enfolded: Nested World Adventure — shared persistent multiverse simulation",
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_WORLD_SEED,
        help=f"RNG seed (default: {DEFAULT_WORLD_SEED})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    from persistence.ideas_cli import add_parser as add_ideas_parser
    add_ideas_parser(sub)

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
                        help="Your explorer name (required) — nodes will "
                             "remember you by it; no anonymous play")
    p_play.set_defaults(func=cmd_play)

    p_serve = sub.add_parser("serve", help="Start the REST API server")
    p_serve.add_argument("--host", type=str, default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    p_serve.set_defaults(func=cmd_serve)

    p_models = sub.add_parser(
        "models",
        help="Show the resolved text provider and model id for each task",
    )
    p_models.add_argument(
        "--probe",
        action="store_true",
        help="Make one tiny live call per distinct model id. Off unless "
             "passed. Not used by server startup, tests, or CI. An "
             "unconfigured provider prints 'provider not configured', and "
             "with this flag also 'skipped: provider not configured', then "
             "exits 1 without calling the provider.",
    )
    p_models.set_defaults(func=cmd_models)

    p_voice = sub.add_parser(
        "voice-health",
        help="Report answered and quiet voice lines; exit 1 on voice failures",
    )
    p_voice.add_argument("--days", type=int, default=1,
                         help="UTC days to report, today included (default 1)")
    p_voice.add_argument(
        "--probe", action="store_true",
        help="Also make the tiny live probe from `models --probe` (one call "
             "per distinct model id; no chronicle row, no voice budget).")
    p_voice.set_defaults(func=cmd_voice_health)

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

    p_work = sub.add_parser("work-report", help="Inspect pending work without changing the database")
    p_work.add_argument("--db", help="Existing live database or backup (opened read-only)")
    p_work.add_argument("--seed", type=int, default=None, help="Limit to one world; default is all worlds")
    p_work.add_argument("--limit", type=int, default=20, help="Samples per queue, 1–100 (default: 20)")
    p_work.add_argument("--json", action="store_true", help="Machine-readable report")
    p_work.set_defaults(func=cmd_work_report)

    p_situation = sub.add_parser("situation", help="Install the authored first situation in existing world 382")
    p_situation.add_argument("--seed", type=int, default=382)
    p_situation.set_defaults(func=cmd_situation)

    p_invite = sub.add_parser("invite",
        help="Manage per-user beta invite keys and registration invites "
             "(mint / list / rotate / revoke / create / tokens / cancel / "
             "duplicates)")
    invite_sub = p_invite.add_subparsers(dest="invite_action", required=True)

    p_invite_mint = invite_sub.add_parser("mint",
        help="Mint a new invite key for a named tester (operator picks the name)")
    p_invite_mint.add_argument("--name", type=str, required=True,
                               help="Tester name (must be unique per cohort)")
    p_invite_mint.add_argument("--note", type=str, default=None,
                               help="Optional free-text note (e.g. 'alpha cohort')")
    p_invite_mint.add_argument(
        "--unscreened", action="store_true",
        help="Mint without the moderation screen. Operator override for "
             "when NESTED_WORLDS_DISABLE_MODERATION is set, or when you "
             "accept the name yourself. Agent names stay reserved.")
    p_invite_mint.set_defaults(func=cmd_invite)

    p_invite_list = invite_sub.add_parser("list", help="List issued invite keys")
    p_invite_list.add_argument("--all", action="store_true",
                               help="Include revoked keys (default: active only)")
    p_invite_list.set_defaults(func=cmd_invite)

    p_invite_revoke = invite_sub.add_parser("revoke",
        help="Revoke an invite key (irreversible)")
    p_invite_revoke.add_argument("key", type=str, help="The key string to revoke")
    p_invite_revoke.set_defaults(func=cmd_invite)

    p_invite_rotate = invite_sub.add_parser("rotate", help="Replace a live key, preserving participant ownership")
    p_invite_rotate.add_argument("key", help="Existing key or unique digest prefix from invite list")
    p_invite_rotate.set_defaults(func=cmd_invite)

    p_invite_create = invite_sub.add_parser("create",
        help="Create a single-use registration invite (the PLAYER picks "
             "their own name at /register)")
    p_invite_create.add_argument("--note", type=str, default=None,
                                 help="Optional free-text note (who this is for)")
    p_invite_create.set_defaults(func=cmd_invite)

    p_invite_tokens = invite_sub.add_parser("tokens",
        help="List registration invites (redeemable only by default)")
    p_invite_tokens.add_argument("--all", action="store_true",
                                 help="Include redeemed and cancelled invites")
    p_invite_tokens.set_defaults(func=cmd_invite)

    p_invite_cancel = invite_sub.add_parser("cancel",
        help="Cancel an outstanding registration invite (e.g. a leaked link)")
    p_invite_cancel.add_argument("token", type=str,
                                 help="The registration token to cancel")
    p_invite_cancel.set_defaults(func=cmd_invite)

    p_invite_duplicates = invite_sub.add_parser("duplicates",
        help="List registered names (revoked included) that are one name "
             "under persistence.name_key, with each other or with a reserved "
             "world name; read-only, exits 1 if any")
    p_invite_duplicates.set_defaults(func=cmd_invite)

    reason_help = ("Why (required; private operator data, never shown to "
                   "the player; - reads it from standard input, keeping it "
                   "out of shell history)")
    p_sanction = sub.add_parser("sanction",
        help="Suspend or ban a player with a reason, lift it, or list "
             "sanctions (owner only; reversible, unlike invite revoke)")
    sanction_sub = p_sanction.add_subparsers(dest="sanction_action",
                                             required=True)

    p_sanction_suspend = sanction_sub.add_parser("suspend",
        help="Suspend a player for a set time (1 hour to 365 days, whole "
             "hours or days)")
    p_sanction_suspend.add_argument(
        "player", help="Registered name, or participant id")
    span = p_sanction_suspend.add_mutually_exclusive_group(required=True)
    span.add_argument("--hours", type=_positive_int, help="Length in hours")
    span.add_argument("--days", type=_positive_int, help="Length in days")
    p_sanction_suspend.add_argument(
        "--reason", required=True,
        help=reason_help)
    p_sanction_suspend.set_defaults(func=cmd_sanction)

    p_sanction_ban = sanction_sub.add_parser("ban",
        help="Ban a player until the ban is lifted")
    p_sanction_ban.add_argument(
        "player", help="Registered name, or participant id")
    p_sanction_ban.add_argument(
        "--reason", required=True,
        help=reason_help)
    p_sanction_ban.set_defaults(func=cmd_sanction)

    p_sanction_lift = sanction_sub.add_parser("lift",
        help="End an active suspension or ban early")
    p_sanction_lift.add_argument("sanction_id", type=_positive_int,
                                 help="Sanction id from sanction list")
    p_sanction_lift.add_argument("--reason", required=True,
                                 help="Why it is lifted (required; - reads "
                                      "it from standard input)")
    p_sanction_lift.set_defaults(func=cmd_sanction)

    p_sanction_list = sanction_sub.add_parser("list",
        help="List active sanctions")
    p_sanction_list.add_argument("--all", action="store_true",
                                 help="Include lifted and expired sanctions")
    p_sanction_list.set_defaults(func=cmd_sanction)

    p_speak = sub.add_parser("speak", help="Speak to a node using the configured voice model")
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


def main(argv=None):
    """Run the CLI from either a source checkout or the installed script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
