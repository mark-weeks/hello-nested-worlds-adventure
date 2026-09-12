"""Bounded investigation reads and authenticated participant actions."""
import hashlib

from persistence import participants, situations
from multiverse import store
from puzzles.gates import seal_check
from server import guard
import persistence


def handle(handler, path, qs, body=None):
    if path not in ('/situation', '/situation/discover', '/situation/choose', '/situation/follow-up'):
        return False
    handler._private_response = True
    try:
        key = guard.supplied_key(handler.headers, qs)
        seed = guard.world_seed(body.get('seed') if body is not None else qs.get('seed', [''])[0])
        if body is None and path == '/situation':
            me = participants.identify(key) if persistence.lookup_invite_key(key) else None
            handler._send_json({'situation': situations.view(seed, me['id'] if me else None)})
            return True
        if body is None:
            raise ValueError('This action requires a submission.')
        me = participants.identify(key)
        if path == '/situation/discover':
            name = body.get('node')
            if not isinstance(name, str) or len(name) > 128:
                raise ValueError('Choose a place in this world.')
            node = store.resolve_node_by_name(seed, name)
            position = persistence.get_player_position(key)
            if node is None or not position or position['seed'] != seed or position['node'] != name:
                raise ValueError('Travel to the place before reading its clue.')
            if seal_check(seed, node, position['node']):
                raise ValueError('The ordinary seal still guards this place.')
            result = situations.discover(seed, me['id'], name)
        elif path == '/situation/choose':
            result = situations.choose(seed, me['id'], body.get('request_id'), body.get('branch'))
        elif path == '/situation/follow-up':
            result = situations.follow_up(seed, me['id'], body.get('request_id'),
                actor_identity=hashlib.sha256(key.encode()).hexdigest()[:16], player_name=me['name'])
        else:
            raise ValueError('This page is read-only.')
        handler._send_json(result)
    except participants.Unauthorized as exc:
        handler._send_error(str(exc), 403)
    except (ValueError, TypeError) as exc:
        handler._send_error(str(exc), 409)
    return True
