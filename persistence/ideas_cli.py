"""Local operator commands; no player credential confers moderation rights."""
import json
from pathlib import Path

from persistence import ideas


def run(args):
    try:
        if args.action == 'list':
            result = ideas.operator_list(args.visibility, args.before, args.limit)
        elif args.action == 'show':
            result = ideas.operator_detail(args.id)
        elif args.action in ('prepare','preview','publish','reconcile','record-link'):
            return run_promotion(args)
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
    prepare = commands.add_parser('prepare', help='Store a reviewed public brief; does not contact GitHub')
    prepare.add_argument('id')
    prepare.add_argument('--brief', required=True, help='Local JSON file with the reviewed public fields')
    prepare.add_argument('--repository', help='GitHub owner/repository; defaults to the Enfolded repository')
    prepare.add_argument('--operator', required=True)
    preview = commands.add_parser('preview', help='Print only the reviewed public artifact and its SHA256')
    preview.add_argument('id')
    publish = commands.add_parser('publish', help='Explicitly publish the exact reviewed brief as a GitHub issue')
    publish.add_argument('id')
    publish.add_argument('--reviewed-sha256', required=True)
    publish.add_argument('--operator', required=True)
    reconcile = commands.add_parser('reconcile', help='Read GitHub to recover an interrupted publication; never creates issues')
    reconcile.add_argument('id')
    reconcile.add_argument('--operator', required=True)
    record = commands.add_parser('record-link', help='Verify and retain a matching manually published issue')
    record.add_argument('id')
    record.add_argument('url')
    record.add_argument('--operator', required=True)
    for command in (prepare,preview,publish,reconcile,record):
        command.set_defaults(func=run)
    return commands


def run_promotion(args):
    from server import idea_promotion as promotion
    try:
        if args.action == 'prepare':
            # This is operator-authored public text, never a dump of the source record.
            try:
                with Path(args.brief).open('rb') as stream:
                    raw = stream.read(32 * 1024 + 1)
            except OSError:
                raise ValueError('The public brief file could not be read. Check the file and try preparing again.') from None
            if len(raw) > 32 * 1024:
                raise ValueError('The public brief JSON file must fit within 32 KiB.')
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise ValueError('The public brief file must contain a valid JSON object.') from None
            repository = args.repository if args.repository is not None else promotion.DEFAULT_REPOSITORY
            result = promotion.prepare(args.id, data, operator=args.operator, repository=repository)
        elif args.action == 'preview':
            print(promotion.preview(args.id))
            return
        elif args.action == 'publish':
            result = promotion.publish(args.id, args.reviewed_sha256, operator=args.operator)
        elif args.action == 'reconcile':
            result = promotion.reconcile(args.id, operator=args.operator)
        else:
            result = promotion.record_link(args.id, args.url, operator=args.operator)
        print(json.dumps(result, indent=2, ensure_ascii=True))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except Exception:
        # Never echo file contents, HTTP responses, credentials or private local paths.
        if args.action == 'prepare':
            message = 'Preparation was not confirmed. Inspect the local intent before preparing again; no publication was requested.'
        elif args.action == 'preview':
            message = 'The public preview could not be read. Check the local intent and retry.'
        else:
            message = 'Promotion could not complete. Inspect the local intent and reconcile any attempted publication before retrying.'
        raise SystemExit(message) from None
