from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.backup_health import assess
from scripts.backup_store import object_key

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
APP = 'enfolded-beta'
STAMP = '20261003T113000Z'


def check(pages, **kwargs):
    return assess(pages, app=APP, **kwargs)


def stored(stamp=STAMP, *, quarantine=False, size=1024, **changes):
    item = {'Key': object_key(APP, stamp, quarantine=quarantine), 'Size': size,
            'LastModified': '2026-10-03T11:59:00Z'}
    item.update(changes)
    return item


def page(*items, **page_fields):
    return {'Prefix': 'offhost/', 'Contents': list(items), **page_fields}


def test_snapshot_time_controls_age_not_a_recent_upload():
    result = check(page(stored('20261003T100000Z')), now=NOW)
    assert result['status'] == 'stale'
    assert result['age_minutes'] == 120
    assert result['key'] == object_key(APP, '20261003T100000Z')


@pytest.mark.parametrize('item', [
    stored(size=0),
    stored(size=True),
    stored(size='1024'),
    stored('20261003T113000Z', quarantine=True),
    stored('20261003T130000Z'),
    {'Key': object_key('enfolded-staging', STAMP), 'Size': 1024},
    {'Key': 'worlds-backup-enfolded-beta-20261003T113000Z.db', 'Size': 1024},
    {'Key': object_key(APP, STAMP) + '.bak', 'Size': 1024},
    {'Key': None, 'Size': 1024},
    {'Key': object_key(APP, STAMP)},
])
def test_unusable_wrong_world_future_or_quarantine_objects_cannot_pass(item):
    assert check(page(item), now=NOW)['status'] == 'missing'


def test_pagination_and_unsorted_responses_preserve_latest_snapshot():
    pages = [page(stored('20261003T110000Z')), page(stored())]
    result = check(pages, now=NOW)
    assert result['status'] == 'fresh'
    assert result['age_minutes'] == 30
    assert result['key'].endswith(f'-{STAMP}.db')
    assert not result['key'].startswith('offhost/unvalidated-')


def test_newer_quarantine_cannot_hide_a_stale_validated_backup():
    result = check(page(stored('20261003T100000Z'), stored(quarantine=True)), now=NOW)
    assert result['status'] == 'stale'
    assert result['key'] == object_key(APP, '20261003T100000Z')


def test_exact_age_limit_is_fresh():
    result = check(page(stored('20261003T110000Z')), max_age_minutes=60, now=NOW)
    assert result['status'] == 'fresh'
    assert result['age_minutes'] == 60


def test_empty_listing_shapes_are_missing_and_garbage_is_rejected():
    assert check({'Prefix': 'offhost/'}, now=NOW)['status'] == 'missing'
    assert check({'KeyCount': 0}, now=NOW)['status'] == 'missing'
    with pytest.raises(ValueError):
        check({'error': 'forbidden'}, now=NOW)
    with pytest.raises(ValueError):
        check([], now=NOW)


def test_cli_missing_object_is_failure_and_malformed_response_is_unavailable(tmp_path):
    source = tmp_path / 'objects.json'
    script = Path(__file__).resolve().parents[1] / 'scripts/backup_health.py'
    for payload, expected in [({'object_pages': [{'Contents': []}]}, 1), ({'error': 'forbidden'}, 2)]:
        source.write_text(json.dumps(payload))
        result = subprocess.run([sys.executable, str(script), '--objects', str(source),
                                 '--app', APP], capture_output=True, text=True)
        assert result.returncode == expected


def test_invalid_age_limit_is_not_a_healthy_report():
    with pytest.raises(ValueError):
        check(page(stored()), max_age_minutes=0, now=NOW)


def _gate(tmp_path, **env):
    output, summary = tmp_path / 'output', tmp_path / 'summary'
    script = Path(__file__).resolve().parents[1] / 'scripts/backup_gate.sh'
    clean = {key: value for key, value in os.environ.items()
             if not key.startswith('ENFOLDED_BACKUP_') and key not in ('FLY_API_TOKEN', 'FLY_APP', 'BACKUP_REQUIRED')}
    result = subprocess.run(['bash', str(script)], env={**clean, **env,
        'GITHUB_OUTPUT': str(output), 'GITHUB_STEP_SUMMARY': str(summary)},
        capture_output=True, text=True)
    ready = output.read_text().strip() if output.exists() else ''
    summary_text = summary.read_text() if summary.exists() else ''
    return result, ready, summary_text


