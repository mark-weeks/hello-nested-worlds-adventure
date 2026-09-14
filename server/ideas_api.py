"""Ideas is an authenticated, non-fictional surface; it never invokes agents."""
from persistence import ideas, participants
from server import guard, observability

READS = {'/ideas/list', '/ideas/detail'}
WRITES = {'/ideas/submit', '/ideas/vote', '/ideas/withdraw'}


def handle(handler, path, qs, body=None):
    if not path.startswith('/ideas/'):
        return False
    handler._private_response = True
    key = handler.headers.get('X-Beta-Key', '').strip()
    try:
        # Header only: neither identity nor credentials are accepted in URLs/bodies.
        if body is None:
            if path not in READS:
                participants.identify(key)
                return handler._send_error('This action requires a submission.', 405) or True
            if path == '/ideas/list':
                try:
                    limit = int(qs.get('limit', ['20'])[0])
                except ValueError:
                    raise ValueError('Choose a page size between 1 and 50.') from None
                data = ideas.listing(key, sort=qs.get('sort', ['recent'])[0],
                                     q=qs.get('q', [''])[0], limit=limit,
                                     cursor=qs.get('cursor', [''])[0])
            else:
                data = ideas.detail(key, qs.get('id', [''])[0])
        elif path == '/ideas/search':
            data = ideas.listing(key, sort=body.get('sort', 'recent'), q=body.get('q', ''),
                                 limit=body.get('limit', 20), cursor=body.get('cursor', ''))
        else:
            # Authenticate before charging a write; persistence rechecks inside
            # the write transaction so revocation cannot race the commit.
            participants.identify(key)
            if path not in WRITES:
                return handler._send_error('This page is read-only.', 405) or True
            ideas.charge_ip(guard.client_ip(handler.client_address, handler.headers))
            if path == '/ideas/submit':
                data = ideas.submit(key, body)
            elif path == '/ideas/vote':
                data = ideas.vote(key, body.get('id'), body.get('supported'))
            else:
                data = ideas.withdraw(key, body.get('id'))
        handler._send_json(data)
    except participants.Unauthorized:
        handler._send_error('Open your current personal game invite to participate in Ideas.', 403)
    except ideas.Missing as exc:
        handler._send_error(str(exc), 404)
    except ideas.Conflict as exc:
        handler._send_error(str(exc), 409)
    except ideas.Limited as exc:
        handler._send_error(str(exc), 429)
    except ValueError as exc:
        handler._send_error(str(exc), 400)
    except Exception as exc:
        observability.community_failure(path, exc)
        # Community input must not enter third-party exception telemetry or error bodies.
        handler._send_error('Ideas could not complete that request. Your draft is safe; please retry.', 503)
    return True
