"""Ordered creation, competing intentions, actual receivers and durable recovery."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from copy import deepcopy
from types import SimpleNamespace
import multiprocessing
import os
from pathlib import Path
import signal
from urllib.parse import quote

import pytest

import persistence as db
from persistence import participants, interventions as work
from multiverse import interventions as physics, store
from multiverse.senses import describe
from multiverse.situation import NODES
from tests.test_participant_contracts import accounts, http  # noqa: F401

START = datetime(2026, 9, 20, 12)
SCORE = [{'op': 'weave'}, {'op': 'charge', 'amount': 3}, {'op': 'release'}]


@pytest.fixture
def owner(accounts, monkeypatch):
    monkeypatch.setattr(work, '_now', lambda: START)
    return participants.identify(accounts[0])['id']


def accept(owner, name=NODES['instrument'], steps=SCORE, request='compose-001'):
    p = work.preview(382, name, steps)
    return work.accept(382, owner, name, request, p['steps'], p['expected'],
                       performer='Ada', actor_identity='participant:' + owner)


def events():
    return [r for r in db.get_mutations(382, 100) if r['type'].startswith('INTERVENTION')]


def test_order_creation_polarity_and_receiver_arrangements_have_distinct_effects():
    outward = physics.simulate({}, SCORE)
    inward = physics.simulate({}, [{'op': 'weave'}, {'op': 'charge', 'amount': 3}, {'op': 'invert'}, {'op': 'release'}])
    assert outward['state']['woven'] and outward['signal']['coherent']
    assert outward['signal']['strength'] == -inward['signal']['strength'] == 3
    inverted_after = physics.simulate({}, SCORE + [{'op': 'invert'}])
    assert inverted_after['signal']['strength'] == 3
    unbound, _ = physics.receive({'danger_level': 7}, outward['signal'], 1)
    bound, _ = physics.receive({'danger_level': 7, 'resonance': {'woven': True}}, outward['signal'], 1)
    quiet, _ = physics.receive({'danger_level': 7}, inward['signal'], 1)
    assert bound['resonance']['energy'] > unbound['resonance']['energy']
    assert bound['resonance']['echo'] < unbound['resonance']['echo']
    assert unbound['danger_level'] == 8 and quiet['danger_level'] == 6
    destroyed = physics.simulate({'resonance': outward['state']}, [{'op': 'unweave'}])
    assert not destroyed['state']['woven'] and destroyed['state']['scar'] == 1
    assert outward['state']['woven']  # pure, no input mutation


@pytest.mark.parametrize('bad', [[{'op':'delete_world'}], [{'op':'charge','amount':True}], [{'op':'release','amount':2}], [{'op':'weave','delta':{}}], [{'op':'invert'}]*5])
def test_invalid_scores_cannot_reach_world_writes(bad):
    with pytest.raises(ValueError):
        physics.simulate({}, bad)
    assert physics.parse_score('do not release') is None
    assert physics.parse_score('weave, charge 2, release')[-1]['op'] == 'release'


def test_stale_preview_retry_and_atomic_origin(owner, monkeypatch):
    p = work.preview(382, NODES['instrument'], SCORE)
    before = deepcopy(store.resolve_node_by_name(382, NODES['instrument']).properties)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: work.accept(382, owner, NODES['instrument'], 'same-request', p['steps'], p['expected'], performer='Ada', actor_identity=owner), range(2)))
    assert results[0] == results[1] and len(events()) == 1
    assert store.resolve_node_by_name(382, NODES['instrument']).properties == before
    with pytest.raises(ValueError, match='changed since'):
        work.accept(382, owner, NODES['instrument'], 'another-request', p['steps'], p['expected'], performer='Ada', actor_identity=owner)
    with db._connection() as conn:
        assert conn.execute('SELECT count(*) FROM intervention_work').fetchone()[0] == 3
    # A failure after the material write leaves neither the delta nor a receipt.
    real = db.record_substance_change
    def fail(*args, **kwargs):
        real(*args, **kwargs)
        raise RuntimeError('injected after write')
    monkeypatch.setattr(db, 'record_substance_change', fail)
    with pytest.raises(RuntimeError):
        accept(owner, NODES['chain'], request='failed-request')
    assert not db.load_node_property_override(382, NODES['chain'])
    assert len(events()) == 1


def test_arrivals_use_current_receivers_land_once_and_enter_recap(owner):
    result = accept(owner)
    gallery = work.lineage(382, NODES['instrument'])[1]
    # Construct a receiving resonator AFTER the source commits.
    accept(owner, gallery.name, [{'op':'weave'}], 'receiver-weave')
    with ThreadPoolExecutor(2) as pool:
        counts = list(pool.map(lambda _: work.advance(382, now=START+timedelta(seconds=90)), range(2)))
    assert sum(counts) == 3
    state = db.load_node_property_override(382, gallery.name)['resonance']
    assert state['woven'] and state['energy'] > 0 and state['memory']
    assert work.advance(382, now=START+timedelta(days=1)) == 0
    assert sum(r['type'] == 'INTERVENTION_ARRIVED' for r in events()) == 3
    assert any(r['node'] == gallery.name for r in participants.recap(owner, 382))
    receipt = next(r for r in work.recent(382, NODES['instrument'], owner) if r['id'] == result['id'])
    assert receipt['pending'] == 0 and len(receipt['arrivals']) == 3


def test_delivery_failure_rolls_back_and_unknown_versions_remain_pending(owner, monkeypatch):
    accept(owner)
    original = db.record_substance_change
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        if args[2] == 'INTERVENTION_ARRIVED':
            raise RuntimeError('after delivery write')
    monkeypatch.setattr(db, 'record_substance_change', fail)
    assert work.advance(382, now=START+timedelta(seconds=90)) == 0
    assert len(events()) == 1
    monkeypatch.setattr(db, 'record_substance_change', original)
    with db.transaction() as conn:
        conn.execute('UPDATE interventions SET version=99')
    assert work.advance(382, now=START+timedelta(seconds=150)) == 0
    with db._connection() as conn:
        assert conn.execute("SELECT count(*) FROM intervention_work WHERE status='pending'").fetchone()[0] == 3
    with db.transaction() as conn:
        conn.execute('UPDATE interventions SET version=1')
    assert work.advance(382, now=START+timedelta(seconds=220)) == 3


def test_http_actions_are_scale_native_and_never_delegate(http, accounts):
    name = NODES['instrument']
    assert http('/interventions?node='+quote(name), '')[0] == 403
    status, data, headers = http('/interventions?node='+quote(name))
    assert status == 200 and headers['Cache-Control'] == 'no-store'
    assert set(data['operators']) == {'mend', 'engrave', 'fracture', 'polish'}
    assert 'agents' not in data
    for field in ('delegate', 'performer', 'actor_identity'):
        assert http('/interventions/preview', body={'node':name, 'steps':[{'op':'engrave'}], field:'Tessera'})[0] == 409
    assert http('/interventions/preview', body={'node':name, 'steps':[{'op':'cleave'}]})[0] == 409
    assert http('/interventions/preview', body={'node':name, 'steps':SCORE})[0] == 409
    status, preview, _ = http('/interventions/preview', body={'node':name,'steps':[{'op':'engrave'}]})
    assert status == 200 and preview['changed'] == {'surface':'engraved'}
    payload={'node':name,'steps':preview['steps'],'expected':preview['expected'],'version':2,'request_id':'own-action-001'}
    assert http('/interventions/commit', body=payload)[0] == 409
    assert http('/position', body={'node':name,'seed':382,'depth':9})[0] == 200
    for field in ('delegate', 'performer', 'actor_identity'):
        assert http('/interventions/commit', body={**payload,field:'Tessera'})[0] == 409
    assert not events()
    status, result, _ = http('/interventions/commit', body=payload)
    assert status == 200 and result['accepted']
    assert http('/interventions/commit', body=payload)[1] == result
    assert events()[0]['player'] == participants.identify(accounts[0])['name']
    assert http('/node?node_name='+quote(name))[1]['node']['properties']['surface'] == 'engraved'
    assert http('/interventions/preview', body={'node':name,'intention':'do not engrave'})[0] == 409


def test_senses_follow_literal_properties_and_material_history(owner):
    node=store.resolve_node_by_name(382,NODES['instrument'])
    before=describe(node)
    assert before['plate'] == '/media/places/instrument-v1.png'
    assert before['texture'] == 'filament'
    original=deepcopy(node.properties)
    accept(owner)
    node.properties=work.live(382,node)
    after=describe(node)
    assert after['woven'] and after['memory'] and after['revision'] != before['revision']
    assert after['description'] != before['description']
    assert 'woven resonator' in after['description'] and 'harmonic memory' in after['description']
    assert node.properties['aspect'] == original['aspect']
    assert store.resolve_node_by_name(382, node.name).properties == original
    node.properties={**original,'aspect':'A changed aspect that the curated plate no longer represents.'}
    assert describe(node)['plate'] is None
    assert before['family'] == after['family']
    node.properties={**original,'condition':'pristine'}
    assert describe(node)['plate'] is None  # the visibly broken reference no longer fits


def test_model_can_only_propose_bounded_operations(monkeypatch):
    from consciousness import interventions as proposal
    def response(text):
        return SimpleNamespace(stop_reason='end_turn',content=[SimpleNamespace(type='text',text=text)])
    answers=iter([response('{"supported":true,"steps":[{"op":"engrave","amount":1}]}'),response('{"supported":true,"steps":[{"op":"invent_canon","amount":1}]}'),response('{"supported":false,"steps":[]}')])
    calls=[]
    def create(**kwargs):
        calls.append(kwargs)
        return next(answers)
    monkeypatch.setattr(proposal,'_get_client',lambda:SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(proposal,'_log_cache_usage',lambda *args:None)
    assert proposal.propose('cut a pattern',{'level':'Object'}) == [{'op':'engrave','amount':1}]
    with pytest.raises(ValueError):
        proposal.propose('invent a galaxy',{'level':'Object'})
    with pytest.raises(ValueError):
        proposal.propose('ambiguous',{'level':'Object'})
    assert calls[0]['output_config']['format']['type'] == 'json_schema'
    assert events() == []


def _die_during_arrival(path):
    db._DB_PATH = Path(path)
    original = db.record_substance_change
    def die(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[2] == 'INTERVENTION_ARRIVED':
            os.kill(os.getpid(), signal.SIGKILL)
        return result
    db.record_substance_change = die
    work.advance(382, now=START + timedelta(seconds=90))


def test_process_death_backup_restore_and_future_proposals_keep_v1_promises(owner, tmp_path, monkeypatch):
    accept(owner, NODES['chain'])
    process = multiprocessing.get_context('spawn').Process(target=_die_during_arrival, args=(str(db._DB_PATH),))
    process.start()
    process.join(15)
    assert not process.is_alive() and process.exitcode == -signal.SIGKILL
    assert len(events()) == 1
    backup = tmp_path / 'restored.db'
    db.backup_to(backup)
    monkeypatch.setattr(db, '_DB_PATH', backup)
    db._initialized.discard(backup)
    def future(*args):
        raise AssertionError('a current proposal interpreter must not redefine an accepted v1 signal')
    monkeypatch.setattr(physics, 'receive', future)
    assert work.advance(382, now=START + timedelta(seconds=90)) == 3
    assert work.advance(382, now=START + timedelta(seconds=120)) == 0
    assert {r['node'] for r in events()} == {NODES['chain'], NODES['instrument'], NODES['gallery'], NODES['region']}


def test_wayback_keeps_birth_and_present_senses_distinct_and_receipts_survive_movement(http, accounts):
    name = NODES['instrument']
    http('/position', body={'node':name,'seed':382,'depth':9})
    preview = http('/interventions/preview', body={'node':name,'steps':[{'op':'engrave'}]})[1]
    payload = {'node':name,'steps':preview['steps'],'expected':preview['expected'],'request_id':'historical-01','version':2}
    result = http('/interventions/commit', body=payload)[1]
    http('/position', body={'node':NODES['region'],'seed':382,'depth':9})
    assert http('/interventions/commit', body=payload)[1] == result
    before = events()
    present = http('/wayback?node_name='+quote(name))[1]['node']
    birth = http('/wayback?node_name='+quote(name)+'&at=0')[1]['node']
    assert present['properties']['surface'] == 'engraved'
    assert birth['properties']['surface'] != 'engraved'
    assert present['senses']['revision'] != birth['senses']['revision']
    assert 'surface is engraved' in present['senses']['description']
    assert 'surface is engraved' not in birth['senses']['description']
    assert present['properties']['aspect'] == birth['properties']['aspect']
    assert events() == before


def test_old_delegated_receipt_recovers_but_cannot_authorize_new_work(http, accounts):
    participant = participants.identify(accounts[0])['id']
    name = NODES['instrument']
    preview = work.preview(382, name, SCORE)
    result = work.accept(382, participant, name, 'legacy-entrusted', preview['steps'], preview['expected'],
                         performer='Tessera', actor_identity='Tessera', delegate='Tessera')
    payload = {'node': name, 'request_id':'legacy-entrusted', 'steps':preview['steps'],
               'expected':preview['expected'], 'delegate':'Tessera'}
    assert http('/interventions/commit', body=payload)[1] == result
    assert http('/interventions/commit', body={**payload,'request_id':'new-entrusted'})[0] == 409
    assert len(events()) == 1


def test_scale_spectra_change_materials_and_order_matters():
    from multiverse import interventions_v2 as native
    from multiverse.verbs import VERBS
    for level in VERBS:
        assert len(native.vocabulary(level)) == 4
    object_props = {'condition':'damaged','surface':'rough hewn'}
    engrave = native.simulate(object_props, [{'op':'engrave'}], 'Object')
    polish = native.simulate(object_props, [{'op':'engrave'},{'op':'polish'}], 'Object')
    assert engrave['changed']['surface'] == 'engraved'
    assert polish['changed']['surface'] == 'mirror smooth'
    assert object_props == {'condition':'damaged','surface':'rough hewn'}
    with pytest.raises(ValueError, match='does not belong'):
        native.simulate(object_props, [{'op':'seed'}], 'Object')
    with pytest.raises(ValueError):
        native.simulate(object_props, [{'op':'engrave','amount':2}], 'Object')
    assert native.parse_score('do not engrave', 'Object') is None
    assert native.parse_score('engrave, polish', 'Object') == [{'op':'engrave','amount':1},{'op':'polish','amount':1}]
    assert native.simulate({'resonance':'3:5','ecliptic_tilt_deg':10}, [{'op':'incline'}], 'Planetary System')['changed'] == {'ecliptic_tilt_deg':13}
    delta, _ = native.receive({'resonance':'3:5'}, {'strength':2,'coherent':True,'motif':'abc'}, 1)
    assert 'resonance' not in delta
    assert delta['acoustic_resonance']['memory'] == 'abc'
    assert native.read_state({'resonance':'3:5', **delta})['echo'] > 0


def test_v2_delayed_origin_and_receiving_work_settle_once(owner, monkeypatch):
    monkeypatch.setenv('NESTED_WORLDS_MATURATION_SCALE', '0.01')
    node = work.lineage(382, NODES['region'])[-1]  # Galaxy
    assert node.level == 'Galaxy'
    before = work.live(382,node)
    preview = work.preview(382, node.name, [{'op':'scatter'}], version=2)
    assert preview['matures_in'] == 3
    args=(382, owner, node.name, 'new-delayed', preview['steps'], preview['expected'])
    result = work.accept(*args, performer='Ada', actor_identity=owner, version=2)
    assert result['changed'] == {}
    assert work.live(382,node) == before
    assert work.advance(382, now=START+timedelta(seconds=2)) == 0
    assert work.advance(382, now=START+timedelta(seconds=100)) == 3
    assert work.live(382,node)['star_density'] < before['star_density']
    assert work.advance(382, now=START+timedelta(seconds=200)) == 0
    assert work.accept(*args, performer='Ada', actor_identity=owner, version=2) == result


def test_v2_changed_conditions_can_exhaust_delayed_action_without_false_waves(owner, monkeypatch):
    monkeypatch.setenv('NESTED_WORLDS_MATURATION_SCALE', '0.01')
    node = work.lineage(382, NODES['region'])[-1]
    db.record_substance_change(382,node.name,'TEST',None,{}, {'shape':'irregular'})
    preview=work.preview(382,node.name,[{'op':'spiral'}],version=2)
    work.accept(382,owner,node.name,'shape-later',preview['steps'],preview['expected'],performer='Ada',actor_identity=owner,version=2)
    db.record_substance_change(382,node.name,'TEST',None,{}, {'shape':'spiral'})
    assert work.advance(382,now=START+timedelta(seconds=100)) == 3
    arrivals = [r for r in events() if r['type']=='INTERVENTION_ARRIVED']
    assert len(arrivals)==3 and all(not r['data']['materialized'] for r in arrivals)
    assert work.advance(382,now=START+timedelta(seconds=200))==0
