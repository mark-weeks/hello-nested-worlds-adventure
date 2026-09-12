"""Both shared branches, disagreement, late entry and transactional recovery."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
import multiprocessing
import os
from pathlib import Path
import signal

import pytest

import persistence
from persistence import participants, situations
from multiverse.situation import NODES
from tests.test_participant_contracts import accounts, http  # noqa: F401

START = datetime(2026, 9, 12, 12)


@pytest.fixture
def experience(accounts, monkeypatch):
    monkeypatch.setattr(situations, '_now', lambda: START)
    situations.install(382)
    return [participants.identify(key)['id'] for key in accounts]


def investigate(owner):
    for name in ('instrument', 'regulator', 'fold', 'chain'):
        situations.discover(382, owner, NODES[name])


def history():
    return [r for r in persistence.get_mutations(382, 100) if r['type'].startswith('SITUATION')]


@pytest.mark.parametrize('branch,expected_danger', [('preserve', 6), ('release', 8)])
def test_both_branches_land_once_and_late_visitors_have_aftermath(experience, branch, expected_danger):
    owner, late = experience
    investigate(owner)
    situations.choose(382, owner, 'choice-request', branch)
    assert situations.view(382, owner)['phase'] == 'decision'
    assert situations.advance(382, now=START + timedelta(seconds=61)) == 1
    assert situations.view(382)['phase'] == 'pending'
    with ThreadPoolExecutor(2) as pool:
        counts = list(pool.map(lambda _: situations.advance(382, now=START + timedelta(seconds=200)), range(2)))
    assert sum(counts) == 2
    assert situations.view(382)['phase'] == 'aftermath'
    assert persistence.load_node_property_override(382, NODES['region'])['danger_level'] == expected_danger
    assert persistence.load_node_property_override(382, NODES['fold'])['signal_echo'] == branch
    before = history()
    assert situations.advance(382, now=START + timedelta(days=1)) == 0
    assert history() == before
    with pytest.raises(ValueError):
        situations.choose(382, late, 'late-choice', 'release')
    investigate(late)
    result = situations.follow_up(382, late, 'late-followup', actor_identity='late-identity', player_name='Late')
    repeated = situations.follow_up(382, late, 'another-followup', actor_identity='late-identity', player_name='Late')
    assert repeated['event_id'] == result['event_id']
    assert situations.view(382, late)['followed_up']
    assert len(history()) == len(before) + 1
    assert history()[0]['type'] == 'SITUATION_FOLLOWUP'
    assert persistence.load_node_property_override(382, NODES['chain'])['echo_markers'] == 1


def test_tie_keeps_window_open_one_choice_per_participant_and_version_is_pinned(experience, monkeypatch):
    a, b = experience
    for owner in (a, b):
        investigate(owner)
    situations.choose(382, a, 'a-choice-1', 'preserve')
    situations.choose(382, b, 'b-choice-1', 'release')
    assert situations.advance(382, now=START + timedelta(seconds=61)) == 0
    assert situations.view(382)['phase'] == 'decision'
    assert len(history()) == 1
    monkeypatch.setattr(situations, '_now', lambda: START + timedelta(seconds=70))
    situations.choose(382, a, 'a-choice-2', 'release')
    assert situations.view(382)['counts'] == {'release': 2}
    assert situations.advance(382, now=START + timedelta(seconds=122)) == 1
    assert situations.view(382)['branch'] == 'release'
    from multiverse import situation
    monkeypatch.setattr(situation, 'WINDOW_SECONDS', 1)
    original_id = situations.view(382)['id']
    assert situations.install(382) == original_id
    with persistence._connect() as conn:
        spec = json.loads(conn.execute('SELECT definition FROM situations').fetchone()[0])
    assert spec['window_seconds'] == 60


def test_application_failure_rolls_back_delta_and_retries_original_work(experience, monkeypatch):
    a, _ = experience
    investigate(a)
    situations.choose(382, a, 'a-choice-1', 'release')
    original = persistence.record_substance_change
    def fail_after_write(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[2] == 'SITUATION_CONSEQUENCE':
            raise RuntimeError('injected after delta')
        return result
    monkeypatch.setattr(persistence, 'record_substance_change', fail_after_write)
    assert situations.advance(382, now=START + timedelta(seconds=61)) == 0
    assert 'signal_route' not in persistence.load_node_property_override(382, NODES['gallery'])
    assert [r['type'] for r in history()] == ['SITUATION_COMMITTED', 'SITUATION_OPENED']
    monkeypatch.setattr(persistence, 'record_substance_change', original)
    assert situations.advance(382, now=START + timedelta(seconds=200)) == 3
    assert situations.view(382)['phase'] == 'aftermath'


def _kill_during_landing(path):
    import persistence
    from persistence import situations
    persistence._DB_PATH = Path(path)
    original = persistence.record_substance_change
    def kill(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[2] == 'SITUATION_CONSEQUENCE':
            os.kill(os.getpid(), signal.SIGKILL)
        return result
    persistence.record_substance_change = kill
    situations.advance(382, now=START + timedelta(seconds=61))


def test_process_death_and_backup_restore_preserve_pending_promise(experience, tmp_path):
    a, _ = experience
    investigate(a)
    situations.choose(382, a, 'a-choice-1', 'preserve')
    process = multiprocessing.get_context('spawn').Process(target=_kill_during_landing, args=(str(persistence._DB_PATH),))
    process.start()
    process.join(15)
    assert not process.is_alive()
    assert process.exitcode == -signal.SIGKILL
    assert situations.view(382)['phase'] == 'pending'
    assert 'signal_route' not in persistence.load_node_property_override(382, NODES['gallery'])
    backup = tmp_path / 'backup.db'
    persistence.backup_to(backup)
    assert situations.advance(382, now=START + timedelta(seconds=200)) == 3
    persistence.restore_from(backup)
    assert situations.view(382)['phase'] == 'pending'
    assert situations.advance(382, now=START + timedelta(seconds=200)) == 3
    assert len([r for r in history() if r['type'] == 'SITUATION_CONSEQUENCE']) == 3


def test_actual_http_requires_travel_and_preserves_choice_receipt(http, accounts, experience):
    key = accounts[0]
    result = http('/situation')[1]['situation']
    assert result['phase'] == 'investigate'
    assert http('/situation/discover', body={'node': NODES['instrument']})[0] == 409
    for role in ('instrument', 'regulator'):
        persistence.save_player_position(key, NODES[role], 382, 9, 2, 3)
        assert http('/situation/discover', body={'node': NODES[role]})[0] == 200
    body = {'request_id': 'http-choice', 'branch': 'release'}
    first = http('/situation/choose', body=body)
    second = http('/situation/choose', body=body)
    assert first[:2] == second[:2]
    assert first[0] == 200
    assert http('/situation/choose', body={**body, 'branch': 'preserve'})[0] == 409
    assert http('/situation/choose', '', body)[0] == 403


def test_return_recap_and_keeper_recall_survive_noise_without_private_notes(experience):
    a, b = experience
    investigate(a)
    participants.save_note(a, 382, NODES['instrument'], 'Secret private theory', 'secret-note')
    situations.choose(382, a, 'choice-recall', 'release')
    situations.advance(382, now=START + timedelta(seconds=61))
    situations.advance(382, now=START + timedelta(seconds=200))
    for _ in range(40):
        persistence.record_mutation(382, NODES['gallery'], 'AGENT_VISIT', None, {'agent': 'Walker'})
    recalled = situations.keeper_history(382, 'Tessera', NODES['gallery'])
    assert {row['type'] for row in recalled} == {'SITUATION_OPENED', 'SITUATION_COMMITTED', 'SITUATION_CONSEQUENCE'}
    assert 'Secret private theory' not in json.dumps(recalled)
    assert situations.keeper_history(382, 'Other', NODES['gallery']) == []
    assert participants.recap(b, 382) == []
    assert any('lasting' in row['text'] for row in participants.recap(a, 382))


def test_maturation_failure_cannot_starve_situation_pump(monkeypatch):
    from server import heartbeat
    from causality import staging
    calls = []
    monkeypatch.setenv('NESTED_WORLDS_CANONICAL_SEED', '382')
    monkeypatch.setattr(staging, 'drain_due_hops', lambda **kwargs: None)
    def failed(**kwargs):
        raise RuntimeError('isolated maturation failure')
    monkeypatch.setattr(heartbeat, 'drain_matured_verbs', failed)
    monkeypatch.setattr(situations, 'advance', lambda seed: calls.append(seed))
    class Stop:
        def __init__(self):
            self.ticks = 0
        def wait(self, _):
            self.ticks += 1
            return self.ticks > 1
    heartbeat.run_pump_loop(Stop())
    assert calls == [382]
