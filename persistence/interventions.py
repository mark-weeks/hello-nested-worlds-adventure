"""Atomic expressive agency and recoverable, versioned consequences."""
from datetime import datetime, timedelta
import json
import logging
import secrets

import persistence as db
from persistence import intents
from multiverse import interventions_v1, interventions_v2, interventions_v3, store
from multiverse.verbs import maturation_seconds

INTERPRETERS = {1: interventions_v1, 2: interventions_v2, 3: interventions_v3}

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


def _record(seed, name, kind, performer, data, delta, actor_identity=None):
    if delta:
        db.record_substance_change(seed, name, kind, performer, data, delta, actor_identity=actor_identity)
    else:
        db.record_mutation(seed, name, kind, performer, data, actor_identity=actor_identity)


def _plan(interpreter, props, steps, node):
    if interpreter.VERSION == 1:
        plan = interpreter.simulate(props, steps)
        return {**plan, 'changed': {'resonance': plan['state']}}
    return interpreter.simulate(props, steps, node.level, node.name)


def preview(seed, name, steps, *, version=1):
    if version not in (1, 2):
        raise ValueError('Attempted actions do not have a forecast.')
    nodes = lineage(seed, name)
    interpreter = INTERPRETERS[version]
    props = live(seed, nodes[0])
    result = _plan(interpreter, props, steps, nodes[0])
    result['expected'] = interpreter.digest({'properties': props, 'version': version})
    result['node'] = name
    result['version'] = version
    delay = maturation_seconds(nodes[0].level) if version == 2 else 0
    result['matures_in'] = delay
    result['route'] = [{'node': n.name, 'level': n.level, 'in_seconds': delay + i * HOP_SECONDS}
                       for i, n in enumerate(nodes) if i == 0 or result['signal']['strength']]
    result['tradeoff'] = ('An outward disturbance will travel through enclosing places; it may increase danger.'
        if result['signal']['strength'] > 0 else
        'A quieting disturbance will travel through enclosing places; it may reduce danger.'
        if result['signal']['strength'] < 0 else 'This changes the local material; no disturbance travels outward.')
    if delay:
        result['tradeoff'] += f' The first change takes about {round(delay / 60)} minutes, meeting the conditions then.'
    return result


def accept(seed, participant, name, request_id, steps, expected, *, performer, actor_identity,
           delegate=None, authorize=None, version=1):
    if version not in (1, 2):
        raise ValueError('This vocabulary commits attempts without a forecast.')
    nodes = lineage(seed, name)
    interpreter = INTERPRETERS.get(version)
    if interpreter is None:
        raise ValueError('This action belongs to an unavailable vocabulary.')
    steps = interpreter.normalize_steps(steps)
    if not isinstance(expected, str) or len(expected) != 24:
        raise ValueError('Preview the consequences before acting.')
    # The v1 receipt shape must survive upgrades, including historical delegation.
    payload = {'node': name, 'steps': steps, 'expected': expected, 'delegate': delegate}
    if version != 1:
        payload['version'] = version
    def apply():
        if authorize:
            authorize()
        props = live(seed, nodes[0])
        if interpreter.digest({'properties': props, 'version': version}) != expected:
            raise ValueError('This place has changed since your preview. Listen again before committing.')
        plan = _plan(interpreter, props, steps, nodes[0])
        ident = secrets.token_hex(16)
        now = _now()
        delay = maturation_seconds(nodes[0].level) if version == 2 else 0
        flavor = performer + (' begins ' if delay else ' acts: ') + plan['summary'] + '.'
        if delay:
            flavor += ' Its material change is still travelling.'
        data = {'intervention': ident, 'version': version, 'steps': steps,
                'flavor': flavor, 'performer': performer}
        changed = {} if delay else plan['changed']
        _record(seed, name, 'INTERVENTION_COMMITTED', performer,
                                  data, changed, actor_identity=actor_identity)
        source = db.latest_event_id()
        with db._connection() as conn:
            conn.execute('''INSERT INTO interventions(id,world_seed,participant_id,node_name,version,plan,signal,route,performer,source_event_id)
                VALUES (?,?,?,?,?,?,?,?,?,?)''', (ident, seed, participant, name, version,
                json.dumps(plan), json.dumps(plan['signal']), json.dumps([n.name for n in nodes]), performer, source))
            for hop, node in enumerate(nodes):
                if (hop == 0 and delay) or (hop > 0 and plan['signal']['strength']):
                    conn.execute('''INSERT INTO intervention_work(intervention_id,hop,node_name,due_at)
                        VALUES (?,?,?,?)''', (ident, hop, node.name, _stamp(now + timedelta(seconds=delay + hop * HOP_SECONDS))))
        return {'id': ident, 'accepted': True, 'event_id': source, 'node': name,
                'changed': changed, 'flavor': flavor,
                'pending_steps': (len(nodes) - 1 if plan['signal']['strength'] else 0) + bool(delay)}
    result, replayed = intents.execute(participant, seed, 'intervention', request_id, payload, apply)
    if not replayed:
        notify(seed, result)
    return result


