"""Atomic, bounded progression for the first shared situation (ADR-025)."""
from datetime import datetime, timedelta, timezone
import json
import logging
import secrets

import persistence as db
from persistence import intents
from multiverse import store
from multiverse.situation import definition, SLUG

_log = logging.getLogger(__name__)
FIELDS = 'id,world_seed,definition_version,definition,phase,deadline,branch,opened_event_id,commitment_event_id,outcome_event_id'
KEYS = FIELDS.split(',')


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _stamp(value):
    return value.isoformat(sep=' ')


def _decode(row):
    result = dict(zip(KEYS, row))
    result['definition'] = json.loads(result['definition'])
    return result


def _read(conn, seed):
    row = conn.execute(f'SELECT {FIELDS} FROM situations WHERE world_seed=? AND slug=?',
                       (seed, SLUG)).fetchone()
    return _decode(row) if row else None


def install(seed):
    db.init_db()
    with db._connection() as conn:
        existing = _read(conn, seed)
        if existing:
            return existing['id']
    spec = definition(seed)  # Resolve/birth outside an acceptance transaction.
    with db.transaction() as conn:
        existing = _read(conn, seed)
        if existing:
            return existing['id']
        instance = secrets.token_hex(16)
        conn.execute('''INSERT INTO situations(id,world_seed,slug,definition_version,definition)
            VALUES (?,?,?,?,?)''', (instance, seed, SLUG, 1, json.dumps(spec)))
        db.record_mutation(seed, spec['nodes']['gallery'], 'SITUATION_OPENED', None,
            {'situation': instance, 'definition_version': 1, 'authored': True,
             'flavor': 'A recurring signal sounds in the gallery. Tessera offers to trace its next passage.'})
        conn.execute('UPDATE situations SET opened_event_id=? WHERE id=?', (db.latest_event_id(), instance))
    return instance


def view(seed, participant=None):
    db.init_db()
    with db._connection() as conn:
        situation = _read(conn, seed)
        if not situation:
            return None
        spec = situation['definition']
        counts = dict(conn.execute('SELECT branch,COUNT(*) FROM situation_choices WHERE situation_id=? GROUP BY branch',
                                   (situation['id'],)))
        choice = conn.execute('SELECT branch FROM situation_choices WHERE situation_id=? AND participant_id=?',
                              (situation['id'], participant)).fetchone() if participant else None
        discoveries = [r[0] for r in conn.execute('''SELECT node_name FROM situation_discoveries
            WHERE situation_id=? AND participant_id=?''', (situation['id'], participant))] if participant else []
        followed = bool(conn.execute('SELECT 1 FROM situation_followups WHERE situation_id=? AND participant_id=?',
                                    (situation['id'], participant)).fetchone()) if participant else False
        pending = conn.execute('SELECT COUNT(*) FROM situation_work WHERE situation_id=? AND status=?',
                               (situation['id'], 'pending')).fetchone()[0]
    return {'id': situation['id'], 'title': spec['title'], 'phase': situation['phase'],
            'entry': spec['entry'], 'nodes': spec['nodes'], 'keeper': spec['keeper'],
            'branches': spec['branches'], 'promise': spec['promise'], 'deadline': situation['deadline'],
            'branch': situation['branch'], 'counts': counts, 'choice': choice[0] if choice else None,
            'discoveries': discoveries, 'followed_up': followed, 'pending_steps': pending,
            'opened_event_id': situation['opened_event_id'],
            'commitment_event_id': situation['commitment_event_id'],
            'outcome_event_id': situation['outcome_event_id']}


