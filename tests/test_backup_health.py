from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.backup_health import WORKFLOW, assess as assess_artifacts

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
WORKFLOW_METADATA = {'id': 42, 'path': WORKFLOW}


def backup_run(**changes):
    return {**dict(id=7, workflow_id=42, path=WORKFLOW, event='schedule',
                   status='completed', conclusion='success', head_branch='main',
                   head_sha='fixture-sha', repository={'id': 1}, head_repository={'id': 1}),
            **changes}


def check(pages, *, runs=None, **kwargs):
    runs = {7: backup_run()} if runs is None else runs
    return assess_artifacts(pages, workflow=WORKFLOW_METADATA, run_lookup=runs.__getitem__, **kwargs)


def artifact(stamp='20261003T113000Z', **changes):
    return {**dict(id=1, name=f'worlds-backup-enfolded-beta-{stamp}', expired=False,
                   expires_at='2027-01-01T00:00:00Z', size_in_bytes=1024,
                   workflow_run={'id': 7, 'repository_id': 1, 'head_repository_id': 1,
                                 'head_branch': 'main', 'head_sha': 'fixture-sha'}), **changes}


def test_snapshot_time_controls_age_not_a_recent_upload():
    old = artifact('20261003T100000Z', created_at='2026-10-03T11:59:00Z')
    result = check({'artifacts': [old]}, app='enfolded-beta', now=NOW)
    assert result['status'] == 'stale'
    assert result['age_minutes'] == 120


@pytest.mark.parametrize('changes', [
    {'expired': True}, {'size_in_bytes': 0}, {'expires_at': '2026-10-03T11:59:00Z'},
    {'name': 'worlds-backup-enfolded-staging-20261003T113000Z'},
    {'name': 'worlds-backup-20261003-1100'},
    {'name': 'worlds-backup-enfolded-beta-20261003T130000Z'},
    {'name': 'unvalidated-worlds-backup-enfolded-beta-20261003T113000Z'},
    {'expires_at': None}, {'name': None}, {'size_in_bytes': '1024'},
])
def test_unusable_wrong_world_or_future_artifacts_cannot_pass(changes):
    candidate = artifact()
    candidate.update(changes)
    assert check({'artifacts': [candidate]}, app='enfolded-beta', now=NOW)['status'] == 'missing'


def test_pagination_and_unsorted_responses_preserve_latest_snapshot():
    pages = [{'artifacts': [artifact('20261003T110000Z')]}, {'artifacts': [artifact()]}]
    result = check(pages, app='enfolded-beta', now=NOW)
    assert result['status'] == 'fresh'
    assert result['age_minutes'] == 30


def test_cli_missing_artifact_is_failure_and_malformed_response_is_unavailable(tmp_path):
    source = tmp_path / 'artifacts.json'
    script = Path(__file__).resolve().parents[1] / 'scripts/backup_health.py'
    for payload, expected in [({'workflow': WORKFLOW_METADATA, 'artifact_pages': [{'artifacts': []}],
                               'runs': []}, 1), ({'error': 'forbidden'}, 2)]:
        source.write_text(json.dumps(payload))
        result = subprocess.run([sys.executable, str(script), '--artifacts', str(source),
                                 '--app', 'enfolded-beta'], capture_output=True, text=True)
        assert result.returncode == expected


def test_invalid_age_limit_is_not_a_healthy_report():
    with pytest.raises(ValueError):
        check({'artifacts': [artifact()]}, app='enfolded-beta', max_age_minutes=0, now=NOW)