def accept_attempt(seed, participant, name, request_id, payload, steps, *, performer, actor_identity, authorize):
    node = lineage(seed, name)[0]
    plan = interventions_v3.attempt(steps, node.level, name)
    def apply():
        authorize()
        ident, now = secrets.token_hex(16), _now()
        flavor = f'{performer} attempts {plan["summary"]}.'
        _record(seed, name, 'INTERVENTION_COMMITTED', performer,
                {'intervention': ident, 'version': 3, 'steps': plan['steps'],
                 'phase': 'accepted', 'flavor': flavor, 'performer': performer}, {}, actor_identity)
        source = db.latest_event_id()
        with db._connection() as conn:
            conn.execute("""INSERT INTO interventions(id,world_seed,participant_id,node_name,version,plan,signal,route,performer,source_event_id)
                VALUES (?,?,?,?,3,?,'{}','[]',?,?)""",
                (ident, seed, participant, name, json.dumps(plan), performer, source))
            delay = maturation_seconds(node.level)
            work_id = conn.execute("""INSERT INTO intervention_work(intervention_id,hop,node_name,due_at)
                VALUES (?,0,?,?)""", (ident, name, _stamp(now + timedelta(seconds=delay)))).lastrowid
            observed = None if delay else _settle_attempt(conn, work_id, ident, 0, node, seed, source, plan, now)
            pending = conn.execute("SELECT COUNT(*) FROM intervention_work WHERE intervention_id=? AND status='pending'", (ident,)).fetchone()[0]
        # An instant local settlement can still queue outward hops: the phase
        # and the pending line follow the queue, not the origin's delay alone.
        if observed:
            flavor += ' ' + observed['flavor']
        if pending:
            flavor += ' Consequences are pending.'
        return {'id': ident, 'accepted': True, 'phase': 'pending' if pending else 'observed',
                'event_id': source, 'node': name, 'changed': observed['changed'] if observed else {},
                'flavor': flavor, 'observed': observed, 'pending_steps': pending}
    result, replayed = intents.execute(participant, seed, 'intervention', request_id, payload, apply)
    if not replayed:
        notify(seed, result)
    return result


