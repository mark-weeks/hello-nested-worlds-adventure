"""PR #102 regressions: bounded reads, private diagnostics and recoverable moderation."""
from contextlib import contextmanager
from http.client import HTTPConnection, HTTPResponse
import json
import subprocess
import sys
import threading

import pytest

import persistence as db
from persistence import ideas, participants
from server import _Handler, _ThreadedServer, guard, observability
from tests.test_ideas import create, submission
from tests.test_participant_contracts import accounts, http  # noqa: F401


@pytest.mark.parametrize('route', ['/ideas/list', '/ideas/search', '/ideas/detail'])
def test_read_paths_are_throttled_without_spending_write_quota(http, monkeypatch, route):
    idea_id = create(http)
    monkeypatch.setenv(guard.READ_RATE_LIMIT_ENV, '2')
    path = route + ('?id=' + idea_id if route.endswith('detail') else '')
    body = {} if route.endswith('search') else None
    assert [http(path, body=body)[0] for _ in range(3)] == [200, 200, 429]
    assert http('/ideas/vote', body={'id': idea_id, 'supported': True})[0] == 200
    with db._connection() as conn:
        assert conn.execute('SELECT count(*) FROM community_ip_writes').fetchone()[0] == 2


def test_read_budget_is_shared_across_get_and_post(http, monkeypatch):
    monkeypatch.setenv(guard.READ_RATE_LIMIT_ENV, '2')
    assert http('/ideas/list')[0] == 200
    assert http('/ideas/search', body={})[0] == 200
    assert http('/ideas/list')[0] == 429
    with db._connection() as conn:
        assert conn.execute('SELECT count(*) FROM community_ip_writes').fetchone()[0] == 0


@pytest.mark.parametrize('route', ['/ideas', '/ideas/', '/ideas///'])
def test_normalized_shell_is_public_but_api_stays_private(http, monkeypatch, route):
    monkeypatch.setattr(guard, 'check_invite_key', lambda *_: False)
    assert http(route, '')[0] == 200
    assert http('/ideas/list/', '')[0] == 403
    assert http('/ideas/search/', '', {})[0] == 403


@pytest.mark.parametrize('field', ['title', 'description', 'q'])
@pytest.mark.parametrize('character', ['\ud800', '\udfff'])
def test_surrogates_are_clean_client_errors(http, field, character):
    route = '/ideas/search' if field == 'q' else '/ideas/submit'
    body = {field: character} if field == 'q' else {**submission(), field: character}
    status, error, headers = http(route, body=body)
    assert status == 400 and headers['Cache-Control'] == 'no-store'
    assert 'invalid characters' in error['error']


