"""Public export privacy and remote/local failure boundaries; never real GitHub."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
from urllib.parse import parse_qs, urlsplit

import pytest

import persistence as db
from persistence import ideas, participants
from server import idea_promotion as p
from tests.test_participant_contracts import accounts, http  # noqa: F401
from tests.test_ideas import create, submission


def brief(**changes):
    return {'public_title':'Clarify crossing destinations', 'problem':'Crossings need clearer destination cues.',
            'outcome':'A player understands where a crossing leads.', 'scope':'Show a destination cue; preserve world identity.',
            'acceptance_checks':'Exercise map and scene views on mobile and desktop.',
            'decisions':'ADR-023 and ADR-026.', 'open_questions':'None recorded.',
            'reviewed':True, **changes}


@pytest.fixture
def intent(http):
    idea_id = create(http)
    result = p.prepare(idea_id, brief(), operator='Maintainer')
    return idea_id, result['review_hash']


@pytest.fixture
def github():
    state = {'issues':[], 'posts':0, 'requests':[], 'behavior':'ok', 'hidden':False, 'on_post':None, 'redirect':False}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def send(self, body, code=200):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            state['requests'].append(('GET',self.path))
            if state['redirect']:
                self.send_response(302)
                self.send_header('Location', state['base'] + '/credential-trap')
                self.end_headers()
                return
            parsed = urlsplit(self.path)
            if '/issues/' in parsed.path:
                number = int(parsed.path.rsplit('/',1)[1])
                return self.send(next((i for i in state['issues'] if i['number'] == number), {}))
            query = parse_qs(parsed.query)
            assert query['state'] == ['all'] and query['per_page'] == ['100']
            page = int(query['page'][0])
            self.send([] if state['hidden'] else state['issues'][(page-1)*100:page*100])
        def do_POST(self):
            state['posts'] += 1
            state['requests'].append(('POST',self.path))
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if state['on_post']:
                state['on_post'](data)
            if state['behavior'] == 'reject':
                return self.send({'private':'nw_do_not_echo_this', 'error':'private upstream text'}, 422)
            issue = {'number':len(state['issues'])+1, 'body':data['body'], 'title':data['title'],
                     'html_url':'https://evil.invalid/?key=nw_never_follow'}
            if state['behavior'] != 'drop_before_accept':
                state['issues'].append(issue)
            if state['behavior'] in ('drop_after_accept','drop_before_accept'):
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            self.send(issue, 201)
    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = p.GitHub('fake-operator-token')
    base = f'http://127.0.0.1:{server.server_port}'
    original = client._open
    def local(request, timeout):
        parsed = urlsplit(request.full_url)
        # Test-only transport redirection; production exposes no configurable API host.
        request.full_url = base + parsed.path + ('?' + parsed.query if parsed.query else '')
        return original(request, timeout=timeout)
    client._open = local
    state.update(client=client, base=base)
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_prepare_preview_is_allowlisted_anonymous_and_offline(http, accounts, monkeypatch):
    idea_id = create(http, title='Private report title', request='private-report')
    owner = participants.identify(accounts[0])['id']
    participants.save_profile(owner, {'bio':'Private unpublished bio','published':False})
    with db._connection() as conn:
        conn.execute('INSERT INTO journal_notes(id,participant_id,world_seed,node_name,text) VALUES (?,?,?,?,?)',
                     ('private-note',owner,382,'fixture-place','Private journal details'))
    monkeypatch.setattr(p, 'GitHub', lambda *a: pytest.fail('Preparation and preview must be offline'))
    result = p.prepare(idea_id, brief(), operator='Private operator name')
    output = p.preview(idea_id)
    assert p.marker(result['token']) in output and idea_id in output and result['review_hash'] in output
    for private in ('Ada','Private report title','Private unpublished bio','Private journal details',owner,
                    accounts[0],db._credential_digest(accounts[0]),'Private operator name',submission()['description']):
        assert private not in output
    assert p.get(idea_id)['state'] == 'prepared'
    assert http('/ideas/detail?id=' + idea_id)[1]['idea']['issue_url'] is None
    assert 'brief' not in json.dumps(http('/ideas/detail?id=' + idea_id)[1])


def test_opt_in_credit_and_plain_text_export(http):
    idea_id = create(http, public_credit=True)
    result = p.prepare(idea_id, brief(include_credit=True, scope='Do not execute <script>x()</script> or ![tracking](https://evil.invalid/a).'), operator='Maintainer')
    output = p.preview(idea_id)
    assert 'Ada' in output and 'public credit opted in' in output
    assert '\n```\nDo not execute <script>x()</script> or ![tracking](https://evil.invalid/a).\n```\n' in output
    assert result['state'] == 'prepared'


@pytest.mark.parametrize('changes', [dict(include_credit=True),dict(problem='Ada requested this'),
    dict(problem='nw_'+'x'*32),dict(problem='email: person@example.test'),
    dict(problem='Device 12345678-abcd-abcd-abcd-123456789012'),dict(raw_submission='Private'),
    dict(voters=['a']),dict(reviewed=False),dict(public_title='x'*121),dict(scope=[]),
    dict(public_title='one\ntwo'),dict(problem='https://example.test/?key=secret')])
def test_public_brief_rejects_private_or_unreviewed_material(http, changes):
    idea_id = create(http)
    with pytest.raises(ValueError):
        p.prepare(idea_id, brief(**changes), operator='Maintainer')
    with db._connection() as conn:
        assert conn.execute('SELECT count(*) FROM community_promotions').fetchone()[0] == 0


def test_private_participant_and_credential_aliases_cannot_export(http, accounts):
    idea_id = create(http)
    owner = participants.identify(accounts[0])['id']
    for value in (owner, db._credential_digest(accounts[0]),db._credential_digest(accounts[0])[:16]):
        with pytest.raises(ValueError):
            p.prepare(idea_id, brief(problem='Observed ID ' + value), operator='Maintainer')


def test_exact_preview_hash_and_durable_intent_precede_any_remote_write(intent, github):
    idea_id, digest = intent
    with pytest.raises(ideas.Conflict):
        p.publish(idea_id,'wrong',operator='Maintainer',github=github['client'])
    assert github['posts'] == 0 and not github['requests']
    def on_post(data):
        assert set(data) == {'title','body'}  # No assignee or agent launch instruction.
        row = p.get(idea_id)
        assert row['state'] == 'publishing' and row['review_hash'] == digest
        assert p.marker(row['token']) in data['body']
        # A new independent writer can acquire the lock while HTTP publication is in flight.
        with db.transaction() as conn:
            conn.execute("INSERT OR REPLACE INTO community_settings VALUES ('fixture-writer','ok')")
    github['on_post'] = on_post
    result = p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert result['state'] == 'published' and result['issue_url'] == 'https://github.com/' + p.DEFAULT_REPOSITORY + '/issues/1'
    assert p.publish(idea_id,digest,operator='Maintainer',github=github['client']) == result
    assert github['posts'] == 1 and github['requests'][0][0] == 'GET'
    assert 'evil.invalid' not in result['issue_url']
    with db._connection() as conn:
        assert conn.execute('SELECT action FROM community_promotion_events WHERE idea_id=? ORDER BY id', (idea_id,)).fetchall() == [('prepared',),('publish_requested',),('issue_linked',)]


def test_concurrent_publishers_send_only_one_post(intent, github):
    idea_id,digest = intent
    def publish(_):
        try:
            return p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
        except p.Uncertain:
            return None
    with ThreadPoolExecutor(8) as pool:
        outcomes = list(pool.map(publish, range(8)))
    assert any(result is not None and result['state'] == 'published' for result in outcomes)
    assert all(result is None or result['state'] == 'published' for result in outcomes)
    assert github['posts'] == 1 and p.get(idea_id)['state'] == 'published'


def test_timeout_after_acceptance_recovers_by_token_without_resending(intent, github, http):
    idea_id,digest = intent
    github['behavior'] = 'drop_after_accept'
    with pytest.raises(p.Uncertain):
        p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert p.get(idea_id)['state'] == 'uncertain' and github['posts'] == 1
    # A temporarily missing/late remote result is never proof that it was not created.
    github['hidden'] = True
    with pytest.raises(p.Uncertain):
        p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert github['posts'] == 1
    github['hidden'] = False
    result = p.reconcile(idea_id,operator='Maintainer',github=github['client'])
    assert result['state'] == 'published' and github['posts'] == 1
    state = http('/ideas/detail?id=' + idea_id)[1]['idea']
    assert state['issue_url'] == result['issue_url'] and state['status'] == 'considering'


def test_uncertain_without_remote_acceptance_stays_fenced(intent, github):
    idea_id,digest = intent
    github['behavior'] = 'drop_before_accept'
    for _ in range(3):
        with pytest.raises(p.Uncertain):
            p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert github['posts'] == 1 and not github['issues'] and p.get(idea_id)['state'] == 'uncertain'


def test_definitive_rejection_allows_explicit_retry_but_does_not_echo_response(intent, github):
    idea_id,digest = intent
    github['behavior'] = 'reject'
    with pytest.raises(p.Rejected) as error:
        p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert p.get(idea_id)['state'] == 'prepared'
    assert 'nw_' not in str(error.value) + p.get(idea_id)['last_error']
    github['behavior'] = 'ok'
    assert p.publish(idea_id,digest,operator='Maintainer',github=github['client'])['state'] == 'published'
    assert github['posts'] == 2 and len(github['issues']) == 1


def test_local_link_failure_after_remote_acceptance_is_reconciled(intent, github, monkeypatch):
    idea_id,digest = intent
    original = p._link
    monkeypatch.setattr(p, '_link', lambda *a,**k: (_ for _ in ()).throw(sqlite3.OperationalError('private detail nw_secret')))
    with pytest.raises(p.Uncertain) as error:
        p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert 'private detail' not in str(error.value) and 'nw_' not in p.get(idea_id)['last_error']
    monkeypatch.setattr(p,'_link',original)
    assert p.reconcile(idea_id,operator='Maintainer',github=github['client'])['state'] == 'published'
    assert github['posts'] == 1


def test_failed_local_intent_commit_never_publishes(intent, github):
    idea_id,digest = intent
    with db._connection() as conn:
        conn.execute("""CREATE TRIGGER fixture_refuse_claim BEFORE UPDATE OF state ON community_promotions
            WHEN NEW.state='publishing' BEGIN SELECT RAISE(ABORT,'fixture commit refusal'); END""")
    with pytest.raises(sqlite3.DatabaseError):
        p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert github['posts'] == 0 and p.get(idea_id)['state'] == 'prepared'


@pytest.mark.parametrize('after_remote', [False,True])
def test_process_death_preserves_claim_and_reconciles_without_duplicate(intent, github, after_remote):
    idea_id,digest = intent
    code = '''import os,sys
from pathlib import Path
from urllib.parse import urlsplit
import persistence as db
from server import idea_promotion as p
db._DB_PATH=Path(sys.argv[1])
client=p.GitHub('fake-operator-token')
original=client._open
def local(request,timeout):
    parsed=urlsplit(request.full_url)
    request.full_url=sys.argv[4]+parsed.path+('?' + parsed.query if parsed.query else '')
    return original(request,timeout=timeout)
client._open=local
if sys.argv[5]=='after':
    p._link=lambda *a,**k: os._exit(73)
else:
    client.create=lambda *a: os._exit(73)
p.publish(sys.argv[2],sys.argv[3],operator='Fixture',github=client)
'''
    result = subprocess.run([sys.executable,'-c',code,str(db._DB_PATH),idea_id,digest,github['base'], 'after' if after_remote else 'before'],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True)
    assert result.returncode == 73, result.stderr
    assert p.get(idea_id)['state'] == 'publishing'
    if after_remote:
        assert p.reconcile(idea_id,operator='Maintainer',github=github['client'])['state'] == 'published'
        assert github['posts'] == 1
    else:
        with pytest.raises(p.Uncertain):
            p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
        assert github['posts'] == 0


def test_paginated_reconciliation_finds_closed_manual_issue_and_rejects_collisions(intent, github):
    idea_id,_ = intent
    token = p.get(idea_id)['token']
    github['issues'] = [{'number':n+1,'body':'unrelated'} for n in range(100)] + [
        {'number':101,'body':p.marker(token),'state':'closed'}]
    result = p.reconcile(idea_id,operator='Maintainer',github=github['client'])
    assert result['issue_url'].endswith('/101') and github['posts'] == 0
    assert any('page=2' in url for _,url in github['requests'])


def test_multiple_matching_issues_fail_closed(intent, github):
    idea_id,digest = intent
    token = p.get(idea_id)['token']
    github['issues'] = [{'number':n,'body':p.marker(token)} for n in (1,2)]
    with pytest.raises(p.RemoteFailure):
        p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert github['posts'] == 0 and p.get(idea_id)['issue_url'] is None


def test_manual_issue_link_must_match_repository_number_and_token(intent, github):
    idea_id,_ = intent
    token = p.get(idea_id)['token']
    github['issues'] = [{'number':1,'body':'unrelated'}, {'number':2,'body':p.marker(token)}]
    for url in ('https://evil.invalid/issues/1', 'https://github.com/'+p.DEFAULT_REPOSITORY+'/issues/2?key=secret'):
        with pytest.raises(ValueError):
            p.record_link(idea_id,url,operator='Maintainer',github=github['client'])
    with pytest.raises(p.RemoteFailure):
        p.record_link(idea_id,'https://github.com/'+p.DEFAULT_REPOSITORY+'/issues/1',operator='Maintainer',github=github['client'])
    assert p.record_link(idea_id,'https://github.com/'+p.DEFAULT_REPOSITORY+'/issues/2',operator='Maintainer',github=github['client'])['state'] == 'published'
    assert github['posts'] == 0


def test_amendment_preserves_token_and_invalidates_old_preview(intent, github):
    idea_id,digest = intent
    token = p.get(idea_id)['token']
    updated = p.prepare(idea_id,brief(outcome='A legible destination cue.'),operator='Maintainer')
    assert updated['token'] == token and updated['review_hash'] != digest
    with pytest.raises(ideas.Conflict):
        p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    p.publish(idea_id,updated['review_hash'],operator='Maintainer',github=github['client'])
    with pytest.raises(ideas.Conflict):
        p.prepare(idea_id,brief(),operator='Maintainer')


def test_hidden_and_withdrawn_source_never_exports_or_starts_publication(intent, http, github):
    idea_id,digest = intent
    ideas.moderate(idea_id,operator='Maintainer',explanation='Review',visibility='hidden')
    with pytest.raises(ideas.Missing):
        p.preview(idea_id)
    with pytest.raises(ideas.Missing):
        p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert github['posts'] == 0
    http('/ideas/withdraw',body={'id':idea_id})
    row = p.get(idea_id)
    assert row['state'] == 'cancelled' and row['brief'] == row['public_title'] == ''
    with pytest.raises(ideas.Conflict):
        p.publish(idea_id,digest,operator='Maintainer',github=github['client'])


def test_withdrawal_during_authorized_publication_scrubs_brief_but_keeps_result(intent, github, accounts):
    idea_id,digest = intent
    github['on_post'] = lambda data: ideas.withdraw(accounts[0],idea_id)
    result = p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert result['state'] == 'published'
    assert p.get(idea_id)['brief'] == p.get(idea_id)['public_title'] == ''
    assert ideas.operator_detail(idea_id)['visibility'] == 'withdrawn'
    assert result['issue_url'] and github['posts'] == 1


def test_operator_cli_and_no_browser_publish_route(intent, http, github, monkeypatch, capsys):
    from main import build_parser
    idea_id,digest = intent
    args = build_parser().parse_args(['ideas','preview',idea_id])
    args.func(args)
    assert digest in capsys.readouterr().out
    for route in ('/ideas/publish','/ideas/prepare','/ideas/reconcile'):
        assert http(route,body={'id':idea_id,'reviewed_sha256':digest})[0] == 405
    monkeypatch.setattr(p,'GitHub',lambda: github['client'])
    args = build_parser().parse_args(['ideas','publish',idea_id,'--reviewed-sha256',digest,'--operator','Maintainer'])
    args.func(args)
    assert 'published' in capsys.readouterr().out and github['posts'] == 1


def test_github_transport_refuses_redirects_and_missing_tokens(monkeypatch, github):
    monkeypatch.delenv('ENFOLDED_GITHUB_TOKEN',raising=False)
    with pytest.raises(p.RemoteFailure):
        p.GitHub()
    github['redirect'] = True
    with pytest.raises(p.RemoteFailure):
        github['client'].matches(p.DEFAULT_REPOSITORY, 'a'*32)
    assert len(github['requests']) == 1
    assert 'credential-trap' not in github['requests'][0][1]


def test_ideas_outer_errors_do_not_forward_private_credential_frames(http, monkeypatch):
    def failure(*args, **kwargs):
        raise sqlite3.OperationalError('private submission nw_never_export')
    monkeypatch.setattr(participants, 'identify', failure)
    monkeypatch.setattr('server.observability.capture_exception', lambda *args: pytest.fail('Private community frame reached telemetry'))
    for route,body in [('/ideas/list',None),('/ideas/submit',submission())]:
        status,data,headers = http(route,body=body)
        assert status == 503 and headers['Cache-Control'] == 'no-store'
        assert 'private submission' not in json.dumps(data) and 'nw_' not in json.dumps(data)


def test_publication_does_not_change_world_tables_or_community_status(intent, github, http):
    idea_id,digest = intent
    tables = ('world_nodes','world_mutations','world_meta','agent_memory','puzzle_results')
    def snapshot():
        with db._connection() as conn:
            return {table:conn.execute('SELECT * FROM '+table).fetchall() for table in tables}
    before = snapshot()
    p.publish(idea_id,digest,operator='Maintainer',github=github['client'])
    assert snapshot() == before
    assert http('/ideas/detail?id='+idea_id)[1]['idea']['status'] == 'considering'
    expected = p.get(idea_id)['issue_url']
    assert http('/ideas/list')[1]['ideas'][0]['issue_url'] == expected
    assert http('/ideas/search', body={})[1]['ideas'][0]['issue_url'] == expected
