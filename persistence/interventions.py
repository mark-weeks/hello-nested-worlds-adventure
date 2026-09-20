"""Atomic expressive agency and recoverable, versioned consequences."""
from datetime import datetime, timedelta
import json
import logging
import secrets

import persistence as db
from persistence import intents
from multiverse import interventions as physics, interventions_v1, store

INTERPRETERS = {1: interventions_v1}

_log = logging.getLogger(__name__)
HOP_SECONDS = 12


def _now():
    return datetime.utcnow().replace(microsecond=0)


def _stamp(value):
    return value.isoformat(sep=' ')


def lineage(seed, name):
    node = store.resolve_node_by_name(seed, name)
    if node is None:
        raise ValueError('Choose a place that exists in this world.')
    result = [node]
    while result[-1].parent is not None and len(result) < 4:
        result.append(result[-1].parent)
    return result


def live(seed, node):
    return db.json_merge_patch(node.properties, db.load_node_property_override(seed, node.name))


def preview(seed, name, steps):
    nodes = lineage(seed, name)
    props = live(seed, nodes[0])
    result = physics.simulate(props, steps)
    result['expected'] = physics.digest({'properties': props, 'version': physics.VERSION})
    result['node'] = name
    result['version'] = physics.VERSION
    result['route'] = [{'node': n.name, 'level': n.level, 'in_seconds': i * HOP_SECONDS}
                       for i, n in enumerate(nodes) if i == 0 or result['signal']['strength']]
    result['tradeoff'] = ('The outward wave will brighten its surroundings and may increase regional danger.'
        if result['signal']['strength'] > 0 else
        'The returning wave will quiet its surroundings, dimming its outward reach.'
        if result['signal']['strength'] < 0 else 'This changes the local arrangement; no wave travels yet.')
    return result


def accept(seed, participant, name, request_id, steps, expected, *, performer, actor_identity, delegate=None, authorize=None):
    nodes = lineage(seed, name)  # Birth/resolve before acquiring acceptance lock.
    steps = physics.normalize_steps(steps)
    if not isinstance(expected, str) or len(expected) != 24:
        raise ValueError('Listen to a preview before committing an intervention.')
    payload = {'node': name, 'steps': steps, 'expected': expected, 'delegate': delegate}
    def apply():
        if authorize:
            authorize()
        props = live(seed, nodes[0])
        if physics.digest({'properties': props, 'version': physics.VERSION}) != expected:
            raise ValueError('This place has changed since your preview. Listen again before committing.')
        plan = physics.simulate(props, steps)
        ident = secrets.token_hex(16)
        now = _now()
        flavor = performer + ' sets a new arrangement in motion: ' + plan['summary'] + '.'
        data = {'intervention': ident, 'version': physics.VERSION, 'steps': steps,
                'flavor': flavor, 'performer': performer}
        db.record_substance_change(seed, name, 'INTERVENTION_COMMITTED', performer,
                                  data, {'resonance': plan['state']}, actor_identity=actor_identity)
        source = db.latest_event_id()
        with db._connection() as conn:
            conn.execute('''INSERT INTO interventions(id,world_seed,participant_id,node_name,version,plan,signal,route,performer,source_event_id)
                VALUES (?,?,?,?,?,?,?,?,?,?)''', (ident, seed, participant, name, physics.VERSION,
                json.dumps(plan), json.dumps(plan['signal']), json.dumps([n.name for n in nodes]), performer, source))
            if plan['signal']['strength']:
                for hop, node in enumerate(nodes[1:], 1):
                    conn.execute('''INSERT INTO intervention_work(intervention_id,hop,node_name,due_at)
                        VALUES (?,?,?,?)''', (ident, hop, node.name, _stamp(now + timedelta(seconds=hop * HOP_SECONDS))))
        return {'id': ident, 'accepted': True, 'event_id': source, 'node': name,
                'changed': {'resonance': plan['state']}, 'flavor': flavor,
                'pending_steps': len(nodes) - 1 if plan['signal']['strength'] else 0}
    result, replayed = intents.execute(participant, seed, 'intervention', request_id, payload, apply)
    if not replayed:
        notify(seed, result)
    return result