def discover(seed, participant, node):
    with db.transaction() as conn:
        situation = _read(conn, seed)
        if not situation:
            raise ValueError('There is no open investigation here.')
        role = next((role for role, name in situation['definition']['nodes'].items() if name == node), None)
        if role is None:
            raise ValueError('That place carries no clue for this investigation.')
        conn.execute('''INSERT INTO situation_discoveries(situation_id,participant_id,node_name)
            VALUES (?,?,?) ON CONFLICT DO NOTHING''', (situation['id'], participant, node))
        clue = situation['definition']['clues'][role]
        if role == 'fold' and situation['phase'] == 'aftermath':
            clue = ('Tessera’s lasting mark records the ' + situation['branch'] +
                    ' route. The promise is fulfilled in recorded event #' + str(situation['outcome_event_id']) + '.')
        if role == 'chain' and situation['phase'] == 'aftermath':
            count = conn.execute('SELECT COUNT(*) FROM situation_followups WHERE situation_id=?', (situation['id'],)).fetchone()[0]
            clue += f' The lasting echo records the {situation["branch"]} route; {count} reference markers have been left for comparison.'
        return {'clue': clue, 'node': node}


def _settle(conn, situation, now):
    if situation['phase'] != 'decision' or datetime.fromisoformat(situation['deadline']) > now:
        return False
    if situation['definition_version'] != 1:
        raise ValueError('This situation needs a compatible decision interpreter.')
    counts = dict(conn.execute('SELECT branch,COUNT(*) FROM situation_choices WHERE situation_id=? GROUP BY branch',
                               (situation['id'],)))
    if counts.get('preserve', 0) == counts.get('release', 0):
        conn.execute('UPDATE situations SET deadline=? WHERE id=?',
            (_stamp(now + timedelta(seconds=situation['definition']['window_seconds'])), situation['id']))
        return False
    branch = max(counts, key=counts.get)
    spec = situation['definition']
    db.record_substance_change(situation['world_seed'], spec['nodes']['regulator'], 'SITUATION_COMMITTED', None,
        {'situation': situation['id'], 'branch': branch, 'source_event_id': situation['opened_event_id'],
         'flavor': ('The shared decision holds: ' + spec['branches'][branch]['label'] + '. ' + spec['promise'])},
        {'signal_control': 'held' if branch == 'preserve' else 'released'})
    source = db.latest_event_id()
    conn.execute('UPDATE situations SET phase=?,branch=?,commitment_event_id=? WHERE id=?',
                 ('pending', branch, source, situation['id']))
    for step in range(3):
        conn.execute('INSERT INTO situation_work(situation_id,step,due_at) VALUES (?,?,?)',
            (situation['id'], step, _stamp(now + timedelta(seconds=spec['step_seconds'] * step))))
    return True


def _settle_overdue(seed):
    """Close an expired window in its own commit before a choice is judged.

    The commitment must never share a transaction with the choice that
    arrives after it: rejecting that late choice would otherwise roll the
    commitment back, leaving the window open with no pump to close it.
    """
    now = _now()
    with db._connection() as conn:
        situation = _read(conn, seed)
    if (not situation or situation['phase'] != 'decision'
            or datetime.fromisoformat(situation['deadline']) > now):
        return  # Nothing to close; _settle re-checks under the write lock.
    with db.transaction() as conn:
        situation = _read(conn, seed)
        if situation:
            _settle(conn, situation, now)


def choose(seed, participant, request_id, branch):
    _settle_overdue(seed)

    def apply():
        with db._connection() as conn:
            situation = _read(conn, seed)
            if not situation:
                raise ValueError('There is no open investigation here.')
            if branch not in situation['definition']['branches']:
                raise ValueError('Choose one of the two signal routes.')
            if situation['phase'] not in ('investigate', 'decision'):
                raise ValueError('The shared decision has already been made. You can investigate its aftermath.')
            known = {r[0] for r in conn.execute('SELECT node_name FROM situation_discoveries WHERE situation_id=? AND participant_id=?',
                                               (situation['id'], participant))}
            required = {situation['definition']['nodes'][role] for role in situation['definition']['required_clues']}
            if not required <= known:
                raise ValueError('Read the instrument and regulator before choosing their future.')
            deadline = situation['deadline'] or _stamp(_now() + timedelta(seconds=situation['definition']['window_seconds']))
            conn.execute('UPDATE situations SET phase=?,deadline=? WHERE id=?', ('decision', deadline, situation['id']))
            conn.execute('''INSERT INTO situation_choices(situation_id,participant_id,branch) VALUES (?,?,?)
                ON CONFLICT(situation_id,participant_id) DO UPDATE SET branch=excluded.branch''',
                (situation['id'], participant, branch))
            return {'recorded': True, 'branch': branch, 'deadline': deadline,
                    'message': 'Your preference is recorded. The shared decision is still open.'}
    return intents.execute(participant, seed, 'situation-choice', request_id, {'branch': branch}, apply)[0]


