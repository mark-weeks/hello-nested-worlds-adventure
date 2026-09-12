"""Identity survives rotation; private data and retry receipts have actual owners."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import threading
import urllib.error
import urllib.request
from urllib.parse import quote

import pytest

import persistence
from persistence import intents, participants
from multiverse import store
from puzzles.instances import get_puzzle
from server import _Handler, _ThreadedServer


@pytest.fixture
def accounts():
    persistence.mint_invite_key('nw_' + 'a' * 32, 'Ada')
    persistence.mint_invite_key('nw_' + 'b' * 32, 'Bea')
    return 'nw_' + 'a' * 32, 'nw_' + 'b' * 32


def test_concurrent_first_use_and_rotation_keep_one_person(accounts):
    a, b = accounts
    with ThreadPoolExecutor(4) as pool:
        people = list(pool.map(participants.identify, [a] * 4))
    owner = people[0]['id']
    assert {p['id'] for p in people} == {owner}
    assert participants.identify(b)['id'] != owner
    node = store.world_tree(382).name
    participants.save_note(owner, 382, node, 'Private question', 'note-0001')
    participants.save_profile(owner, {'bio': 'My public bio', 'published': True})
    before = persistence.get_mutations(382)
    replacement = 'nw_' + 'c' * 32
    participants.rotate(hashlib.sha256(a.encode()).hexdigest()[:12], replacement)
    assert participants.identify(replacement)['id'] == owner
    with pytest.raises(participants.Unauthorized):
        participants.identify(a)
    assert participants.notes(owner, 382)[0]['text'] == 'Private question'
    assert participants.profile(owner)['bio'] == 'My public bio'
    assert persistence.get_mutations(382) == before
    assert set(participants.actor_aliases(hashlib.sha256(replacement.encode()).hexdigest()[:16])) == {
        hashlib.sha256(a.encode()).hexdigest()[:16], hashlib.sha256(replacement.encode()).hexdigest()[:16]}


def test_rotation_keeps_conversation_without_rewriting_history(accounts):
    a, _ = accounts
    original = hashlib.sha256(a.encode()).hexdigest()[:16]
    persistence.record_mutation(382, 'Room-1', 'PLAYER_SPEAK', 'Ada',
        {'identity': original, 'message': 'Remember the signal?', 'reply': 'I remember.'}, actor_identity=original)
    before = persistence.get_mutations(382)
    replacement = 'nw_' + 'c' * 32
    participants.rotate(a, replacement)
    current = hashlib.sha256(replacement.encode()).hexdigest()[:16]
    assert persistence.get_player_exchanges(382, 'Room-1', current)[0]['user'] == 'Remember the signal?'
    assert persistence.get_mutations(382) == before


def test_private_notes_never_appear_in_profiles_and_cannot_be_taken(accounts):
    a, b = [participants.identify(k)['id'] for k in accounts]
    participants.save_note(a, 382, 'Room-1', 'Never public', 'note-0001')
    participants.save_profile(a, {'bio': 'Unpublished', 'goals': 'Secret goal'})
    assert participants.profile(a)['bio'] == ''
    assert participants.notes(b, 382) == []
    with pytest.raises(ValueError):
        participants.save_note(b, 382, 'Room-1', '', 'note-0001')
    participants.save_profile(a, {'bio': 'Public', 'published': True})
    assert 'Never public' not in json.dumps(participants.profile(a))
    assert 'home' not in participants.profile(a)


def test_receipt_and_effect_rollback_together_and_reject_changed_intent(accounts):
    owner = participants.identify(accounts[0])['id']
    def fail():
        persistence.record_mutation(382, 'Room-1', 'TEST', 'Ada', {})
        raise RuntimeError('injected failure')
    with pytest.raises(RuntimeError):
        intents.execute(owner, 382, 'test', 'request-1', {'value': 1}, fail)
    assert persistence.get_mutations(382) == []
    def apply():
        persistence.record_mutation(382, 'Room-1', 'TEST', 'Ada', {})
        return {'accepted': True}
    assert intents.execute(owner, 382, 'test', 'request-1', {'value': 1}, apply) == ({'accepted': True}, False)
    assert intents.execute(owner, 382, 'test', 'request-1', {'value': 1}, fail) == ({'accepted': True}, True)
    with pytest.raises(ValueError):
        intents.execute(owner, 382, 'test', 'request-1', {'value': 2}, apply)
    assert len(persistence.get_mutations(382)) == 1


def test_open_puzzle_keeps_definition_through_code_change_and_new_epoch(monkeypatch):
    from dataclasses import replace
    from puzzles import generators, instances
    root = store.world_tree(382)
    original = get_puzzle(382, root)
    real = generators.build_puzzle
    monkeypatch.setattr(generators, 'build_puzzle', lambda node, epoch=0: replace(real(node, epoch),
        prompt='A new question', answer='a new answer'))
    monkeypatch.setattr(instances, 'DEFINITION_VERSION', 2)
    assert get_puzzle(382, root).prompt == original.prompt
    assert get_puzzle(382, root).answer == original.answer
    monkeypatch.setattr(instances, 'DEFINITION_VERSION', 1)
    assert get_puzzle(382, root, 1).answer == 'a new answer'
    assert persistence.get_mutations(382) == []


@pytest.fixture
def http(accounts, monkeypatch):
    monkeypatch.setenv('NESTED_WORLDS_CANONICAL_SEED', '382')
    server = _ThreadedServer(('127.0.0.1', 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(path, key=accounts[0], body=None):
        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',
            data=json.dumps(body).encode() if body is not None else None,
            headers={'X-Beta-Key': key, 'Content-Type': 'application/json'})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            data = json.load(response) if response.headers.get_content_type() == 'application/json' else response.read().decode()
            return response.status, data, dict(response.headers)
    try:
        yield request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_http_private_access_rotation_and_retry(http, accounts):
    a, b = accounts
    root = store.world_tree(382)
    status, me, _ = http('/me')
    assert status == 200
    note = {'id': 'private-note-1', 'node': root.name, 'text': 'My private discovery'}
    assert http('/journal/note', body=note)[0] == 200
    status, data, headers = http('/journal/data', b)
    assert status == 200 and data['notes'] == []
    assert headers['Cache-Control'] == 'no-store'
    assert http('/journal/data', '')[0] == 403
    body = {'node_name': root.name, 'request_id': 'one-real-act'}
    first = http('/act', body=body)
    second = http('/act', body=body)
    assert first[0] == second[0] == 200
    assert first[1] == second[1]
    replacement = 'nw_' + 'c' * 32
    participants.rotate(a, replacement)
    assert http('/journal/data', a)[0] == 403
    assert http('/journal/data', replacement)[1]['notes'][0]['text'] == 'My private discovery'
    assert http('/act', replacement, body)[1] == first[1]
    assert http('/me', replacement)[1]['participant']['id'] == me['participant']['id']


def test_named_puzzle_rejects_a_renewed_question_without_consuming_attempt(http):
    root = store.world_tree(382)
    query = '/puzzle?node_name=' + quote(root.name)
    puzzle = http(query)[1]
    persistence.record_mutation(382, root.name, 'PUZZLE_REARM', None, {})
    before = persistence.get_mutations(382)
    response = http('/puzzle/attempt', body={'node_name': root.name, 'puzzle_name': puzzle['name'], 'answer': 'old guess'})
    assert response[0] == 409
    assert persistence.get_mutations(382) == before


def test_renewal_between_read_and_acceptance_cannot_solve_old_instance(monkeypatch):
    from server.rooms import get_room, puzzle_attempt, PuzzleRenewed
    root = store.world_tree(382)
    puzzle = get_puzzle(382, root)
    persistence.record_mutation(382, root.name, 'PUZZLE_REARM', None, {})
    with pytest.raises(PuzzleRenewed):
        with puzzle_attempt(get_room(382), root.name, puzzle.name, 'Ada', True, expected_epoch=0):
            pytest.fail('A stale question must not enter the effect scope.')


def test_question_evidence_preserves_original_conditions_and_escapes_html(http):
    root = store.world_tree(382)
    persistence.record_substance_change(382, root.name, 'TEST_CHANGE', None, {}, {'evidence_test': '<script>first()</script>'})
    http('/puzzle?node_name=' + quote(root.name))
    persistence.record_substance_change(382, root.name, 'TEST_CHANGE', None, {}, {'evidence_test': 'later conditions'})
    status, html, headers = http('/puzzle/evidence?node_name=' + quote(root.name) + '&epoch=0')
    assert status == 200 and 'later conditions' not in html
    assert '&lt;script&gt;first()&lt;/script&gt;' in html and '<script>' not in html
    assert 'Conditions when this question opened' in html
    assert headers['Cache-Control'] == 'no-store'
    assert http('/puzzle/evidence?node_name=' + quote(root.name) + '&epoch=100')[0] == 404


def test_new_routes_enforce_canonical_world_before_any_parallel_history(http):
    for path in ('/situation', '/me', '/profile', '/journal/data', '/puzzle/evidence'):
        assert http(path + '?seed=999')[0] in (400, 409)
    assert not persistence.world_is_born(999)
