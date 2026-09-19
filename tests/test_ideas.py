"""Ideas behavior through real HTTP, concurrent writers and restarted processes."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest

import persistence as db
from persistence import ideas, participants
from tests.test_participant_contracts import accounts, http  # noqa: F401


def submission(title='A clearer crossing', request='submission-0001', **kwargs):
    return dict(title=title, description='I could not tell where the passage led.', request_id=request, **kwargs)


def create(http, **kwargs):
    status, data, _ = http('/ideas/submit', body=submission(**kwargs))
    assert status == 200, data
    return data['id']


def test_submit_retry_concurrency_identity_and_private_reads(http, accounts):
    body = submission(member_id=participants.identify(accounts[1])['id'], name='Imposter')
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(lambda _: http('/ideas/submit', body=body), range(24)))
    assert {r[0] for r in results} == {200}
    assert len({r[1]['id'] for r in results}) == 1
    idea_id = results[0][1]['id']
    data = http('/ideas/detail?id=' + idea_id)[1]['idea']
    assert data['author'] == 'Ada' and data['own'] and data['votes'] == 0
    other = http('/ideas/detail?id=' + idea_id, accounts[1])[1]['idea']
    assert not other['own']
    assert not http('/ideas/list?sort=own', accounts[1])[1]['ideas']
    assert http('/ideas/submit', body={**body, 'description': 'Different'})[0] == 409
    assert http('/ideas/list')[2]['Cache-Control'] == 'no-store'
    search = http('/ideas/search', body={'q': 'passage', 'limit': 5})
    assert search[0] == 200 and search[2]['Cache-Control'] == 'no-store'
    assert len(search[1]['ideas']) == 1
    public = json.dumps(data)
    assert all(word not in public for word in ('member_id','request_id','request_hash','credential','actor_identity',accounts[0]))


def test_concurrent_votes_are_unique_undo_and_repeated_desired_state(http, accounts):
    idea_id = create(http)
    def vote(pair):
        key, supported = pair
        return http('/ideas/vote', key, {'id': idea_id, 'supported': supported})
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(vote, [(accounts[0], True)] * 20 + [(accounts[1], True)] * 20))
    assert {r[0] for r in results} == {200}
    assert http('/ideas/detail?id=' + idea_id)[1]['idea']['votes'] == 2
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(vote, [(accounts[0], False)] * 20))
    assert {r[0] for r in results} == {200}
    state = http('/ideas/detail?id=' + idea_id)[1]['idea']
    assert state['votes'] == 1 and not state['supported']
    assert http('/ideas/detail?id=' + idea_id, accounts[1])[1]['idea']['supported']
    with db._connection() as conn:
        assert conn.execute('SELECT count(*) FROM community_vote_events').fetchone()[0] == 3


def test_active_invite_required_even_with_open_game_and_header_only(http, accounts, monkeypatch):
    monkeypatch.setattr('server.guard.check_invite_key', lambda *args: True)
    idea_id = create(http)
    assert http('/ideas', '')[0] == 200
    for route, body in [('/ideas/list', None), ('/ideas/detail?id=' + idea_id, None),
                        ('/ideas/submit', submission()), ('/ideas/vote', {'id': idea_id, 'supported': True}),
                        ('/ideas/withdraw', {'id': idea_id})]:
        status, data, headers = http(route, '', body)
        assert status == 403 and headers['Cache-Control'] == 'no-store'
        assert 'description' not in data
    assert http('/ideas/list?key=' + accounts[0], '')[0] == 403
    assert http('/ideas/submit', '', {**submission(), 'key': accounts[0]})[0] == 403


def test_rotation_preserves_submissions_votes_and_quota_and_revokes_old(http, accounts):
    idea_id = create(http)
    http('/ideas/vote', body={'id': idea_id, 'supported': True})
    new = 'nw_' + 'c' * 32
    participants.rotate(accounts[0], new)
    assert http('/ideas/list', accounts[0])[0] == 403
    assert http('/ideas/submit', accounts[0], submission())[0] == 403
    assert http('/ideas/submit', new, submission())[1]['id'] == idea_id
    state = http('/ideas/detail?id=' + idea_id, new)[1]['idea']
    assert state['own'] and state['supported'] and state['votes'] == 1
    assert http('/ideas/vote', new, {'id': idea_id, 'supported': False})[1]['idea']['votes'] == 0
    db.revoke_invite_key(new)
    assert http('/ideas/list', new)[0] == 403


@pytest.mark.parametrize('operation', ['submit','vote'])
def test_revocation_between_http_auth_and_write_cannot_commit(http, accounts, monkeypatch, operation):
    idea_id = create(http)
    entered = threading.Event()
    original = ideas.charge_ip
    def entering(*args, **kwargs):
        entered.set()
        return original(*args, **kwargs)
    monkeypatch.setattr(ideas, 'charge_ip', entering)
    payload = submission(request='race-request') if operation == 'submit' else {'id': idea_id, 'supported': True}
    with ThreadPoolExecutor(1) as pool:
        with db.transaction() as conn:
            conn.execute("UPDATE invite_keys SET revoked_at=datetime('now') WHERE key=?", (db._credential_digest(accounts[0]),))
            future = pool.submit(http, '/ideas/' + operation, accounts[0], payload)
            # Both HTTP credential preflights saw the live committed credential.
            assert entered.wait(5)
            # Release only now: the operation must recheck under its write lock.
        assert future.result()[0] == 403
    with db._connection() as conn:
        assert conn.execute('SELECT count(*) FROM community_ideas').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM community_votes').fetchone()[0] == 0


def test_hidden_withdrawn_duplicate_decisions_and_content_redaction(http, accounts):
    first, survivor = create(http), create(http, title='A second passage', request='submission-0002')
    http('/ideas/vote', accounts[1], {'id': first, 'supported': True})
    ideas.moderate(first, operator='Maintainer', explanation='Consolidating this work.', status='duplicate', duplicate_id=survivor)
    data = http('/ideas/detail?id=' + first)[1]['idea']
    assert data['duplicate_id'] == survivor and data['votes'] == 1
    assert http('/ideas/detail?id=' + survivor)[1]['idea']['votes'] == 0
    with pytest.raises(ValueError):
        ideas.moderate(survivor, operator='Maintainer', explanation='Cycle', status='duplicate', duplicate_id=first)
    ideas.moderate(survivor, operator='Maintainer', explanation='Private operator decision', visibility='hidden')
    assert http('/ideas/detail?id=' + first)[1]['idea']['duplicate_id'] is None
    for key in accounts:
        assert http('/ideas/detail?id=' + survivor, key)[0] == 404
        assert http('/ideas/vote', key, {'id': survivor, 'supported': True})[0] == 404
    assert len(ideas.operator_list('hidden')) == 1
    assert 'Private operator decision' not in json.dumps(http('/ideas/list')[1])
    assert http('/ideas/withdraw', accounts[1], {'id': first})[0] == 404
    assert http('/ideas/withdraw', body={'id': first})[0] == 200
    assert http('/ideas/withdraw', body={'id': first})[0] == 200
    assert http('/ideas/detail?id=' + first)[0] == 404
    assert http('/ideas/submit', body=submission())[1] == {'id': first, 'submitted': True, 'visible': False}
    record = ideas.operator_detail(first)
    assert record['title'] == record['description'] == '' and record['visibility'] == 'withdrawn'
    with db._connection() as conn:
        assert conn.execute('SELECT count(*) FROM community_votes WHERE idea_id=?', (first,)).fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM community_vote_events WHERE idea_id=?', (first,)).fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM community_decisions WHERE idea_id=?', (first,)).fetchone()[0] == 2
    with pytest.raises(ideas.Conflict):
        ideas.moderate(first, operator='Maintainer', explanation='Restore', visibility='visible')


def test_status_progress_requires_separate_availability_evidence(http):
    idea_id = create(http)
    for status in ('planned','in_progress','implemented','merged'):
        ideas.moderate(idea_id, operator='Maintainer', explanation='Explicit decision: ' + status, status=status)
        data = http('/ideas/detail?id=' + idea_id)[1]['idea']
        assert data['status'] == status and data['status_label'] != 'Available to play'
    with pytest.raises(ValueError):
        ideas.moderate(idea_id, operator='Maintainer', explanation='Missing deployment', status='available')
    ideas.moderate(idea_id, operator='Maintainer', explanation='Verified in release QA', status='available', availability='Release QA.3, verified by operator on 2026-09-14')
    data = http('/ideas/detail?id=' + idea_id)[1]['idea']
    assert data['status_label'] == 'Available to play' and len(data['decisions']) == 5
    assert 'Maintainer' not in json.dumps(data['decisions'])


@pytest.mark.parametrize('change', [dict(title=''),dict(title=' '*4),dict(title='x'*121),dict(description='x'*2001),
    dict(title=[]),dict(description=None),dict(public_credit=1),dict(request_id='bad'),dict(request_id=[]),
    dict(description='nw_'+'z'*32),dict(title='hello\x00world')])
def test_submission_input_limits_are_clean_and_echo_no_private_input(http, change):
    status, data, _ = http('/ideas/submit', body={**submission(), **change})
    assert status == 400 and set(data) == {'error'}
    assert 'nw_' not in json.dumps(data)


@pytest.mark.parametrize('route,body', [('/ideas/vote', {'id': [], 'supported': True}),
    ('/ideas/vote', {'id': 'f'*32, 'supported': 1}),('/ideas/withdraw', {'id': '<script>'}),
    ('/ideas/submit', []),('/ideas/list?limit=51', None),('/ideas/list?limit=0', None),
    ('/ideas/list?limit=no', None),('/ideas/list?sort=bad', None),('/ideas/list?cursor=garbage', None)])
def test_invalid_api_input_never_becomes_server_error(http, route, body):
    assert http(route, body=body)[0] == 400


def test_body_limit_and_literal_html_no_paid_moderation(http, monkeypatch):
    monkeypatch.setattr('server.moderation.screen', lambda *a: pytest.fail('Ideas must not invoke paid screening'))
    title = '<img src=x onerror=alert(1)>'
    idea_id = create(http, title=title)
    assert http('/ideas/detail?id=' + idea_id)[1]['idea']['title'] == title
    assert http('/ideas/submit', body={**submission(), 'description':'secret'*2000})[0] == 413
    monkeypatch.setenv('NESTED_WORLDS_MODERATION_BLOCK_EXTRA', 'badcommunityword')
    assert http('/ideas/submit', body=submission(title='badcommunityword', request='blocked-0001'))[0] == 400


def test_member_and_ip_limits_persist_but_noops_do_not_charge_member(http, accounts, monkeypatch):
    first = create(http)
    for n in range(2,6):
        create(http, request=f'submission-000{n}')
    assert http('/ideas/submit', body=submission(request='over-limit'))[0] == 429
    assert http('/ideas/submit', body=submission())[0] == 200
    assert http('/ideas/withdraw', body={'id':first})[0] == 200
    assert http('/ideas/submit', body=submission(request='after-withdraw'))[0] == 429
    second = http('/ideas/list')[1]['ideas'][0]['id']
    for n in range(60):
        assert http('/ideas/vote', body={'id':second,'supported':n % 2 == 0})[0] == 200
    assert http('/ideas/vote', body={'id':second,'supported':False})[0] == 200
    assert http('/ideas/vote', body={'id':second,'supported':True})[0] == 429
    assert http('/ideas/vote', accounts[1], {'id':second,'supported':True})[0] == 200
    monkeypatch.setattr(ideas, 'IP_WRITES_PER_HOUR', 1)
    assert http('/ideas/vote', body={'id':second,'supported':False})[0] == 429
    db._initialized.discard(db._DB_PATH)
    assert http('/ideas/submit', body=submission(request='after-restart'))[0] == 429
    with db._connection() as conn:
        last_revision = conn.execute('SELECT max(id) FROM community_vote_events').fetchone()[0]
    monkeypatch.setattr(ideas, 'now', lambda: __import__('time').time_ns() // 1000 + ideas.DAY + 1)
    assert http('/ideas/submit', body=submission(request='after-a-day'))[0] == 200
    ideas.vote(accounts[0], second, True)
    with db._connection() as conn:
        assert conn.execute('SELECT id FROM community_vote_events').fetchall() == [(last_revision + 1,)]


@pytest.mark.parametrize('sort', ['recent','supported','own'])
def test_pagination_is_bounded_stable_under_insert_vote_hide_and_cannot_cross_viewers(http, accounts, monkeypatch, sort):
    monkeypatch.setattr(ideas, 'SUBMISSIONS_PER_DAY', 100)
    ids = [create(http, title=f'Passage {n}', request=f'page-idea-{n}') for n in range(55)]
    if sort == 'supported':
        for idea_id in ids[:5]:
            ideas.vote(accounts[0], idea_id, True)
    # Timestamp equality models a vote stamped before the first page but committed
    # after its read snapshot. Only commit-order revisions can freeze this ranking.
    frozen_time = ideas.now()
    monkeypatch.setattr(ideas, 'now', lambda: frozen_time)
    first = http('/ideas/list?sort=' + sort + '&limit=3')[1]
    initial = [r['id'] for r in first['ideas']]
    cursor = first['next_cursor']
    assert cursor and http('/ideas/list?sort=' + sort + '&cursor=' + cursor, accounts[1])[0] == 400
    assert http('/ideas/list?sort=' + sort + '&q=changed&cursor=' + cursor)[0] == 400
    new = create(http, request='new-between-pages')
    candidate = next(i for i in ids if i not in initial)
    ideas.vote(accounts[1], candidate, True)
    hidden = next(i for i in ids if i not in initial and i != candidate)
    ideas.moderate(hidden, operator='Operator', explanation='Hide during browsing', visibility='hidden')
    seen = initial[:]
    while cursor:
        page = http('/ideas/list?sort=' + sort + '&limit=50&cursor=' + cursor)[1]
        assert len(page['ideas']) <= 50
        seen.extend(r['id'] for r in page['ideas'])
        cursor = page['next_cursor']
    assert len(seen) == len(set(seen)) == 54
    assert new not in seen and hidden not in seen and candidate in seen
    search = http('/ideas/list?q=Passage%202')[1]['ideas']
    assert all('Passage 2' in i['title'] for i in search)
    monkeypatch.setattr(ideas, 'now', lambda: __import__('time').time_ns() // 1000 + ideas.PAGE_LIFETIME + 1)
    assert http('/ideas/list?sort=' + sort + '&cursor=' + first['next_cursor'])[0] == 400


def test_restart_and_world_tables_unchanged(http, accounts):
    from multiverse import store
    store.world_tree(382)
    tables = ('world_nodes','world_mutations','world_meta','agent_memory','puzzle_results')
    def snapshot():
        with db._connection() as conn:
            return {table: conn.execute('SELECT * FROM ' + table).fetchall() for table in tables}
    before = snapshot()
    idea_id = create(http)
    http('/ideas/vote', body={'id':idea_id,'supported':True})
    ideas.moderate(idea_id, operator='Maintainer', explanation='Worth considering', status='planned')
    code = '''import json,sys
from pathlib import Path
import persistence as db
from persistence import ideas
db._DB_PATH=Path(sys.argv[1])
print(json.dumps(ideas.detail(sys.argv[2],sys.argv[3])))
'''
    output = subprocess.check_output([sys.executable,'-c',code,str(db._DB_PATH),accounts[0],idea_id], cwd=Path(__file__).resolve().parents[1])
    data = json.loads(output)['idea']
    assert data['votes'] == 1 and data['supported'] and data['status'] == 'planned'
    assert http('/ideas/submit', body=submission())[1]['id'] == idea_id
    assert snapshot() == before


def test_operator_cli_records_decision_and_lists_private_content(http):
    from main import build_parser
    idea_id = create(http)
    args = build_parser().parse_args(['ideas','decide',idea_id,'--operator','Operator',
                                      '--explanation','Review required','--visibility','hidden'])
    args.func(args)
    assert ideas.operator_detail(idea_id)['visibility'] == 'hidden'