def _settle_attempt(conn, work_id, ident, hop, node, world, source, plan, now):
    """Effect, observed signal, continuation and completion share one transaction."""
    physics = interventions_v3
    if hop == 0:
        delta, signal, outcomes = physics.settle(live(world, node), plan)
        flavor = 'The attempted action settles. ' + ' '.join(
            f"{interventions_v2.OPERATORS[o['op']]['label']}: {physics.describe(o)}" for o in outcomes)
        if not delta and any(o['changed'] for o in outcomes):
            flavor += ' No net material change remains.'
    else:
        previous = conn.execute("""SELECT event_id FROM intervention_work
            WHERE intervention_id=? AND hop=? AND status='completed'""", (ident, hop - 1)).fetchone()
        if not previous:
            raise ValueError('The preceding consequence has not yet arrived.')
        signal = json.loads(conn.execute('SELECT signal FROM interventions WHERE id=?', (ident,)).fetchone()[0])
        if not signal:
            # Compatibility with v3 work accepted before observed signals were
            # retained operationally. Never recompute a missing observed signal.
            historical = conn.execute('SELECT data FROM world_mutations WHERE id=?', previous).fetchone()
            if not historical:
                raise ValueError('The preceding observed signal needs recovery.')
            signal = json.loads(historical[0])['signal']
        delta, signal, flavor = physics.receive(live(world, node), signal)
        outcomes = []
    data = {'intervention': ident, 'version': 3, 'source_event_id': source, 'hop': hop,
            'phase': 'observed', 'flavor': flavor, 'materialized': bool(delta), 'signal': signal, 'outcomes': outcomes}
    _record(world, node.name, 'INTERVENTION_ARRIVED', None, data, delta)
    event = db.latest_event_id()
    # One ordered chain has at most one pending successor. Keep its input in
    # operational storage, atomically with this observation and completion.
    conn.execute('UPDATE interventions SET signal=? WHERE id=?', (json.dumps(signal), ident))
    if signal['strength'] and hop < 3 and node.parent is not None:
        conn.execute("""INSERT INTO intervention_work(intervention_id,hop,node_name,due_at)
            VALUES (?,?,?,?)""", (ident, hop + 1, node.parent.name, _stamp(now + timedelta(seconds=HOP_SECONDS))))
    conn.execute("UPDATE intervention_work SET status='completed',event_id=?,last_error=NULL,retry_at=NULL WHERE id=?", (event, work_id))
    return {'event_id': event, 'node': node.name, 'changed': delta, 'flavor': flavor, 'outcomes': outcomes}


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
        # Work that nothing blocks sorts ahead of hops waiting on an earlier
        # hop, so a run of failed first hops cannot fill the batch with their
        # blocked successors and starve independent eligible work. Successors
        # still ride in the same batch when there is room: once their
        # predecessor lands earlier in this pass, the recheck below lets them go.
        rows = conn.execute('''SELECT w.id FROM intervention_work w JOIN interventions i ON i.id=w.intervention_id
            WHERE w.status='pending' AND w.due_at<=? AND (w.retry_at IS NULL OR w.retry_at<=?)
            AND (? IS NULL OR i.world_seed=?)
            ORDER BY EXISTS (SELECT 1 FROM intervention_work p WHERE p.intervention_id=w.intervention_id
                             AND p.hop<w.hop AND p.status='pending'), w.id LIMIT 32''',
            (_stamp(now), _stamp(now), seed, seed)).fetchall()
    count = 0
    for (work_id,) in rows:
        try:
            with db.transaction() as conn:
                row = conn.execute('''SELECT w.intervention_id,w.hop,w.node_name,w.status,w.due_at,w.retry_at,
                    i.world_seed,i.version,i.signal,i.source_event_id,i.performer,i.plan
                    FROM intervention_work w JOIN interventions i ON i.id=w.intervention_id WHERE w.id=?''', (work_id,)).fetchone()
                ident, hop, name, status, due, retry, world, version, raw, source, performer, raw_plan = row
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
                if version == 3:
                    observed = _settle_attempt(conn, work_id, ident, hop, node, world, source, json.loads(raw_plan), now)
                    delta, flavor, event = observed['changed'], observed['flavor'], observed['event_id']
                else:
                    if hop == 0 and version == 2:
                        plan = json.loads(raw_plan)
                        try:
                            settled = interpreter.simulate(live(world, node), plan['steps'], plan['level'], plan['token'])
                            delta, flavor = settled['changed'], 'The delayed action settles: ' + settled['summary'] + '.'
                        except ValueError:
                            # Changed conditions can make an accepted action moot. Record that
                            # outcome once; never keep retrying a physically impossible promise.
                            delta, flavor = {}, 'The delayed action meets changed conditions and leaves no new material change.'

                    else:
                        source_outcome = conn.execute("""SELECT m.data FROM intervention_work w
                            JOIN world_mutations m ON m.id=w.event_id
                            WHERE w.intervention_id=? AND w.hop=0 AND w.status='completed'""", (ident,)).fetchone()
                        if source_outcome and not json.loads(source_outcome[0]).get('materialized'):
                            delta, flavor = {}, 'No disturbance arrives: its source met changed conditions.'
                        else:
                            delta, flavor = interpreter.receive(live(world, node), json.loads(raw), hop)
                    _record(world, name, 'INTERVENTION_ARRIVED', None,
                        {'intervention': ident, 'source_event_id': source, 'hop': hop, 'flavor': flavor, 'materialized': bool(delta)}, delta)
                    event = db.latest_event_id()
                    conn.execute("UPDATE intervention_work SET status='completed',event_id=?,last_error=NULL,retry_at=NULL WHERE id=?", (event, work_id))
            count += 1
            notify(world, {'id': ident, 'node': name, 'event_id': event, 'changed': delta, 'flavor': flavor})
        except Exception as exc:
            # Same retention policy as persistence.deliver_work: capped exponential
            # backoff (1..300s) and no attempt limit, so a promise is never silently
            # discarded. The traceback is logged once; later retries log a line.
            with db.transaction() as conn:
                attempts = conn.execute('SELECT attempts FROM intervention_work WHERE id=?', (work_id,)).fetchone()
                conn.execute("""UPDATE intervention_work SET attempts=attempts+1,last_error=?,
                    retry_at=datetime(?, '+' || min(300, (1 << min(attempts, 9))) || ' seconds')
                    WHERE id=? AND status='pending'""", (str(exc)[:500], _stamp(now), work_id))
            first = not attempts or attempts[0] == 0
            _log.log(logging.ERROR if first else logging.WARNING,
                     'Intervention consequence remains pending: %s (%s: %s)', work_id, type(exc).__name__, exc,
                     exc_info=first)
    return count


