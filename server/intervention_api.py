"""Player-owned previews, explicit commitments, and bounded delegated agency."""
import logging
import os

import persistence
from persistence import participants, interventions
from multiverse import interventions as physics
from agents.roster import CAST_NAMES, profile_for
from puzzles.gates import seal_check
from server import guard

_log = logging.getLogger(__name__)
ROUTES = {'/interventions', '/interventions/preview', '/interventions/commit'}


def handle(handler, path, qs, body=None):
    if path not in ROUTES:
        return False
    handler._private_response = True
    try:
        key = guard.supplied_key(handler.headers, qs)
        seed = guard.world_seed(body.get('seed') if body is not None else qs.get('seed', [''])[0])
        me = participants.identify(key)
        name = body.get('node') if body is not None else qs.get('node', [''])[0]
        if not isinstance(name, str) or not name or len(name) > 128:
            raise ValueError('Choose a place in this world.')
        nodes = interventions.lineage(seed, name)
        position = persistence.get_player_position(key)
        if path != '/interventions/commit' and seal_check(seed, nodes[0], position['node'] if position and position['seed'] == seed else None):
            raise ValueError('The seal still guards this place.')
        props = interventions.live(seed, nodes[0])
        if body is None and path == '/interventions':
            data = {'participant': me['id'], 'operators': physics.OPERATORS, 'state': physics.read_state(props),
                    'suggestions': physics.suggestions(props), 'agents': list(CAST_NAMES),
                    'recent': interventions.recent(seed, name, me['id'])}
        elif body is None:
            raise ValueError('This action needs a submission.')
        elif path == '/interventions/preview':
            steps = body.get('steps')
            delegate = body.get('delegate')
            if delegate is not None and delegate not in CAST_NAMES:
                raise ValueError('Choose a traveler from the known cast.')
            if delegate and steps is None and not body.get('intention'):
                choices = physics.suggestions(props)
                persona = profile_for(delegate).persona
                index = 1 if persona == 'destabilizer' and len(choices) > 1 else 0
                steps = choices[index]['steps']
            if steps is None:
                intention = body.get('intention')
                steps = physics.parse_score(intention)
                if steps is None:
                    if guard.ai_disabled() or not os.environ.get('ANTHROPIC_API_KEY'):
                        raise ValueError('The intention is not clear enough to enact. Compose a sequence such as “weave, charge 2, invert, release”.')
                    if not guard.consume_anthropic(user_key=key):
                        raise ValueError(guard.QUIET_RESPONSE)
                    from consciousness.interventions import propose
                    try:
                        steps = propose(intention, {'name': name, 'level': nodes[0].level,
                                                  'properties': props, 'state': physics.read_state(props)})
                    except ValueError:
                        raise
                    except Exception:
                        _log.exception('Intention proposal unavailable')
                        raise ValueError('The intention has not settled into a dependable shape. Try composing a sequence.') from None
            data = interventions.preview(seed, name, steps)
            data['delegate'] = delegate
            if delegate:
                data['invitation'] = delegate + ' offers to enact this arrangement if you entrust it to them.'
        elif path == '/interventions/commit':
            def authorize():
                current = persistence.get_player_position(key)
                if not current or current['seed'] != seed or current['node'] != name:
                    raise ValueError('Arrive at this place before committing an intervention.')
                if seal_check(seed, nodes[0], current['node']):
                    raise ValueError('The seal still guards this place.')
            delegate = body.get('delegate')
            if delegate is not None and delegate not in CAST_NAMES:
                raise ValueError('Choose a traveler from the known cast.')
            from server.handlers import _actor_identity
            data = interventions.accept(seed, me['id'], name, body.get('request_id'), body.get('steps'),
                body.get('expected'), performer=delegate or me['name'],
                actor_identity=delegate if delegate else _actor_identity(key, me['name']), delegate=delegate, authorize=authorize)
        else:
            raise ValueError('This page is read-only.')
        handler._send_json(data)
    except participants.Unauthorized as exc:
        handler._send_error(str(exc), 403)
    except (ValueError, TypeError) as exc:
        handler._send_error(str(exc), 409)
    return True