S3_READY = {
    'ENFOLDED_BACKUP_S3_ACCESS_KEY_ID': 'fixture-key',
    'ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY': 'fixture-secret-value',
    'ENFOLDED_BACKUP_S3_BUCKET': 'enfolded-backups',
    'ENFOLDED_BACKUP_S3_ENDPOINT': 'https://example.r2.cloudflarestorage.com',
    'ENFOLDED_BACKUP_S3_REGION': 'auto',
    'ENFOLDED_BACKUP_RETENTION_DAYS': '30',
    'FLY_APP': 'enfolded-beta',
}


@pytest.mark.parametrize('required,token,extra,expected,ready', [
    ('', '', {}, 0, 'ready=no'),
    ('false', '', {}, 0, 'ready=no'),
    ('true', '', {}, 1, ''),
    ('true', 'fixture-token', {}, 1, ''),
    ('true', 'fixture-token', S3_READY, 0, 'ready=yes'),
    ('false', 'fixture-token', S3_READY, 0, 'ready=yes'),
    ('false', 'fixture-token', {'ENFOLDED_BACKUP_S3_BUCKET': 'enfolded-backups'}, 0, 'ready=no'),
    ('tru', '', {}, 2, ''),
    ('tru', 'fixture-token', {}, 2, ''),
    ('TRUE', '', {}, 2, ''),
    ('0', '', {}, 2, ''),
])
def test_gate_requires_bucket_config_when_backup_is_required(tmp_path, required, token, extra, expected, ready):
    result, got, summary = _gate(tmp_path, BACKUP_REQUIRED=required, FLY_API_TOKEN=token, **extra)
    assert result.returncode == expected
    assert got == ready
    assert 'fixture-token' not in result.stdout + result.stderr
    assert 'fixture-secret-value' not in result.stdout + result.stderr + summary
    if got == 'ready=no':
        assert 'artifact' not in summary


@pytest.mark.parametrize('extra', [
    {'ENFOLDED_BACKUP_RETENTION_DAYS': 'thirty'},
    {'ENFOLDED_BACKUP_RETENTION_DAYS': '0'},
    {'ENFOLDED_BACKUP_RETENTION_DAYS': '3651'},
    {'ENFOLDED_BACKUP_S3_REGION': 'AUTO'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'http://example.r2.cloudflarestorage.com'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'https://user:secret@example.r2.cloudflarestorage.com'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'https://example.r2.cloudflarestorage.com/bucket'},
    {'ENFOLDED_BACKUP_S3_BUCKET': 'Bad_Name'},
    {'ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY': 'has space'},
    {'FLY_APP': '../enfolded'},
])
def test_gate_rejects_malformed_bucket_configuration(tmp_path, extra):
    result, ready, _summary = _gate(tmp_path, BACKUP_REQUIRED='false', FLY_API_TOKEN='',
                                    **{**S3_READY, **extra})
    assert result.returncode == 2
    assert ready == ''
    assert 'fixture-secret-value' not in result.stdout + result.stderr
    assert 'has space' not in result.stdout + result.stderr


def test_backup_workflow_never_publishes_a_github_artifact():
    text = (Path(__file__).resolve().parents[1] / '.github/workflows/backup.yml').read_text()
    assert 'uses: actions/upload-artifact' not in text
    assert 'upload-artifact@' not in text
    assert 'ENFOLDED_BACKUP_S3_BUCKET' in text
    assert 'ENFOLDED_BACKUP_S3_ENDPOINT' in text
    assert 'ENFOLDED_BACKUP_S3_ACCESS_KEY_ID' in text
    assert 'ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY' in text
    assert 'actions/checkout@11d5960a326750d5838078e36cf38b85af677262' in text
    assert "cron: '17,47 * * * *'" in text