def recent(seed, name, participant=None):
    db.init_db()
    with db._connection() as conn:
        # Unsettled commitments come first so the composer keeps polling for them
        # even when eight newer, settled records exist.
        rows = conn.execute('''SELECT id,node_name,performer,plan,source_event_id,pending FROM (
                SELECT i.id,i.node_name,i.performer,i.plan,i.source_event_id,i.rowid AS position,
                    (SELECT COUNT(*) FROM intervention_work w WHERE w.intervention_id=i.id AND w.status='pending') AS pending
                FROM interventions i WHERE i.world_seed=? AND (i.node_name=? OR i.participant_id=? OR
                EXISTS(SELECT 1 FROM intervention_work w WHERE w.intervention_id=i.id AND w.node_name=? AND w.status='completed')))
            ORDER BY (pending>0) DESC, position DESC LIMIT 8''', (seed, name, participant, name)).fetchall()
        result = []
        for ident, origin, performer, plan, event, pending in rows:
            arrivals = []
            for n, e, data in conn.execute(
                """SELECT w.node_name,w.event_id,m.data FROM intervention_work w JOIN world_mutations m ON m.id=w.event_id
                   WHERE w.intervention_id=? AND w.status='completed' ORDER BY w.hop""", (ident,)):
                observed = json.loads(data)
                arrivals.append({'node': n, 'status': 'completed', 'event_id': e,
                                 'flavor': observed.get('flavor', ''), 'materialized': observed.get('materialized')})
            result.append({'id': ident, 'origin': origin, 'performer': performer, 'summary': json.loads(plan)['summary'],
                           'event_id': event, 'phase': 'pending' if pending else 'observed',
                           'pending': pending, 'arrivals': arrivals})
        return result
