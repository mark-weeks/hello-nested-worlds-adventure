from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.backup_health import assess

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def artifact(stamp='20261003T113000Z', **changes):
    return dict(id=1, name=f'worlds-backup-enfolded-beta-{stamp}', expired=False,
                expires_at='2027-01-01T00:00:00Z', size_in_bytes=1024, **changes)


def test_snapshot_time_controls_age_not_a_recent_upload():
    old = artifact('20261003T100000Z', created_at='2026-10-03T11:59:00Z')
    result = assess({'artifacts': [old]}, app='enfolded-beta', now=NOW)
    assert result['status'] == 'stale'
    assert result['age_minutes'] == 120


@pytest.mark.parametrize('changes', [
    {'expired': True}, {'size_in_bytes': 0}, {'expires_at': '2026-10-03T11:59:00Z'},
    {'name': 'worlds-backup-enfolded-staging-20261003T113000Z'},
    {'name': 'worlds-backup-20261003-1100'},
    {'name': 'worlds-backup-enfolded-beta-20261003T130000Z'},
])
def test_unusable_wrong_world_or_future_artifacts_cannot_pass(changes):
    candidate = artifact()
    candidate.update(changes)
    assert assess({'artifacts': [candidate]}, app='enfolded-beta', now=NOW)['status'] == 'missing'


def test_pagination_and_unsorted_responses_preserve_latest_snapshot():
    pages = [{'artifacts': [artifact('20261003T110000Z')]}, {'artifacts': [artifact()]}]
    result = assess(pages, app='enfolded-beta', now=NOW)
    assert result['status'] == 'fresh'
    assert result['age_minutes'] == 30


def test_cli_missing_artifact_is_failure_and_malformed_response_is_unavailable(tmp_path):
    source = tmp_path / 'artifacts.json'
    script = Path(__file__).resolve().parents[1] / 'scripts/backup_health.py'
    for payload, expected in [({'artifacts': []}, 1), ({'error': 'forbidden'}, 2)]:
        source.write_text(json.dumps(payload))
        result = subprocess.run([sys.executable, str(script), '--artifacts', str(source),
                                 '--app', 'enfolded-beta'], capture_output=True, text=True)
        assert result.returncode == expected


def test_invalid_age_limit_is_not_a_healthy_report():
    with pytest.raises(ValueError):
        assess({'artifacts': [artifact()]}, app='enfolded-beta', max_age_minutes=0, now=NOW)


@pytest.mark.parametrize('required,token,expected,ready', [
    ('0', '', 0, 'ready=no'), ('1', '', 1, ''),
    ('1', 'fixture-token', 0, 'ready=yes'), ('invalid', '', 2, ''),
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
