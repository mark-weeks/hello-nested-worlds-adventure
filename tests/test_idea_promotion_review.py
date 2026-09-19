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


@pytest.mark.parametrize('base_version', [24, 25])
def test_promotion_upgrade_preserves_main_and_board_data(monkeypatch, base_version):
    migrations = db._list_migrations()
    with monkeypatch.context() as previous:
        previous.setattr(db, '_list_migrations', lambda: [(v, path) for v, path in migrations if v <= base_version])
        db.init_db()
        key = 'nw_' + 'd' * 32
        db.mint_invite_key(key, 'Upgrade fixture')
        member = participants.identify(key)['id']
        participants.save_note(member, 382, 'Fixture place', 'Keep this private note', 'upgrade-note')
        idea_id = None
        if base_version == 25:
            idea_id = ideas.submit(key, {'title': 'Keep the existing idea', 'description': 'Existing board content.',
                                        'request_id': 'upgrade-idea'})['id']
            # Populate the pre-promotion schema without using a newer read path.
            with db.transaction() as conn:
                conn.execute('INSERT INTO community_votes VALUES (?,?)', (idea_id, member))
        with db._connection() as conn:
            names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='schema_version'")]
            before = {name: conn.execute(f'SELECT * FROM "{name}"').fetchall() for name in names}
            assert conn.execute('SELECT max(version) FROM schema_version').fetchone()[0] == base_version
    db._initialized.discard(db._DB_PATH)
    db.init_db()
    db.init_db()
    with db._connection() as conn:
        assert {name: conn.execute(f'SELECT * FROM "{name}"').fetchall() for name in names} == before
        assert conn.execute('SELECT version FROM schema_version WHERE version>=24 ORDER BY version').fetchall() == [(24,), (25,), (26,)]
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name LIKE 'community_%'").fetchone()[0] == 8
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name IN ('idx_world_mutations_material_node','idx_world_mutations_rearms')").fetchone()[0] == 2
    if idea_id is None:
        idea_id = ideas.submit(key, {'title': 'A new idea after upgrading', 'description': 'Board content after main upgrade.',
                                    'request_id': 'upgrade-idea'})['id']
    assert p.prepare(idea_id, brief(), operator='Fixture')['state'] == 'prepared'


class PreparedRendering(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks, self.links, self.comments, self.tags = [], [], [], []
        self.current = None
    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == 'pre':
            self.current = []
            self.blocks.append(self.current)
        if self.current is not None:
            assert tag in ('pre', 'code')
        if tag == 'a':
            self.links.append(dict(attrs).get('href', ''))
    def handle_endtag(self, tag):
        if tag == 'pre':
            self.current = None
    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)
    def handle_comment(self, data):
        self.comments.append(data)


def test_prepared_brief_matches_verified_github_rendering(http, monkeypatch):
    fixture = json.loads((Path(__file__).parent / 'fixtures' / 'idea-prepared-render.json').read_text())
    idea_id = create(http, public_credit=True)
    monkeypatch.setattr(p.secrets, 'token_hex', lambda _: fixture['token'])
    p.prepare(idea_id, fixture['input'], operator='Fixture')
    body = p.get(idea_id)['brief']
    # Only the randomly generated public board reference varies between runs.
    assert body.replace(idea_id, fixture['idea_id']) == fixture['markdown']
    assert p.marker(fixture['token']) in body
    assert body in p.preview(idea_id)
    rendered = PreparedRendering()
    rendered.feed(fixture['html'])
    expected = [fixture['input'][field] for field in p.FIELDS if field != 'public_title']
    expected.append('Ada — reporting/playtesting; public credit opted in.')
    assert [''.join(block).removesuffix('\n') for block in rendered.blocks] == expected
    assert not set(rendered.tags) & {'script', 'img', 'iframe', 'form', 'object', 'em', 'strong', 'del'}
    # Only GitHub's own heading anchors may be active; submitted links/references
    # and mentions remain literal text, including attempted closing fences.
    assert all(href.startswith('#') for href in rendered.links)
    assert fixture['idea_id'] in fixture['html']
    assert rendered.tags.count('h2') == len(expected)
    assert not any(fixture['token'] in comment for comment in rendered.comments)
