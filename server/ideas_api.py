"""Ideas is an authenticated, non-fictional surface; it never invokes agents."""
from persistence import ideas, participants
from server import guard, moderation, observability

READS = {'/ideas/list', '/ideas/detail'}
WRITES = {'/ideas/submit', '/ideas/vote', '/ideas/withdraw'}


def handle(handler, path, qs, body=None):
    if not path.startswith('/ideas/'):
        return False
    handler._private_response = True
    key = handler.headers.get('X-Beta-Key', '').strip()
    try:
        # Resolve active credentials before spending the shared read budget. The
        # private read helpers reuse this server identity; no body/query identity
        # can reach them. Writes still recheck the credential in their transaction.
        me = participants.identify(key)
        if (body is None or path == '/ideas/search') and not handler._read_rate_ok(path):
            return True
        # Header only: neither identity nor credentials are accepted in URLs/bodies.
        if body is None:
            if path not in READS:
                return handler._send_error('This action requires a submission.', 405) or True
            if path == '/ideas/list':
                try:
                    limit = int(qs.get('limit', ['20'])[0])
                except ValueError:
                    raise ValueError('Choose a page size between 1 and 50.') from None
                data = ideas._listing(me, sort=qs.get('sort', ['recent'])[0],
                                     q=qs.get('q', [''])[0], limit=limit,
                                     cursor=qs.get('cursor', [''])[0])
            else:
                data = ideas._detail(me, qs.get('id', [''])[0])
        elif path == '/ideas/search':
            data = ideas._listing(me, sort=body.get('sort', 'recent'), q=body.get('q', ''),
                                 limit=body.get('limit', 20), cursor=body.get('cursor', ''))
        else:
            # Authenticate before charging a write; persistence rechecks inside
            # the write transaction so revocation cannot race the commit.
            if path not in WRITES:
                return handler._send_error('This page is read-only.', 405) or True
            ideas.charge_ip(guard.client_ip(handler.client_address, handler.headers))
            if path == '/ideas/submit':
                data = ideas.submit(key, body, review=lambda text: _screen_idea(key, text),
                                     participant=me)
            elif path == '/ideas/vote':
                data = ideas.vote(key, body.get('id'), body.get('supported'))
            else:
                data = ideas.withdraw(key, body.get('id'))
        handler._send_json(data)
    except participants.Unauthorized:
        ip = guard.client_ip(handler.client_address, handler.headers)
        if guard.IDEAS_AUTH_FAILURE_RATE_LIMITER.allow(ip):
            handler._send_error('Open your current personal game invite to participate in Ideas.', 403)
        else:
            handler._send_error('Too many unsuccessful Ideas invite checks. Please wait a minute and retry.', 429)
    except ideas.Missing as exc:
        handler._send_error(str(exc), 404)
    except ideas.Conflict as exc:
        handler._send_error(str(exc), 409)
    except ideas.Limited as exc:
        handler._send_error(str(exc), 429)
    except ideas.Held as exc:
        # 422 is a finished moderation hold. The text was not published.
        # 503 stays reserved for an indeterminate failure, which the browser
        # keeps as a pending receipt. A hold must not look like one of those.
        handler._send_json({"error": str(exc), "held": True}, 422)
    except ValueError as exc:
        handler._send_error(str(exc), 400)
    except Exception as exc:
        observability.community_failure(path, exc)
        # Community input must not enter third-party exception telemetry or error bodies.
        handler._send_error('Ideas could not complete that request. Your draft is safe; please retry.', 503)
    return True


def _screen_idea(key, text):
    """Decline or hold a new idea. An existing receipt never reaches here."""
    verdict = moderation.screen(text, user_key=key, surface='ideas')
    if verdict.allowed:
        return
    if verdict.outcome == 'block':
        raise ValueError(moderation.IDEAS_DECLINE)
    raise ideas.Held(moderation.IDEAS_HOLD)
