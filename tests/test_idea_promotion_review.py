"""PR #103 recovery interleavings and public-rendering contract; no live issues."""
from html.parser import HTMLParser
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import persistence as db
from persistence import ideas, ideas_cli, participants
from server import idea_promotion as p
from tests.test_idea_promotion import brief, github, intent  # noqa: F401
from tests.test_ideas import create
from tests.test_participant_contracts import accounts, http  # noqa: F401


def settle(idea_id, state, key):
    if state == 'published':
        return p._link(idea_id, {'number': 123, 'body': p.marker(p.get(idea_id)['token'])}, operator='Fixture')
    ideas.withdraw(key, idea_id)
    return p.summary(p.get(idea_id))


@pytest.mark.parametrize('state', ['published', 'cancelled'])
def test_claim_reports_a_concurrently_settled_outcome(intent, github, accounts, monkeypatch, state):
    idea_id, digest = intent
    original = p.reconcile
    def reconcile(*args, **kwargs):
        stale = original(*args, **kwargs)
        settle(idea_id, state, accounts[0])
        return stale
    monkeypatch.setattr(p, 'reconcile', reconcile)
    if state == 'published':
        result = p.publish(idea_id, digest, operator='Fixture', github=github['client'])
        assert result['state'] == state and result['issue_url'].endswith('/123')
    else:
        with pytest.raises(ideas.Conflict, match='cancelled'):
            p.publish(idea_id, digest, operator='Fixture', github=github['client'])
    assert github['posts'] == 0


@pytest.mark.parametrize('state', ['published', 'cancelled'])
def test_reconcile_refreshes_local_state_after_remote_read(intent, accounts, state):
    idea_id, _ = intent
    class Remote:
        def matches(self, *_):
            settle(idea_id, state, accounts[0])
            return []
    assert p.reconcile(idea_id, operator='Fixture', github=Remote())['state'] == state


@pytest.mark.parametrize('withdraw', [False, True])
def test_definitive_rejection_settles_concurrent_reconcile_without_reviving_withdrawal(
        intent, github, accounts, withdraw):
    idea_id, digest = intent
    github['behavior'] = 'reject'
    def during_post(_):
        with pytest.raises(p.Uncertain):
            p.reconcile(idea_id, operator='Concurrent operator', github=github['client'])
        assert p.get(idea_id)['state'] == 'uncertain'
        if withdraw:
            ideas.withdraw(accounts[0], idea_id)
    github['on_post'] = during_post
    with pytest.raises(p.Rejected):
        p.publish(idea_id, digest, operator='Fixture', github=github['client'])
    row = p.get(idea_id)
    assert row['state'] == ('cancelled' if withdraw else 'prepared')
    github['on_post'] = None
    github['behavior'] = 'ok'
    if withdraw:
        assert row['brief'] == row['public_title'] == ''
        with pytest.raises(ideas.Conflict, match='cancelled'):
            p.publish(idea_id, digest, operator='Fixture', github=github['client'])
        assert github['posts'] == 1 and not github['issues']
    else:
        assert p.publish(idea_id, digest, operator='Fixture', github=github['client'])['state'] == 'published'
        assert github['posts'] == 2 and len(github['issues']) == 1


def test_rejection_after_withdrawal_without_reconcile_also_cancels(intent, github, accounts):
    idea_id, digest = intent
    github['behavior'] = 'reject'
    github['on_post'] = lambda _: ideas.withdraw(accounts[0], idea_id)
    with pytest.raises(p.Rejected):
        p.publish(idea_id, digest, operator='Fixture', github=github['client'])
    row = p.get(idea_id)
    assert row['state'] == 'cancelled' and row['brief'] == row['public_title'] == ''


def test_definitive_rejection_does_not_overwrite_a_verified_concurrent_link(intent, github):
    idea_id, digest = intent
    github['behavior'] = 'reject'
    def during_post(_):
        issue = {'number': 7, 'body': p.marker(p.get(idea_id)['token'])}
        github['issues'].append(issue)
        p.record_link(idea_id, f'https://github.com/{p.DEFAULT_REPOSITORY}/issues/7',
                      operator='Concurrent operator', github=github['client'])
    github['on_post'] = during_post
    result = p.publish(idea_id, digest, operator='Fixture', github=github['client'])
    assert result['state'] == 'published' and result['issue_url'].endswith('/7')
    assert github['posts'] == 1 and len(github['issues']) == 1


