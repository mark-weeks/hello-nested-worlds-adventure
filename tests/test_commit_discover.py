"""Real HTTP acceptance, versioned delivery and deterministic model fixtures."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
import json

import pytest

import persistence as db
from persistence import interventions as work
from multiverse import interventions_v3 as physics, store
from multiverse.situation import NODES
from tests.test_expressive_interventions import START, events, owner  # noqa: F401
from tests.test_participant_contracts import accounts, http  # noqa: F401


def arrive(http, name, key=None):
    args = (key,) if key else ()
    assert http('/position', *args, body={'node':name,'seed':382,'depth':9})[0] == 200


def commit(http, name, steps, request, key=None):
    args = (key,) if key else ()
    status, result, _ = http('/interventions/commit', *args, body={
        'node':name,'steps':[{'op':s} for s in steps],'version':3,'request_id':request})
    assert status == 200, result
    return result


def model(monkeypatch, answers):
    """Fixture provider, through the actual schema parser and endpoint."""
    from consciousness import interventions as proposals
    from server import guard
    monkeypatch.delenv('NESTED_WORLDS_DISABLE_AI', raising=False)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fixture-only')
    monkeypatch.setattr(guard, 'consume_anthropic', lambda **kwargs: True)
    calls = []
    iterator = iter(answers)
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(stop_reason='end_turn', content=[SimpleNamespace(type='text',text=json.dumps(next(iterator)))])
    monkeypatch.setattr(proposals, '_get_client', lambda: SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(proposals, '_log_cache_usage', lambda *args: None)
    return calls


@pytest.mark.parametrize('ambiguity', ['action','target','scope','order'])
def test_material_ambiguity_clarifies_without_writes_and_revision_commits(http, monkeypatch, ambiguity):
    name = NODES['instrument']
    arrive(http, name)
    calls = model(monkeypatch, [
        {'status':'clarify','ambiguity':ambiguity,'steps':[]},
        {'status':'ready','ambiguity':'none','steps':[{'op':'engrave','amount':1}]},
    ])
    body = {'node':name,'intention':'change it','version':3,'request_id':'ambiguous-01'}
    status, reply, _ = http('/interventions/commit', body=body)
    assert status == 200 and reply['clarification'] and not reply['accepted']
    assert not events()
    assert http('/interventions/commit', body=body)[1] == reply and len(calls) == 1
    body.update(intention='cut a pattern in this surface',request_id='clear-revision')
    status, accepted, _ = http('/interventions/commit', body=body)
    assert status == 200 and accepted['accepted'] and accepted['changed'] == {'surface':'engraved'}
    # A lost ack/reload/retry after leaving bypasses both model and position.
    arrive(http, NODES['region'])
    assert http('/interventions/commit', body=body)[1] == accepted and len(calls) == 2
    assert len(events()) == 2
    assert http('/interventions/commit', body={**body,'intention':'fracture'})[0] == 409


def test_unsupported_constraints_delegation_and_invalid_model_output_never_become_actions(http, monkeypatch):
    name = NODES['instrument']
    arrive(http, name)
    calls = model(monkeypatch, [
        {'status':'unsupported','ambiguity':'none','steps':[]},
        {'status':'ready','ambiguity':'none','steps':[{'op':'cleave','amount':1}]},
        {'status':'ready','ambiguity':'none','steps':[{'op':'engrave','amount':1,'performer':'Bea'}]},
    ])
    for i, intention in enumerate(['open it without destroying its pattern','cleave a bond','have Bea engrave it']):
        status, reply, _ = http('/interventions/commit', body={
            'node':name,'intention':intention,'version':3,'request_id':f'unsupported-{i}'})
        assert status == 200 and not reply['accepted'] and reply['steps'] == []
        if i == 0:
            assert reply['declined']
    for field in ['delegate','performer','actor_identity']:
        assert http('/interventions/commit', body={'node':name,'intention':'engrave','version':3,
                    'request_id':'forced-performer',field:'Bea'})[0] == 409
    assert len(calls) == 3 and not events()


def test_direct_attempts_accept_current_state_and_noops_have_observed_history(http, accounts):
    name = NODES['instrument']
    arrive(http, name)
    arrive(http, name, accounts[1])
    # The menu is read before Bea's independent action; there is no stale forecast token.
    before = http('/interventions?node='+name.replace(' ', '%20'))[1]
    first = commit(http, name, ['engrave'], 'bea-engraves', accounts[1])
    second = commit(http, name, ['engrave'], 'ada-engraves')
    assert before['version'] == 3 and first['changed'] and second['accepted']
    assert f"Engrave: {physics._OBSERVED['engrave']['surface']}" in first['flavor'] and 'surface is' not in first['flavor']
    # An instant settlement that still queues outward hops reports the queue,
    # agreeing with what recent() says about the same attempt.
    assert first['phase'] == 'pending' and first['pending_steps'] == 1 and first['flavor'].endswith(' Consequences are pending.')
    assert second['phase'] == 'observed' and 'Consequences are pending' not in second['flavor']
    assert {r['id']: r['phase'] for r in work.recent(382, name)}[first['id']] == 'pending'
    assert second['changed'] == {} and second['pending_steps'] == 0
    assert 'No new material change' in second['flavor']
    records = [e for e in events() if e['data']['intervention'] == second['id']]
    assert {e['data']['phase'] for e in records} == {'accepted','observed'}
    assert not next(e for e in records if e['type']=='INTERVENTION_ARRIVED')['data']['materialized']


def test_intervening_player_changes_partial_settlement_and_actual_outward_signal(http, accounts, owner, monkeypatch):
    galaxy = store.world_tree(382).children[0].children[0]
    arrive(http, galaxy.name)
    arrive(http, galaxy.name, accounts[1])
    db.record_substance_change(382, galaxy.name, 'TEST', None, {}, {'shape':'elliptical','star_density':400})
    # Bea starts Spiral first. Ada's accepted Spiral + Scatter would have a
    # net impulse of -1 at acceptance; only Scatter remains possible at maturity.
    monkeypatch.setattr(work, '_now', lambda: START)
    bea = commit(http, galaxy.name, ['spiral'], 'bea-spirals', accounts[1])
    monkeypatch.setattr(work, '_now', lambda: START+timedelta(seconds=1))
    ada = commit(http, galaxy.name, ['spiral','scatter'], 'ada-combines')
    assert ada['phase'] == 'pending' and ada['observed'] is None and ada['changed'] == {}
    with db._connection() as conn:
        saved = conn.execute('SELECT plan,signal,route FROM interventions WHERE id=?',(ada['id'],)).fetchone()
        assert not {'changed','signal'} & set(json.loads(saved[0])) and saved[1:] == ('{}','[]')
        assert conn.execute('SELECT COUNT(*) FROM intervention_work WHERE intervention_id=?',(ada['id'],)).fetchone()[0] == 1
    due = START+timedelta(seconds=work.maturation_seconds(galaxy.level))
    assert work.advance(382, now=due) == 1
    assert work.live(382, galaxy)['shape'] == 'spiral'
    assert work.advance(382, now=due+timedelta(seconds=1)) == 1
    arrival = next(e for e in events() if e['type']=='INTERVENTION_ARRIVED' and e['data']['intervention']==ada['id'])
    assert arrival['data']['signal']['strength'] == -2
    assert [s['outcome'] for s in arrival['data']['outcomes']] == ['no_material_change','materialized']
    assert work.live(382, galaxy)['star_density'] == 360
    assert bea['id'] != ada['id']
    # A recap reveals observed locations only, never the queued next receiver.
    record = next(r for r in work.recent(382,galaxy.name) if r['id']==ada['id'])
    assert record['pending'] == 1 and [a['node'] for a in record['arrivals']] == [galaxy.name]
    # The participant recap draws the same line: a queued receiver with its own
    # material history is not a place Ada has seen until her consequence lands.
    from persistence import participants
    universe = galaxy.parent
    db.record_substance_change(382, universe.name, 'TEST', None, {}, {'dark_matter_ratio':0.3})
    assert universe.name not in {r['node'] for r in participants.recap(owner, 382)}
    assert work.advance(382,now=due+timedelta(seconds=20)) == 2
    assert universe.name in {r['node'] for r in participants.recap(owner, 382)}
    assert work.advance(382,now=due+timedelta(seconds=40)) == 2
    assert work.advance(382,now=due+timedelta(seconds=60)) == 0


def test_settlement_moot_after_independent_player_action_sends_no_false_wave(http, accounts, owner, monkeypatch):
    galaxy = store.world_tree(382).children[0].children[0]
    db.record_substance_change(382, galaxy.name, 'TEST', None, {}, {'shape':'elliptical'})
    arrive(http,galaxy.name)
    arrive(http,galaxy.name,accounts[1])
    commit(http,galaxy.name,['spiral'],'first-spiral',accounts[1])
    monkeypatch.setattr(work,'_now',lambda:START+timedelta(seconds=1))
    later = commit(http,galaxy.name,['spiral'],'later-spiral')
    due = START+timedelta(seconds=work.maturation_seconds(galaxy.level)+1)
    assert work.advance(382,now=due) == 2
    with db._connection() as conn:
        assert conn.execute('SELECT hop,status FROM intervention_work WHERE intervention_id=?',(later['id'],)).fetchall() == [(0,'completed')]
    record = next(r for r in work.recent(382,galaxy.name) if r['id']==later['id'])
    assert record['pending']==0 and record['arrivals'][0]['materialized'] is False


def test_v3_atomic_failure_and_concurrent_retry_retain_one_attempt(http, owner, monkeypatch):
    name = NODES['instrument']
    original = db.record_substance_change
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('after effect before completion')
    monkeypatch.setattr(db,'record_substance_change',fail)
    payload = {'node':name,'version':3,'steps':[{'op':'engrave','amount':1}]}
    def accept():
        return work.accept_attempt(382,owner,name,'atomic-attempt',payload,payload['steps'],
                                   performer='Ada',actor_identity=owner,authorize=lambda:None)
    with pytest.raises(RuntimeError):
        accept()
    assert not events() and not db.load_node_property_override(382,name)
    monkeypatch.setattr(db,'record_substance_change',original)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _:accept(),range(2)))
    assert results[0] == results[1] and len(events()) == 2
    with db._connection() as conn:
        assert conn.execute('SELECT hop,status FROM intervention_work ORDER BY hop').fetchall() == [(0,'completed'),(1,'pending')]


def test_v2_receipt_and_pending_work_keep_their_meaning(http, accounts, owner, monkeypatch):
    galaxy = store.world_tree(382).children[0].children[0]
    preview = work.preview(382,galaxy.name,[{'op':'scatter'}],version=2)
    old = work.accept(382,owner,galaxy.name,'old-version-two',preview['steps'],preview['expected'],performer='Ada',actor_identity=owner,version=2)
    body = {'node':galaxy.name,'request_id':'old-version-two','steps':preview['steps'],'expected':preview['expected'],'version':2}
    assert http('/interventions/commit',body=body)[1] == old
    assert http('/interventions/commit',body={**body,'request_id':'new-version-two'})[0] == 409
    monkeypatch.setattr(physics,'settle',lambda *args:pytest.fail('v2 must not run under v3'))
    assert work.advance(382,now=START+timedelta(days=1)) == 3


def test_v3_pending_delivery_survives_process_death_and_backup_restore(owner, tmp_path, monkeypatch):
    import multiprocessing
    from pathlib import Path
    from tests.test_expressive_interventions import _die_during_arrival
    monkeypatch.setenv('NESTED_WORLDS_MATURATION_SCALE', '0.01')
    galaxy = store.world_tree(382).children[0].children[0]
    payload = {'node':galaxy.name,'version':3,'steps':[{'op':'scatter','amount':1}]}
    work.accept_attempt(382,owner,galaxy.name,'v3-process-death',payload,payload['steps'],
                        performer='Ada',actor_identity=owner,authorize=lambda:None)
    before = events()
    child = multiprocessing.get_context('spawn').Process(target=_die_during_arrival,args=(str(db._DB_PATH),))
    child.start()
    child.join(10)
    assert child.exitcode == -9
    assert events() == before
    with db._connection() as conn:
        assert conn.execute('SELECT hop,status FROM intervention_work').fetchall() == [(0,'pending')]
    backup = tmp_path/'v3-backup.db'
    db.backup_to(backup)
    monkeypatch.setattr(db,'_DB_PATH',Path(backup))
    # The durable attempt, not a simulated patch, resumes on restored state.
    assert work.advance(382,now=START+timedelta(days=2)) == 1
    assert len(events()) == 2
    assert work.advance(382,now=START+timedelta(days=2,seconds=20)) == 1
    assert work.advance(382,now=START+timedelta(days=2,seconds=40)) == 1
    assert work.advance(382,now=START+timedelta(days=3)) == 0


def test_concurrent_quiet_reply_cannot_race_a_later_model_acceptance(http, monkeypatch):
    import threading
    from server import intervention_api
    name = NODES['instrument']
    arrive(http,name)
    waiting, release = threading.Event(), threading.Event()
    calls = []
    def resolve(*args):
        calls.append(1)
        if len(calls) == 1:
            waiting.set()
            assert release.wait(5)
            return [{'op':'engrave','amount':1}], None
        return None, intervention_api._quiet(intervention_api._UNSETTLED)
    monkeypatch.setattr(intervention_api,'_propose',resolve)
    body={'node':name,'version':3,'intention':'cut a pattern','request_id':'race-a-model'}
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(http,'/interventions/commit',body=body)
        assert waiting.wait(5)
        second=http('/interventions/commit',body=body)
        release.set()
        assert first.result()[:2] == second[:2]
    assert second[1]['accepted'] is False and not events()
    assert http('/interventions/commit',body=body)[:2] == second[:2]
    assert len(calls) == 2
    # The quiet reply is that request's committed receipt (ADR-028): a same-ID
    # retry returns it without another model call; a new ID is a new attempt.
    calls.clear()
    def ready(*args):
        calls.append(1)
        return [{'op':'engrave','amount':1}], None
    monkeypatch.setattr(intervention_api,'_propose',ready)
    assert http('/interventions/commit',body=body)[:2] == second[:2] and not calls
    status, accepted, _ = http('/interventions/commit',body={**body,'request_id':'race-a-model-2'})
    assert status == 200 and accepted['accepted'] and len(calls) == 1 and len(events()) == 2


def test_receiver_with_saturated_echo_passes_observed_remainder_after_other_changes():
    signal = {'strength':1,'coherent':True,'motif':'heard-before'}
    props = {'danger_level':5,'resonance':{
        **physics.read_state({}), 'echo':12, 'last_wave':0.65, 'memory':'heard-before'}}
    changed, outgoing, _ = physics.receive(props,signal)
    assert changed == {'danger_level':6}
    assert outgoing['strength'] == 0.65
    # Current resonator state still governs the remainder, even after acceptance.
    bound = {**props,'resonance':{**props['resonance'],'woven':True}}
    _, caught, _ = physics.receive(bound,signal)
    assert 0 < caught['strength'] < outgoing['strength']
    # With nothing else to move, the receiver records no change and still
    # passes the same remainder on (ADR-028: the remainder feeds the next hop).
    saturated = {'resonance':props['resonance']}
    changed, onward, flavor = physics.receive(saturated,signal)
    assert changed == {} and onward['strength'] == 0.65 and 'travels on' in flavor


def test_saturated_receiver_records_no_change_and_still_passes_the_remainder_onward(http, owner, monkeypatch):
    universe = store.world_tree(382).children[0]
    galaxy = universe.children[0]
    db.record_substance_change(382, galaxy.name, 'TEST', None, {}, {'star_density':400})
    arrive(http, galaxy.name)
    monkeypatch.setattr(work,'_now',lambda:START)
    ada = commit(http, galaxy.name, ['scatter'], 'scatter-through-saturation')
    due = START+timedelta(seconds=work.maturation_seconds(galaxy.level))
    assert work.advance(382, now=due) == 1
    origin = next(e for e in events() if e['type']=='INTERVENTION_ARRIVED' and e['data']['intervention']==ada['id'])
    signal = origin['data']['signal']
    assert signal['strength'] == -2 and 'danger_level' not in work.live(382, universe)
    # The enclosing Universe already holds exactly the state this wave would
    # leave: a saturated echo, the same remainder and the same motif memory.
    remainder = round(signal['strength'] * .65, 3)
    db.record_substance_change(382, universe.name, 'TEST', None, {}, {'resonance':{
        **physics.read_state({}), 'echo':-12, 'last_wave':remainder, 'memory':signal['motif']}})
    assert work.advance(382, now=due+timedelta(seconds=20)) == 1
    arrival = next(e for e in events() if e['type']=='INTERVENTION_ARRIVED' and e['data']['hop']==1)
    assert arrival['node'] == universe.name and arrival['data']['materialized'] is False
    assert arrival['data']['signal']['strength'] == remainder and 'travels on' in arrival['data']['flavor']
    with db._connection() as conn:
        rows = conn.execute('SELECT hop,node_name,status FROM intervention_work WHERE intervention_id=? ORDER BY hop',(ada['id'],)).fetchall()
    assert rows == [(0,galaxy.name,'completed'),(1,universe.name,'completed'),(2,store.world_tree(382).name,'pending')]
    assert work.advance(382, now=due+timedelta(seconds=40)) == 1
    assert work.advance(382, now=due+timedelta(seconds=60)) == 0


def test_explicit_null_authority_fields_recover_the_same_receipt(http):
    name = NODES['instrument']
    arrive(http, name)
    body = {'node':name,'steps':[{'op':'engrave'}],'version':3,'request_id':'null-authority-01',
            'delegate':None,'performer':None,'actor_identity':None}
    status, accepted, _ = http('/interventions/commit', body=body)
    assert status == 200 and accepted['accepted']
    # A lost-ack retry that omits the null keys recovers the same receipt...
    retry = {k:v for k,v in body.items() if v is not None}
    assert http('/interventions/commit', body=retry)[1] == accepted
    # ...while a retry that names another performer is still a different action.
    assert http('/interventions/commit', body={**retry,'delegate':'Bea'})[0] == 409
    assert len([e for e in events() if e['type']=='INTERVENTION_COMMITTED']) == 1


def test_attempt_and_observation_banks_cover_every_operator():
    from multiverse import interventions_v2
    assert set(physics._ATTEMPTS) == set(interventions_v2.OPERATORS)
    assert set(physics._OBSERVED) == set(interventions_v2._RULES)
    for op, rule in interventions_v2._RULES.items():
        assert set(physics._OBSERVED[op]) == set(rule[3])
    for level in {info['level'] for info in interventions_v2.OPERATORS.values()}:
        assert all(v['description'].startswith('Attempt to ') for v in physics.vocabulary(level).values())


def test_settled_steps_speak_in_the_worlds_voice_never_property_literals():
    plan = {'steps':[{'op':'gather'},{'op':'gather'}],'level':'Planetary System','token':'t'}
    changed, signal, outcomes = physics.settle({'asteroid_belt':False}, plan)
    assert changed == {'asteroid_belt':True} and signal['strength'] == 1
    assert [physics.describe(o) for o in outcomes] == [physics._OBSERVED['gather']['asteroid_belt'], 'No new material change remains.']
    # Verb operators keep their authored line and the node's own aspect clause.
    plan = {'steps':[{'op':'mend'}],'level':'Object','token':'t'}
    _, _, outcomes = physics.settle({'condition':'damaged','aspect':'a brass astrolabe; it hums'}, plan)
    assert outcomes[0]['changed'] == {'condition':'worn'}
    assert physics.describe(outcomes[0]).endswith('A brass astrolabe.') and 'condition is' not in physics.describe(outcomes[0])
    for text in [physics.describe(o) for o in outcomes] + [line for clauses in physics._OBSERVED.values() for line in clauses.values()]:
        assert ' is True' not in text and ' is False' not in text and '_' not in text


@pytest.mark.parametrize('op,level,props,expected,present,absent', [
    ('cultivate','Region',{'terrain':'plain','danger_level':1}, {'terrain':'terraced'}, 'terraces', 'danger'),
    ('cultivate','Region',{'terrain':'terraced','danger_level':3}, {'danger_level':2}, 'danger', 'terraces'),
    ('overgrow','Region',{'terrain':'plain','danger_level':10}, {'terrain':'overgrown'}, 'Growth', 'danger'),
    ('channel','Region',{'terrain':'plain','weather':'ground fog'}, {'terrain':'waterways'}, 'Channels', 'fog'),
    ('fracture','Object',{'condition':'corrupted','fractured':False}, {'fractured':True}, 'breaks open', 'deteriorates'),
    ('fracture','Object',{'condition':'pristine','fractured':True}, {'condition':'worn'}, 'deteriorates', 'breaks open'),
    ('cleave','Molecule',{'bond_count':1,'reactive':False}, {'reactive':True}, 'reactive', 'bond'),
    ('branch','Molecule',{'geometry':'branched chain','reactive':False}, {'reactive':True}, 'reactive', 'reshapes'),
    ('relax','Atom',{'ionized':True,'resonance_nm':780}, {'ionized':False}, 'neutral', 'redward'),
    ('relax','Atom',{'ionized':False,'resonance_nm':600}, {'resonance_nm':630}, 'redward', 'electron'),
    ('superpose','SubatomicParticle',{'spin':'superposed','coherence':.5}, {'coherence':.35}, 'Coherence', 'reopen'),
    ('kindle','Galaxy',{'star_density':999}, {'kindled':True}, 'Kindling', 'New stars'),
    ('align','Planetary System',{'ecliptic_tilt_deg':0}, {'aligned':True}, 'alignment', 'flattens'),
    ('ward','Region',{'danger_level':1}, {'warded':True}, 'Ward lines', 'danger'),
    ('catalyze','Molecule',{'bond_count':12}, {'catalyzed':True}, 'reaction', 'new bond'),
    ('excite','Atom',{'resonance_nm':180,'ionized':False}, {'ionized':True}, 'electron', 'blueward'),
])
def test_partial_outcome_narration_only_claims_materialized_changes(op, level, props, expected, present, absent):
    changed, _, outcomes = physics.settle({**props,'aspect':'a brass astrolabe; it hums'}, physics.attempt([{'op':op}], level, 't'))
    note = physics.describe(outcomes[0])
    assert changed == expected and outcomes[0]['changed'] == expected
    assert present in note and absent not in note
    if op in physics._VERB_OBSERVED:
        assert note.endswith('A brass astrolabe.')


def test_partial_narration_reaches_receipt_history_and_recovery(http):
    name = NODES['region']
    db.record_substance_change(382, name, 'TEST', None, {}, {'danger_level':1,'terrain':'plain'})
    arrive(http, name)
    result = commit(http, name, ['cultivate'], 'cultivate-at-floor')
    assert result['changed'] == {'terrain':'terraced'}
    assert 'terraces' in result['flavor'] and 'danger' not in result['flavor']
    observed = next(e for e in events() if e['type']=='INTERVENTION_ARRIVED')
    assert 'terraces' in observed['data']['flavor'] and 'danger' not in observed['data']['flavor']
    assert work.recent(382, name)[0]['arrivals'][0]['flavor'] == observed['data']['flavor']
    db.record_substance_change(382, name, 'TEST', None, {}, {'danger_level':8})
    assert commit(http, name, ['cultivate'], 'cultivate-at-floor') == result


def test_legacy_accept_rejects_attempt_version_before_writes(owner):
    with pytest.raises(ValueError, match='without a forecast'):
        work.accept(382, owner, NODES['instrument'], 'wrong-entry-point', [{'op':'engrave'}], 'x'*24,
                    performer='Ada', actor_identity='participant:'+owner, version=3)
    assert not events()


@pytest.mark.parametrize('legacy_signal', [False, True])
def test_observed_signal_survives_restart_without_ledger_dependency(http, owner, legacy_signal):
    name = NODES['instrument']
    arrive(http, name)
    result = commit(http, name, ['engrave'], 'signal-recovery')
    with db._connection() as conn:
        signal = json.loads(conn.execute('SELECT signal FROM interventions WHERE id=?',(result['id'],)).fetchone()[0])
        assert signal['strength'] == 1
        if legacy_signal:
            # Simulate a pre-upgrade v3 row. Its first continuation can recover
            # the retained observation, then becomes independent of history.
            conn.execute("UPDATE interventions SET signal='{}' WHERE id=?", (result['id'],))
        else:
            # Fault injection on this disposable fixture only: observation data
            # is unavailable after retention/recovery. Delivery must not read it.
            conn.execute("UPDATE world_mutations SET data='{}' WHERE id=?", (result['observed']['event_id'],))
    db._initialized.discard(db._DB_PATH)
    assert work.advance(382, now=START+timedelta(seconds=20)) == 1
    with db._connection() as conn:
        signal = json.loads(conn.execute('SELECT signal FROM interventions WHERE id=?',(result['id'],)).fetchone()[0])
        assert signal['strength'] == .65
        previous = conn.execute('SELECT event_id FROM intervention_work WHERE intervention_id=? AND hop=1',(result['id'],)).fetchone()[0]
        conn.execute("UPDATE world_mutations SET data='{}' WHERE id=?", (previous,))
    assert work.advance(382, now=START+timedelta(seconds=40)) == 1
    assert work.advance(382, now=START+timedelta(seconds=60)) == 1
    assert work.advance(382, now=START+timedelta(seconds=80)) == 0
    assert commit(http, name, ['engrave'], 'signal-recovery') == result


def test_shared_receipt_lookup_preserves_a_stored_null_response(owner):
    from persistence import intents
    calls = []
    def apply():
        calls.append(1)
        return None
    args = (owner, 382, 'nullable-receipt', 'nullable-001', {'value':1})
    assert intents.execute(*args, apply) == (None, False)
    assert intents.execute(*args, apply) == (None, True)
    assert calls == [1]
    with pytest.raises(ValueError, match='different action'):
        intents.lookup(owner, 382, 'nullable-receipt', 'nullable-001', {'value':2})