def _land(conn, work, situation):
    if situation['definition_version'] != 1:
        raise ValueError('Unsupported situation version; retained for a compatible worker.')
    spec, branch, seed = situation['definition'], situation['branch'], situation['world_seed']
    step = work['step']
    role = ('gallery', 'region', 'fold')[step]
    node = store.resolve_node_by_name(seed, spec['nodes'][role])
    if node is None:
        raise ValueError('An authored place is unavailable; work remains pending.')
    if step == 0:
        delta = {'lighting': 'steady' if branch == 'preserve' else 'flickering', 'signal_route': branch}
        flavor = ('The gallery steadies around the enclosed signal.' if branch == 'preserve' else
                  'The gallery’s steady light gives way; the released signal passes outward.')
    elif step == 1:
        live = db.json_merge_patch(node.properties, db.load_node_property_override(seed, node.name))
        danger = live.get('danger_level')
        if type(danger) is not int:
            raise ValueError('The terraces cannot yet receive this change.')
        delta = {'danger_level': max(1, min(10, danger + (-1 if branch == 'preserve' else 1))), 'signal_route': branch}
        flavor = ('The orchard grows calmer, but the enclosed signal does not reach it.' if branch == 'preserve' else
                  'The orchard hears the freed signal; its paths grow less settled.')
    else:
        delta = {'signal_echo': branch}
        flavor = ('Tessera has kept the promise. A lasting mark in the Fold records the ' +
                  ('enclosed' if branch == 'preserve' else 'released') + ' signal. What will you make of its aftermath?')
    data = {'situation': situation['id'], 'branch': branch, 'step': step,
            'source_event_id': situation['commitment_event_id'], 'flavor': flavor}
    db.record_substance_change(seed, node.name, 'SITUATION_CONSEQUENCE', None, data, delta)
    event = db.latest_event_id()
    conn.execute('UPDATE situation_work SET status=?,event_id=?,last_error=NULL WHERE id=?', ('completed', event, work['id']))
    if step == 2:
        conn.execute('UPDATE situations SET phase=?,outcome_event_id=? WHERE id=?', ('aftermath', event, situation['id']))
    return {'type': 'situation_changed', 'node': node.name, 'event_id': event, 'flavor': flavor}