def test_prepared_target_stays_fixed_and_exported_manual_issue_is_recoverable(intent, github):
    idea_id, _ = intent
    original = p.get(idea_id)
    assert original['repository'] in p.preview(idea_id)
    github['issues'].append({'number': 7, 'body': original['brief']})
    with pytest.raises(ideas.Conflict, match='repository is fixed'):
        p.prepare(idea_id, brief(), operator='Fixture', repository='different/repository')
    assert p.get(idea_id) == original
    result = p.reconcile(idea_id, operator='Fixture', github=github['client'])
    assert result['state'] == 'published' and result['issue_url'].endswith('/7')
    assert github['posts'] == 0


def test_board_and_public_credit_share_the_registered_name_after_replacement(http, accounts):
    idea_id = create(http, public_credit=True)
    member = participants.identify(accounts[0])['id']
    replacement = 'nw_' + 'c' * 32
    participants.rotate(accounts[0], replacement)
    with db._connection() as conn:
        conn.execute('UPDATE invite_keys SET name=? WHERE key=?', ('Updated registered name', db._credential_digest(replacement)))
    assert participants.identify(replacement)['id'] == member
    board_name = http('/ideas/detail?id=' + idea_id, replacement)[1]['idea']['author']
    assert board_name == 'Updated registered name'
    p.prepare(idea_id, brief(include_credit=True), operator='Fixture')
    assert p._markdown(board_name + ' — reporting/playtesting; public credit opted in.') in p.preview(idea_id)


@pytest.mark.parametrize('repository', [None, 'explicit/repository'])
def test_cli_resolves_default_only_when_running_promotion(http, monkeypatch, capsys, tmp_path, repository):
    from main import build_parser
    idea_id = create(http)
    file = tmp_path / 'brief.json'
    file.write_text(json.dumps(brief()))
    argv = ['ideas', 'prepare', idea_id, '--brief', str(file), '--operator', 'Fixture']
    if repository:
        argv += ['--repository', repository]
    args = build_parser().parse_args(argv)
    monkeypatch.setattr(p, 'DEFAULT_REPOSITORY', 'changed/default')
    args.func(args)
    result = json.loads(capsys.readouterr().out)
    assert result['repository'] == (repository or 'changed/default')


@pytest.mark.parametrize('failure', ['missing', 'directory', 'permission'])
def test_brief_read_errors_do_not_claim_a_stored_intent(http, tmp_path, monkeypatch, failure):
    idea_id = create(http)
    private = tmp_path / 'private-credential-path.json'
    if failure == 'directory':
        private.mkdir()
    elif failure == 'permission':
        def refused(*_):
            raise PermissionError('private file detail')
        monkeypatch.setattr(Path, 'open', refused)
    with pytest.raises(SystemExit, match='public brief file could not be read') as error:
        ideas_cli.run_promotion(SimpleNamespace(action='prepare', brief=str(private), id=idea_id))
    assert 'private' not in str(error.value) and 'retained' not in str(error.value)
    with db._connection() as conn:
        assert conn.execute('SELECT count(*) FROM community_promotions').fetchone()[0] == 0


def test_prepare_commit_error_does_not_claim_publication_or_expose_details(http, tmp_path, monkeypatch):
    idea_id = create(http)
    file = tmp_path / 'brief.json'
    file.write_text(json.dumps(brief()))
    def failed(*args, **kwargs):
        raise OSError('private storage detail')
    monkeypatch.setattr(p, 'prepare', failed)
    with pytest.raises(SystemExit, match='Preparation was not confirmed') as error:
        ideas_cli.run_promotion(SimpleNamespace(action='prepare', brief=str(file), id=idea_id,
                                                operator='Fixture', repository=None))
    assert 'private' not in str(error.value) and 'retained' not in str(error.value)


class Rendered(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.text = [], []
    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
    def handle_data(self, data):
        self.text.append(data)


def test_public_text_matches_verified_github_rendering():
    # Captured from GitHub's /markdown GFM renderer with repository context.
    # Keep the exact Markdown paired with that independent rendering evidence.
    fixture = json.loads((Path(__file__).parent / 'fixtures' / 'idea-public-render.json').read_text())
    assert p._markdown(fixture['input']) == fixture['markdown']
    rendered = Rendered()
    rendered.feed(fixture['html'])
    assert set(rendered.tags) == {'pre', 'code'}
    assert ''.join(rendered.text).rstrip('\n') == fixture['input']


@pytest.mark.parametrize('ticks', [1, 2, 3, 4, 8])
def test_public_field_cannot_close_its_text_block(ticks):
    attempted_fence = '`' * ticks
    value = 'Start\n' + attempted_fence + '\n<img src=x> @mark-weeks #123\n   ' + attempted_fence
    rendered = p._markdown(value)
    fence, body = rendered.split('\n', 1)
    assert len(fence) > ticks and set(fence) == {'`'}
    assert body == value + '\n' + fence
