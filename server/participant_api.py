"""Authenticated profile/journal endpoints, kept outside fictional world writes."""
from persistence import participants
from multiverse import store
from server import guard, moderation


def handle(handler, path, qs, body=None):
    routes = {'/me', '/profile', '/journal/data', '/journal/note', '/profile/save', '/profile/home'}
    if path not in routes:
        return False
    handler._private_response = True
    try:
        me = participants.identify(guard.supplied_key(handler.headers, qs))
        seed = guard.world_seed(body.get('seed') if body is not None else qs.get('seed', [''])[0])
        if body is None:
            if path == '/me':
                data = {'participant': me, 'profile': participants.profile(me['id'], owner=True)}
            elif path == '/profile':
                target = qs.get('participant', [me['id']])[0]
                data = {'profile': participants.profile(target, owner=target == me['id'])}
            elif path == '/journal/data':
                data = {'seed': seed, 'participant': me,
                        'profile': participants.profile(me['id'], owner=True),
                        'notes': participants.notes(me['id'], seed),
                        'recap': participants.recap(me['id'], seed)}
            else:
                raise ValueError('This action requires a submission.')
        elif path == '/profile/save':
            # Validate shape before moderation can consume its own bounded budget.
            for field in ('bio', 'goals'):
                if not isinstance(body.get(field, ''), str) or len(body.get(field, '')) > 500:
                    raise ValueError('Bio and goals may each contain up to 500 characters.')
            if body.get('published') and not moderation.screen(body.get('bio', '') + '\n' + body.get('goals', '')).allowed:
                raise ValueError('Please revise the public profile text.')
            data = {'profile': participants.save_profile(me['id'], body)}
        elif path in ('/journal/note', '/profile/home'):
            name = body.get('node', '')
            if not isinstance(name, str) or len(name) > 128:
                raise ValueError('Choose a place in this world.')
            node = store.resolve_node_by_name(seed, name) if name else None
            if name and node is None or path == '/journal/note' and node is None:
                raise ValueError('Choose a place in this world.')
            if path == '/profile/home':
                if name and not participants.has_visited(me['id'], seed, name):
                    raise ValueError('Choose a place you have already visited.')
                participants.set_home(me['id'], seed, name or None)
                data = {'profile': participants.profile(me['id'], owner=True)}
            else:
                participants.save_note(me['id'], seed, name, body.get('text'), body.get('id'))
                data = {'saved': True}
        else:
            raise ValueError('This page is read-only.')
        handler._send_json(data)
    except participants.Unauthorized as exc:
        handler._send_error(str(exc), 403)
    except (ValueError, TypeError) as exc:
        handler._send_error(str(exc), 400)
    return True
