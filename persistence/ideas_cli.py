"""Local operator commands; no player credential confers moderation rights."""
import json

from persistence import ideas


def run(args):
    try:
        if args.action == 'list':
            result = ideas.operator_list(args.visibility, args.before, args.limit)
        elif args.action == 'show':
            result = ideas.operator_detail(args.id)
        else:
            ideas.moderate(args.id, operator=args.operator, explanation=args.explanation,
                           status=args.status, visibility=args.visibility,
                           duplicate_id=args.duplicate, availability=args.availability)
            result = ideas.operator_detail(args.id)
        print(json.dumps(result, indent=2, ensure_ascii=True))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


def add_parser(sub):
    parser = sub.add_parser('ideas', help='Review and moderate the private Ideas board')
    commands = parser.add_subparsers(dest='action', required=True)
    listing = commands.add_parser('list', help='List up to 50 community records (operator-only)')
    listing.add_argument('--visibility', choices=['visible','hidden','withdrawn'], default='visible')
    listing.add_argument('--before', type=int, default=2**63-1, help='Sequence cursor from the previous page')
    listing.add_argument('--limit', type=int, default=50)
    show = commands.add_parser('show', help='Inspect an idea locally; not a public export')
    show.add_argument('id')
    decision = commands.add_parser('decide', help='Record status, visibility, duplicate or withdrawal decisions')
    decision.add_argument('id')
    decision.add_argument('--operator', required=True)
    decision.add_argument('--explanation', required=True, help='Player-facing decision; never copy private details')
    decision.add_argument('--status', choices=list(ideas.STATUSES))
    decision.add_argument('--visibility', choices=['visible','hidden','withdrawn'])
    decision.add_argument('--duplicate', help='Surviving idea ID; votes are not transferred')
    decision.add_argument('--availability', help='Verified release/deployment evidence required for available status')
    for command in (listing, show, decision):
        command.set_defaults(func=run)
    return commands