def advance(seed=None, *, now=None):
    """Bounded pump: one situation per world, at most 16 decisions / 32 work items."""
    db.init_db()
    now = now or _now()
    where, args = (' AND world_seed=?', (seed,)) if seed is not None else ('', ())
    with db._connection() as conn:
        candidates = conn.execute(f'SELECT world_seed FROM situations WHERE phase=?{where} LIMIT 16', ('decision', *args)).fetchall()
    for (world,) in candidates:
        try:
            with db.transaction() as conn:
                situation = _read(conn, world)
                _settle(conn, situation, now)
        except Exception:
            _log.exception('Situation decision for world %s remains pending', world)
    with db._connection() as conn:
        rows = conn.execute(f'''SELECT w.id,s.world_seed FROM situation_work w JOIN situations s ON s.id=w.situation_id
            WHERE w.status='pending' AND w.due_at<=? AND (w.retry_at IS NULL OR w.retry_at<=?)
            {'AND s.world_seed=?' if seed is not None else ''} ORDER BY w.id LIMIT 32''',
            (_stamp(now), _stamp(now), *args)).fetchall()
    notifications = []
    for work_id, world in rows:
        try:
            with db.transaction() as conn:
                row = conn.execute('''SELECT id,step,status,attempts,situation_id,due_at,retry_at FROM situation_work WHERE id=?''', (work_id,)).fetchone()
                if (row[2] != 'pending' or row[5] > _stamp(now)
                        or row[6] is not None and row[6] > _stamp(now)):
                    continue
                if conn.execute("SELECT 1 FROM situation_work WHERE situation_id=? AND step<? AND status='pending'", (row[4], row[1])).fetchone():
                    continue
                situation = _read(conn, world)
                notice = _land(conn, {'id': row[0], 'step': row[1]}, situation)
            notifications.append((world, notice))
        except Exception as exc:
            _log.exception('Situation work %s remains pending', work_id)
            try:
                with db.transaction() as conn:
                    conn.execute('''UPDATE situation_work SET attempts=attempts+1,last_error=?,retry_at=? WHERE id=? AND status='pending' ''',
                                 (str(exc)[:500], _stamp(now + timedelta(seconds=30)), work_id))
            except Exception:
                _log.exception('Situation retry diagnostic unavailable; original work retained')
    # Every notice follows commit. A transport failure cannot replay the work.
    from server.rooms import broadcast, get_room
    for world, notice in notifications:
        try:
            broadcast(get_room(world), notice)
        except Exception:
            _log.exception('Committed situation notification unavailable')
    return len(notifications)


def follow_up(seed, participant, request_id, *, actor_identity, player_name):
    def apply():
        with db._connection() as conn:
            situation = _read(conn, seed)
            if not situation or situation['phase'] != 'aftermath':
                raise ValueError('The lasting echo has not arrived yet.')
            old = conn.execute('SELECT event_id FROM situation_followups WHERE situation_id=? AND participant_id=?',
                               (situation['id'], participant)).fetchone()
            if old:
                return {'event_id': old[0], 'message': 'Your marker is already part of this aftermath.'}
            spec = situation['definition']
            known = {r[0] for r in conn.execute('SELECT node_name FROM situation_discoveries WHERE situation_id=? AND participant_id=?',
                                               (situation['id'], participant))}
            if not {spec['nodes']['fold'], spec['nodes']['chain']} <= known:
                raise ValueError('Read the Fold and chain before setting a reference marker.')
            # A new, bounded contribution by a late visitor; never a first-solver claim.
            db.record_substance_change(seed, spec['nodes']['chain'], 'SITUATION_FOLLOWUP', player_name,
                {'situation': situation['id'], 'source_event_id': situation['outcome_event_id'],
                 'flavor': 'A traveler sets a reference marker beside the echo, making its route easier to compare.'},
                {'echo_markers': _marker_count(conn, situation['id']) + 1}, actor_identity=actor_identity)
            event = db.latest_event_id()
            conn.execute('INSERT INTO situation_followups(situation_id,participant_id,event_id) VALUES (?,?,?)',
                         (situation['id'], participant, event))
            return {'event_id': event, 'message': 'Your reference marker joins the lasting echo. You can return to compare it.'}
    return intents.execute(participant, seed, 'situation-followup', request_id, {}, apply)[0]


def _marker_count(conn, instance):
    return conn.execute('SELECT COUNT(*) FROM situation_followups WHERE situation_id=?', (instance,)).fetchone()[0]


def keeper_history(seed, keeper, node):
    """Retrieve at most three actual public commitment facts, independent of chatter."""
    db.init_db()
    with db._connection() as conn:
        situation = _read(conn, seed)
        if not situation or keeper != situation['definition']['keeper'] or node not in situation['definition']['nodes'].values():
            return []
        ids = [situation[key] for key in ('opened_event_id', 'commitment_event_id', 'outcome_event_id') if situation[key]]
    return db.presented_mutations(seed, ids)