@pytest.mark.parametrize('required,token,expected,ready', [
    ('', '', 0, 'ready=no'), ('false', '', 0, 'ready=no'), ('true', '', 1, ''),
    ('true', 'fixture-token', 0, 'ready=yes'), ('tru', '', 2, ''),
    ('tru', 'fixture-token', 2, ''), ('TRUE', '', 2, ''), ('0', '', 2, ''),
])
def test_actual_workflow_gate_fails_when_active_without_a_token(tmp_path, required, token, expected, ready):
    output, summary = tmp_path / 'output', tmp_path / 'summary'
    script = Path(__file__).resolve().parents[1] / 'scripts/backup_gate.sh'
    result = subprocess.run(['bash', str(script)], env={**os.environ,
        'BACKUP_REQUIRED': required, 'FLY_API_TOKEN': token,
        'GITHUB_OUTPUT': str(output), 'GITHUB_STEP_SUMMARY': str(summary)},
        capture_output=True, text=True)
    assert result.returncode == expected
    assert (output.read_text().strip() if output.exists() else '') == ready
    assert not token or token not in result.stdout + result.stderr


@pytest.mark.parametrize('changes', [
    {'workflow_id': 99}, {'path': '.github/workflows/unrelated.yml'},
    {'head_branch': 'feature'}, {'event': 'pull_request'},
    {'status': 'in_progress', 'conclusion': None}, {'conclusion': 'failure'},
    {'head_repository': {'id': 2}}, {'head_sha': 'different-sha'}, {'id': 8},
])
def test_expected_name_cannot_certify_an_untrusted_or_unfinished_run(changes):
    result = check({'artifacts': [artifact()]}, runs={7: backup_run(**changes)},
                   app='enfolded-beta', now=NOW)
    assert result['status'] == 'missing'


@pytest.mark.parametrize('source', [None, {}, {'id': '7'},
    {'id': 7, 'repository_id': 1, 'head_repository_id': 2, 'head_branch': 'main', 'head_sha': 'fixture-sha'},
])
def test_artifact_requires_matching_source_repository_metadata(source):
    assert check({'artifacts': [artifact(workflow_run=source)]},
                 app='enfolded-beta', now=NOW)['status'] == 'missing'


def test_newer_untrusted_artifact_cannot_hide_stale_valid_backup():
    old = artifact('20261003T100000Z')
    fake = artifact(workflow_run={**old['workflow_run'], 'id': 8})
    result = check({'artifacts': [old, fake]}, runs={7: backup_run(), 8: backup_run(id=8, workflow_id=99)},
                   app='enfolded-beta', now=NOW)
    assert result['status'] == 'stale'
    assert result['run_id'] == 7


def test_run_metadata_is_required_even_for_a_fresh_name():
    with pytest.raises(KeyError):
        check({'artifacts': [artifact()]}, runs={}, app='enfolded-beta', now=NOW)


def test_cli_queries_workflow_and_run_provenance_via_actual_gh_command(tmp_path):
    candidate = artifact(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                         expires_at='2999-01-01T00:00:00Z')
    responses = {
        'repos/owner/repo/actions/workflows/backup.yml': WORKFLOW_METADATA,
        'repos/owner/repo/actions/artifacts?per_page=100': [{'artifacts': [candidate]}],
        'repos/owner/repo/actions/runs/7': backup_run(),
    }
    fixtures, calls = tmp_path / 'responses.json', tmp_path / 'calls.jsonl'
    fixtures.write_text(json.dumps(responses))
    fake_gh = tmp_path / 'gh'
    fake_gh.write_text(f'#!{sys.executable}\n' + '''import json,os,sys
from pathlib import Path
with open(os.environ['GH_FIXTURE_CALLS'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
print(json.dumps(json.loads(Path(os.environ['GH_FIXTURE_RESPONSES']).read_text())[sys.argv[2]]))
''')
    fake_gh.chmod(0o755)
    script = Path(__file__).resolve().parents[1] / 'scripts/backup_health.py'
    result = subprocess.run([sys.executable, str(script), '--repository', 'owner/repo',
                             '--app', 'enfolded-beta'], capture_output=True, text=True,
        env={**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
             'GH_FIXTURE_CALLS': str(calls), 'GH_FIXTURE_RESPONSES': str(fixtures)})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'fresh'
    requests = [json.loads(line) for line in calls.read_text().splitlines()]
    assert [r[1] for r in requests] == list(responses)
    assert requests[1][-2:] == ['--paginate', '--slurp']