def notify(seed, result):
    from server.rooms import broadcast, get_room
    try:
        broadcast(get_room(seed), {'type': 'intervention_changed', **result})
    except Exception:
        _log.exception('Intervention committed; notification unavailable')


def advance(seed=None, *, now=None):
    db.init_db()
    now = now or _now()
    with db._connection() as conn:
        rows = conn.execute('''SELECT w.id FROM intervention_work w JOIN interventions i ON i.id=w.intervention_id
            WHERE w.status='pending' AND w.due_at<=? AND (w.retry_at IS NULL OR w.retry_at<=?)
            AND (? IS NULL OR i.world_seed=?) ORDER BY w.id LIMIT 32''', (_stamp(now), _stamp(now), seed, seed)).fetchall()
    count = 0
    for (work_id,) in rows:
        try:
            with db.transaction() as conn:
                row = conn.execute('''SELECT w.intervention_id,w.hop,w.node_name,w.status,w.due_at,w.retry_at,
                    i.world_seed,i.version,i.signal,i.source_event_id,i.performer
                    FROM intervention_work w JOIN interventions i ON i.id=w.intervention_id WHERE w.id=?''', (work_id,)).fetchone()
                ident, hop, name, status, due, retry, world, version, raw, source, performer = row
                if status != 'pending' or due > _stamp(now) or retry and retry > _stamp(now):
                    continue
                if conn.execute("SELECT 1 FROM intervention_work WHERE intervention_id=? AND hop<? AND status='pending'", (ident, hop)).fetchone():
                    continue
                interpreter = INTERPRETERS.get(version)
                if interpreter is None:
                    raise ValueError('A compatible interpreter is needed; the promise remains pending.')
                node = store.resolve_node_by_name(world, name)
                if node is None:
                    raise ValueError('The receiving place is unavailable.')
                delta, flavor = interpreter.receive(live(world, node), json.loads(raw), hop)
                db.record_substance_change(world, name, 'INTERVENTION_ARRIVED', None,
                    {'intervention': ident, 'source_event_id': source, 'hop': hop, 'flavor': flavor}, delta)
                event = db.latest_event_id()
                conn.execute("UPDATE intervention_work SET status='completed',event_id=?,last_error=NULL,retry_at=NULL WHERE id=?", (event, work_id))
            count += 1
            notify(world, {'id': ident, 'node': name, 'event_id': event, 'changed': delta, 'flavor': flavor})
        except Exception as exc:
            _log.exception('Intervention consequence remains pending: %s', work_id)
            with db.transaction() as conn:
                conn.execute("UPDATE intervention_work SET attempts=attempts+1,last_error=?,retry_at=? WHERE id=? AND status='pending'",
                             (str(exc)[:500], _stamp(now + timedelta(seconds=30)), work_id))
    return count


def recent(seed, name, participant=None):
    db.init_db()
    with db._connection() as conn:
        rows = conn.execute('''SELECT i.id,i.node_name,i.performer,i.plan,i.source_event_id,
            (SELECT COUNT(*) FROM intervention_work w WHERE w.intervention_id=i.id AND w.status='pending')
            FROM interventions i WHERE i.world_seed=? AND (i.node_name=? OR i.participant_id=? OR
            EXISTS(SELECT 1 FROM intervention_work w WHERE w.intervention_id=i.id AND w.node_name=?))
            ORDER BY i.rowid DESC LIMIT 8''', (seed, name, participant, name)).fetchall()
        result = []
        for ident, origin, performer, plan, event, pending in rows:
            arrivals = [{'node': n, 'status': s, 'event_id': e} for n, s, e in conn.execute(
                'SELECT node_name,status,event_id FROM intervention_work WHERE intervention_id=? ORDER BY hop', (ident,))]
            result.append({'id': ident, 'origin': origin, 'performer': performer, 'summary': json.loads(plan)['summary'],
                           'event_id': event, 'pending': pending, 'arrivals': arrivals})
        return result
