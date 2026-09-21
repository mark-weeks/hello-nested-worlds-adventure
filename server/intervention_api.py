"""One player's scale-native attempts, clarification and recoverable commitments."""
import logging
import os

import persistence
from persistence import participants, interventions, intents
from multiverse import interventions_v3 as physics
from puzzles.gates import seal_check
from server import guard

_log = logging.getLogger(__name__)
ROUTES = {'/interventions', '/interventions/preview', '/interventions/commit'}


class Malformed(ValueError):
    """A request-shape mistake: the client's 400, never a world conflict (409)."""


_UNSHAPED = 'That intention needs a clearer shape. Choose actions below, or name them in order, separated by commas.'
_UNSETTLED = 'The intention has not settled into a dependable shape. Try the actions below.'


def _quiet(line, *, ai=False, declined=False, clarification=False):
    data = {'ai': ai, 'response': line, 'steps': [], 'accepted': False}
    if declined:
        data['declined'] = True
    if clarification:
        data['clarification'] = True
    return data


def _propose(intention, key, name, node, props):
    if guard.ai_disabled() or not os.environ.get('ANTHROPIC_API_KEY'):
        return None, _quiet(_UNSHAPED)
    if not guard.consume_anthropic(user_key=key):
        return None, _quiet(guard.QUIET_RESPONSE)
    from consciousness.interventions import Clarification, Unsupported, propose
    try:
        return propose(intention, {'name': name, 'level': node.level, 'properties': props}), None
    except Clarification as exc:
        return None, _quiet(str(exc), ai=True, clarification=True)
    except Unsupported as exc:
        return None, _quiet(str(exc), ai=True, declined=True)
    except Exception:
        _log.exception('Intention interpretation unavailable')
        return None, _quiet(_UNSETTLED)


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
        node = interventions.lineage(seed, name)[0]
        position = persistence.get_player_position(key)
        if path != '/interventions/commit' and seal_check(seed, node, position['node'] if position and position['seed'] == seed else None):
            raise ValueError('The seal still guards this place.')
        if body is not None:
            if 'steps' in body and not isinstance(body['steps'], list):
                raise Malformed('Steps must be a list of actions.')
            if 'intention' in body and not isinstance(body['intention'], str):
                raise Malformed('An intention is written in words.')
        if body is None and path == '/interventions':
            data = {'participant': me['id'], 'version': physics.VERSION,
                    'operators': physics.vocabulary(node.level),
                    'choices': [{'op': op, **info, 'available': True, 'reason': None}
                                for op, info in physics.vocabulary(node.level).items()],
                    'state': physics.read_state(interventions.live(seed, node)),
                    'recent': interventions.recent(seed, name, me['id'])}
        elif body is None:
            raise ValueError('This action needs a submission.')
        elif path == '/interventions/preview':
            raise ValueError('Choose an action or submit an intention to attempt it. Consequences are discovered as they occur.')
        elif path == '/interventions/commit':
            version = body.get('version', 1)  # Missing version can recover historical v1 receipts.
            if type(version) is not int:
                raise Malformed('The vocabulary version is a whole number.')
            if version not in interventions.INTERPRETERS:
                raise ValueError('Choose an action from the current vocabulary.')
            def authorize():
                if any(body.get(field) is not None for field in ('delegate', 'performer', 'actor_identity')):
                    raise ValueError('You may choose your own actions. Other travelers decide for themselves.')
                if version != 3:
                    raise ValueError('This earlier vocabulary is closed to new actions. Choose a scale-native action again.')
                current = persistence.get_player_position(key)
                if not current or current['seed'] != seed or current['node'] != name:
                    raise ValueError('Arrive at this place before acting.')
                if seal_check(seed, node, current['node']):
                    raise ValueError('The seal still guards this place.')
            from server.handlers import _actor_identity
            if version < 3:
                if not isinstance(body.get('steps'), list):
                    raise Malformed('Steps must be a list of actions.')
                # Receipt lookup in accept precedes authorization. No historical
                # actor, payload, signal or pending semantics is reinterpreted.
                data = interventions.accept(seed, me['id'], name, body.get('request_id'), body.get('steps'),
                    body.get('expected'), performer=me['name'], actor_identity=_actor_identity(key, me['name']),
                    delegate=body.get('delegate'), authorize=authorize, version=version)
            else:
                if set(body) - {'node', 'seed', 'version', 'request_id', 'steps', 'intention', 'delegate', 'performer', 'actor_identity'}:
                    raise Malformed('This attempt includes a choice that is not supported.')
                if ('steps' in body) == ('intention' in body):
                    raise Malformed('Submit actions or an intention, one at a time.')
                submission = {'steps': physics.normalize_steps(body['steps'], node.level)} if 'steps' in body else {'intention': body['intention']}
                if 'intention' in submission and not 1 <= len(submission['intention'].strip()) <= 600:
                    raise ValueError('Describe your intention in at most 600 characters.')
                # Include authority fields in the fingerprint: a changed retry
                # cannot smuggle a different performer past receipt recovery. An
                # explicit null is what authorize() ignores, so it matches an
                # omitted key and a lost-ack retry still recovers its receipt.
                payload = {'node': name, 'version': version, **submission,
                           **{f: body[f] for f in ('delegate', 'performer', 'actor_identity') if body.get(f) is not None}}
                request = body.get('request_id')
                data = intents.lookup(me['id'], seed, 'intervention', request, payload)
                if data is None:
                    authorize()
                    quiet = None
                    steps = submission.get('steps')
                    if steps is None:
                        steps = physics.parse_score(submission['intention'], node.level)
                        if steps is None:
                            steps, quiet = _propose(submission['intention'], key, name, node, interventions.live(seed, node))
                    if quiet:
                        # Linearize ALL replies with concurrent submissions of
                        # this ID, including provider silence. A reply saying no
                        # attempt was accepted must never race a later acceptance.
                        data, _ = intents.execute(me['id'], seed, 'intervention', request, payload, lambda: quiet)
                    else:
                        data = interventions.accept_attempt(seed, me['id'], name, request, payload, steps,
                            performer=me['name'], actor_identity=_actor_identity(key, me['name']), authorize=authorize)
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
