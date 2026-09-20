"""One player's scale-native intentions, previews and explicit commitments."""
import logging
import os

import persistence
from persistence import participants, interventions
from multiverse import interventions_v2 as physics
from puzzles.gates import seal_check
from server import guard

_log = logging.getLogger(__name__)
ROUTES = {'/interventions', '/interventions/preview', '/interventions/commit'}


class Malformed(ValueError):
    """A request-shape mistake: the client's 400, never a world conflict (409)."""


_UNSHAPED = 'That intention needs a clearer shape. Choose actions below, or name them in order, separated by commas.'
_UNSETTLED = 'The intention has not settled into a dependable shape. Try the actions below.'


def _quiet(line, *, ai=False, declined=False):
    # Failure stays in fiction: the model's absence, budget or silence answers
    # HTTP 200 with an authored line and no steps, like /speak, never a conflict.
    data = {'ai': ai, 'response': line, 'steps': []}
    if declined:
        data['declined'] = True
    return data


def _propose(intention, key, name, node, props):
    """Ask the model for a score; return (steps, None) or (None, quiet reply)."""
    if guard.ai_disabled() or not os.environ.get('ANTHROPIC_API_KEY'):
        return None, _quiet(_UNSHAPED)
    if not guard.consume_anthropic(user_key=key):
        return None, _quiet(guard.QUIET_RESPONSE)
    from consciousness.interventions import Unsupported, propose
    try:
        return propose(intention, {'name': name, 'level': node.level, 'properties': props}), None
    except Unsupported as exc:
        # The model answered; its refusal is the world's reply, not a failure.
        return None, _quiet(str(exc), ai=True, declined=True)
    except Exception:
        _log.exception('Intention proposal unavailable')
        return None, _quiet(_UNSETTLED)


def _choices(seed, name, level):
    """Each single action with its full preview, so choosing one costs no write."""
    result = []
    for op, info in physics.vocabulary(level).items():
        try:
            preview = interventions.preview(seed, name, [{'op': op}], version=2)
        except ValueError as exc:
            result.append({'op': op, **info, 'available': False, 'reason': str(exc)})
        else:
            result.append({'op': op, **info, 'available': True, 'reason': None, 'preview': preview})
    return result


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
            raise Malformed('Choose a place in this world.')
        nodes = interventions.lineage(seed, name)
        node = nodes[0]
        position = persistence.get_player_position(key)
        if path != '/interventions/commit' and seal_check(seed, node, position['node'] if position and position['seed'] == seed else None):
            raise ValueError('The seal still guards this place.')
        props = interventions.live(seed, node)
        if body is None and path == '/interventions':
            data = {'participant': me['id'], 'version': physics.VERSION,
                    'operators': physics.vocabulary(node.level),
                    'choices': _choices(seed, name, node.level),
                    'state': physics.read_state(props),
                    'recent': interventions.recent(seed, name, me['id'])}
        elif body is None:
            raise ValueError('This action needs a submission.')
        elif path == '/interventions/preview':
            if any(body.get(field) is not None for field in ('delegate', 'performer', 'actor_identity')):
                raise ValueError('You may choose your own actions. Other travelers decide for themselves.')
            steps = body.get('steps')
            if steps is not None and not isinstance(steps, list):
                raise Malformed('Steps must be a list of actions.')
            quiet = None
            if steps is None:
                intention = body.get('intention')
                if intention is not None and not isinstance(intention, str):
                    raise Malformed('An intention is written in words.')
                steps = physics.parse_score(intention, node.level)
                if steps is None:
                    steps, quiet = _propose(intention, key, name, node, props)
            data = quiet or interventions.preview(seed, name, steps, version=2)
        elif path == '/interventions/commit':
            version = body.get('version', 1)  # Old clients may recover already accepted v1 receipts.
            if type(version) is not int:
                raise Malformed('The vocabulary version is a whole number.')
            if version not in interventions.INTERPRETERS:
                raise ValueError('Preview this action again with the current vocabulary.')
            if not isinstance(body.get('steps'), list):
                raise Malformed('Steps must be a list of actions.')
            def authorize():
                # Runs inside receipt acceptance; an old receipt returns without
                # re-enacting it or retroactively falsifying its historical actor.
                if any(body.get(field) is not None for field in ('delegate', 'performer', 'actor_identity')):
                    raise ValueError('You may choose your own actions. Other travelers decide for themselves.')
                if version != 2:
                    raise ValueError('This earlier vocabulary is closed to new actions. Preview a scale-native action instead.')
                current = persistence.get_player_position(key)
                if not current or current['seed'] != seed or current['node'] != name:
                    raise ValueError('Arrive at this place before acting.')
                if seal_check(seed, node, current['node']):
                    raise ValueError('The seal still guards this place.')
            from server.handlers import _actor_identity
            data = interventions.accept(seed, me['id'], name, body.get('request_id'), body.get('steps'),
                body.get('expected'), performer=me['name'], actor_identity=_actor_identity(key, me['name']),
                delegate=body.get('delegate'), authorize=authorize, version=version)
        else:
            raise ValueError('This page is read-only.')
        handler._send_json(data)
    except participants.Unauthorized as exc:
        handler._send_error(str(exc), 403)
    except (Malformed, TypeError) as exc:
        handler._send_error(str(exc), 400)
    except ValueError as exc:
        handler._send_error(str(exc), 409)
    return True
