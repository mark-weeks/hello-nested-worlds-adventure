"""Operator community commands, separate from public HTTP endpoints."""
from __future__ import annotations

import json
import sys

from persistence import community


def _community_output(value: dict, *, error: bool = False) -> None:
    """Private operator JSON: escape every terminal control and non-ASCII byte."""
    import json
    print(json.dumps(value, ensure_ascii=True, sort_keys=True),
          file=sys.stderr if error else sys.stdout)


def cmd_community_policy(args):
    """Parse explicit community policy without activation, database or network."""
    from server import community_policy
    try:
        policy = community_policy.check_file(args.policy)
    except community_policy.CommunityPolicyError:
        _community_output({"error": "Community collection policy is invalid."}, error=True)
        raise SystemExit(1) from None
    _community_output({"configuration": community_policy.summary(policy),
                       "activated": False, "database_opened": False,
                       "live_calls": False})


def _community_note(value: str) -> str:
    """Read private triage text without shell history or unbounded stdin reads."""
    if value == "-":
        if sys.stdin.isatty():
            print("Note, then Enter and Ctrl-D:", file=sys.stderr, flush=True)
        # The ledger accepts at most 2,000 characters; allow a trailing CRLF.
        value = sys.stdin.read(2003)
        for ending in ("\r\n", "\n"):
            if value.endswith(ending):
                value = value[:-len(ending)]
                break
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError from None
    if len(value) > 2000:
        raise ValueError
    return value


def cmd_report(args):
    """Operator-only queue actions, with no model calls or notifications."""
    from persistence import community
    try:
        if args.report_action == "list":
            state = None if args.state == "all" else args.state
            result = {"reports": community.list_reports(state=state, limit=args.limit)}
        elif args.report_action == "show":
            report = community.show_report(args.report_id)
            if report is None:
                raise community.CommunityError()
            result = {"report": report}
        else:
            note = _community_note(args.note)
            operation = (community.acknowledge_report if args.report_action == "acknowledge"
                         else community.close_report)
            result = operation(args.report_id, operator=args.operator, note=note)
    except community.CommunityUnavailable:
        _community_output({"error": "Community records are unavailable."}, error=True)
        raise SystemExit(1) from None
    except (community.CommunityError, ValueError):
        _community_output({"error": "The report operation was refused."}, error=True)
        raise SystemExit(1) from None
    _community_output(result)


def cmd_community_status(_args):
    from persistence import community
    from server import community_policy
    try:
        policy = community_policy.current()
        state = community.status()
    except community_policy.CommunityPolicyError:
        _community_output({"error": "Community collection policy is invalid."}, error=True)
        raise SystemExit(1) from None
    except community.CommunityUnavailable:
        _community_output({"error": "Community records are unavailable."}, error=True)
        raise SystemExit(1) from None
    _community_output({"configuration": community_policy.summary(policy), "storage": state})
    if state.get("storage_error") or not state.get("available"):
        raise SystemExit(1)


def cmd_community_prune(_args):
    from persistence import community
    try:
        result = community.prune_expired()
    except community.CommunityUnavailable:
        _community_output({"error": "Community records are unavailable."}, error=True)
        raise SystemExit(1) from None
    _community_output({"pruned": result})


def delete_chat(args) -> None:
    try:
        result = (community.delete_chat_message(args.evidence_ref)
                  if args.chat_action == "delete" else community.delete_tester_chat(args.tester))
    except (community.UnknownTester, community.AmbiguousTester) as exc:
        _community_output({"error": str(exc)}, error=True)
        raise SystemExit(1) from None
    except community.CommunityError:
        print(json.dumps({"error": "The private chat deletion was refused."}), file=sys.stderr)
        raise SystemExit(1) from None
    except community.CommunityUnavailable:
        print(json.dumps({"error": "Private chat records are unavailable."}), file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


def deletion_ledger(args) -> None:
    """Export or replay only opaque deletion references and timestamps."""
    from persistence import community_deletions
    try:
        operation = (community_deletions.export_to if args.chat_action == "export-deletions"
                     else community_deletions.replay_from)
        result = operation(args.path)
    except community.CommunityError:
        _community_output({"error": "The deletion ledger operation was refused."}, error=True)
        raise SystemExit(1) from None
    except community.CommunityUnavailable:
        _community_output({"error": "Deletion records are unavailable."}, error=True)
        raise SystemExit(1) from None
    _community_output(result)