@contextmanager
def raw_client():
    server = _ThreadedServer(('127.0.0.1', 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = HTTPConnection('127.0.0.1', server.server_port)
    try:
        yield client
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_nested_json_stays_a_400_without_exception_capture(accounts, monkeypatch):
    captures = []
    monkeypatch.setattr(observability, 'capture_exception', captures.append)
    with raw_client() as client:
        body = '[' * 1100 + '0' + ']' * 1100
        client.request('POST', '/ideas/submit/', body, {'X-Beta-Key': accounts[0]})
        response = client.getresponse()
        assert response.status == 400
        assert response.getheader('Cache-Control') == 'no-store'
        assert json.loads(response.read()) == {'error': 'invalid JSON'}
    assert not captures


@pytest.mark.parametrize('method', ['GET', 'POST'])
@pytest.mark.parametrize('target', ['http://[::1/ideas/list', 'http://[bad]/ideas/search'])
def test_malformed_request_targets_return_private_json_and_safe_access_logs(
        monkeypatch, caplog, capsys, method, target):
    captures = []
    monkeypatch.setattr(observability, 'capture_exception', captures.append)
    caplog.set_level('INFO', logger='nested_worlds.access')
    sentinel = 'private-credential-and-draft'
    with raw_client() as client:
        client.connect()
        client.sock.sendall((f'{method} {target}?key={sentinel} HTTP/1.1\r\n'
                             'Host: localhost\r\nConnection: close\r\nContent-Length: 0\r\n\r\n').encode())
        response = HTTPResponse(client.sock)
        response.begin()
        assert response.status == 400
        assert response.getheader('Cache-Control') == 'no-store'
        assert json.loads(response.read()) == {'error': 'invalid request target'}
    assert not captures
    assert sentinel not in caplog.text + capsys.readouterr().err
    logs = [json.loads(r.getMessage()) for r in caplog.records if r.name == 'nested_worlds.access']
    assert len(logs) == 1
    assert logs[0]['path'] == '/[invalid-target]' and logs[0]['status'] == 400
    assert not any(r.exc_info for r in caplog.records)


@pytest.mark.parametrize('method', ['GET', 'POST'])
@pytest.mark.parametrize('point', ['auth', 'query', 'dispatch'])
def test_failures_emit_only_local_safe_diagnostics(http, accounts, caplog, monkeypatch, point, method):
    sentinel = accounts[0] + ' private-submission-detail'
    def broken(*args, **kwargs):
        raise RuntimeError(sentinel)
    captures = []
    monkeypatch.setattr(observability, 'capture_exception', captures.append)
    if point == 'auth':
        monkeypatch.setattr(participants, 'identify', broken)
    elif point == 'query':
        monkeypatch.setattr(ideas, 'listing', broken)
    else:
        # Failure outside the adapter must have the same privacy boundary.
        monkeypatch.setattr(_Handler, '_dispatch_' + method.lower(), broken)
    route = '/ideas/list' if method == 'GET' else '/ideas/search'
    status, data, headers = http(route, body=None if method == 'GET' else {})
    assert status == 503 and headers['Cache-Control'] == 'no-store'
    assert not captures and sentinel not in json.dumps(data) + caplog.text
    records = [r for r in caplog.records if r.name == 'nested_worlds.community']
    assert len(records) == 1
    assert records[0].getMessage() == f'ideas_request_failed route={route} exception=RuntimeError'
    assert records[0].exc_info is False or records[0].exc_info is None


def test_unrecognized_diagnostic_route_cannot_export_user_text(caplog):
    observability.community_failure('/ideas/nw_private?text=private-note', RuntimeError('private-note'))
    assert 'route=/ideas/*' in caplog.text
    assert 'nw_private' not in caplog.text and 'private-note' not in caplog.text


def test_header_whitespace_and_authentication_counts(http, accounts, monkeypatch):
    identify = participants.identify
    calls = []
    def counted(key):
        calls.append(key)
        return identify(key)
    monkeypatch.setattr(participants, 'identify', counted)
    key = '  ' + accounts[0] + '  '
    assert http('/ideas/search', key, {})[0] == 200
    assert calls == [accounts[0]]
    calls.clear()
    result = http('/ideas/submit', key, submission())
    assert result[0] == 200
    assert calls == [accounts[0], accounts[0]]
    calls.clear()
    assert http('/ideas/detail?id=' + result[1]['id'], key)[0] == 200
    assert calls == [accounts[0]]


def test_duplicate_can_be_moderated_after_survivor_is_hidden_or_withdrawn(http):
    duplicate = create(http, request='duplicate-0001')
    survivor = create(http, request='survivor-00001')
    decision = {'operator': 'Maintainer', 'explanation': 'Reviewed decision'}
    ideas.moderate(duplicate, status='duplicate', duplicate_id=survivor, **decision)
    ideas.moderate(survivor, visibility='hidden', **decision)
    ideas.moderate(duplicate, visibility='hidden', **decision)
    assert ideas.operator_detail(duplicate)['visibility'] == 'hidden'
    ideas.moderate(survivor, visibility='withdrawn', **decision)
    ideas.moderate(duplicate, visibility='visible', **decision)
    assert http('/ideas/detail?id=' + duplicate)[1]['idea']['duplicate_id'] is None
    # A newly selected relationship still needs a visible, non-duplicate target.
    other = create(http, request='another-00001')
    with pytest.raises(ValueError, match='visible and not a duplicate'):
        ideas.moderate(other, status='duplicate', duplicate_id=survivor, **decision)


def test_withdrawal_combined_with_status_is_rejected_without_silent_audit_loss(http):
    idea_id = create(http)
    decision = {'operator': 'Maintainer', 'explanation': 'Decision explanation'}
    with pytest.raises(ValueError, match='separately before withdrawal'):
        ideas.moderate(idea_id, status='declined', visibility='withdrawn', **decision)
    assert ideas.operator_detail(idea_id)['visibility'] == 'visible'
    with db._connection() as conn:
        assert conn.execute('SELECT count(*) FROM community_decisions').fetchone()[0] == 0
    ideas.moderate(idea_id, status='declined', **decision)
    ideas.moderate(idea_id, visibility='withdrawn', **decision)
    with db._connection() as conn:
        assert conn.execute('SELECT status,visibility FROM community_decisions ORDER BY id').fetchall() == [
            ('declined', 'visible'), ('declined', 'withdrawn')]


def test_hidden_content_remains_withdrawable_under_approved_retention(http):
    idea_id = create(http)
    ideas.moderate(idea_id, operator='Maintainer', explanation='Hidden pending review.', visibility='hidden')
    assert http('/ideas/withdraw', body={'id': idea_id})[0] == 200
    assert http('/ideas/withdraw', body={'id': idea_id})[0] == 200
    row = ideas.operator_detail(idea_id)
    assert row['title'] == row['description'] == '' and row['visibility'] == 'withdrawn'
    with db._connection() as conn:
        assert conn.execute('SELECT count(*) FROM community_decisions').fetchone()[0] == 2
    assert http('/ideas/submit', body=submission())[1]['id'] == idea_id


def test_page_queries_are_bounded_and_preserve_names_votes_and_private_fields(accounts, monkeypatch):
    monkeypatch.setattr(ideas, 'SUBMISSIONS_PER_DAY', 60)
    ids = [ideas.submit(accounts[0], submission(request=f'page-item-{n:04}'))['id'] for n in range(50)]
    ideas.vote(accounts[1], ids[0], True)
    ideas.listing(accounts[1], limit=1)  # Initialize the signing key before comparing steady-state reads.
    queries = []
    connect = db._connect
    def traced():
        conn = connect()
        conn.set_trace_callback(queries.append)
        return conn
    monkeypatch.setattr(db, '_connect', traced)
    sizes = []
    for limit in [1, 50]:
        queries.clear()
        result = ideas.listing(accounts[1], limit=limit)
        sizes.append(sum(q.lstrip().upper().startswith(('SELECT', 'WITH')) for q in queries))
        assert len(result['ideas']) == limit
        assert all(row['author'] == 'Ada' and not row['own'] for row in result['ideas'])
        assert not any('member_id' in row or 'request_hash' in row for row in result['ideas'])
    assert sizes[0] == sizes[1] <= 8
    assert result['ideas'][-1]['votes'] == 1 and result['ideas'][-1]['supported']


def test_cli_parser_and_local_screen_do_not_import_the_http_runtime():
    probe = '''
import importlib.abc, sys
class RefuseServer(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'server' or fullname.startswith('server.'):
            raise AssertionError('HTTP runtime imported by CLI registration')
sys.meta_path.insert(0, RefuseServer())
import main
parser = main.build_parser()
assert parser.parse_args(['ideas', 'list']).func.__module__ == 'persistence.ideas_cli'
from content_screen import local_tier
assert local_tier('A clearer crossing') == 'clean'
assert 'server' not in sys.modules
'''
    subprocess.run([sys.executable, '-c', probe], check=True, capture_output=True)
