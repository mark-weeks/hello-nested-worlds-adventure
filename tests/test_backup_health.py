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


def test_gate_names_a_missing_endpoint_on_its_own(tmp_path):
    without_endpoint = {key: value for key, value in S3_READY.items()
                        if key != 'ENFOLDED_BACKUP_S3_ENDPOINT'}
    inactive_dir = tmp_path / 'inactive'
    required_dir = tmp_path / 'required'
    inactive_dir.mkdir()
    required_dir.mkdir()
    inactive, ready, summary = _gate(inactive_dir, BACKUP_REQUIRED='false', FLY_API_TOKEN='fixture-token',
                                     **without_endpoint)
    assert inactive.returncode == 0
    assert ready == 'ready=no'
    assert 'ENFOLDED_BACKUP_S3_ENDPOINT' in summary
    assert 'artifact' not in summary
    required, ready, _summary = _gate(required_dir, BACKUP_REQUIRED='true', FLY_API_TOKEN='fixture-token',
                                      **without_endpoint)
    assert required.returncode == 1
    assert ready == ''
    assert 'ENFOLDED_BACKUP_S3_ENDPOINT' in required.stderr


@pytest.mark.parametrize('extra', [
    {'ENFOLDED_BACKUP_RETENTION_DAYS': 'thirty'},
    {'ENFOLDED_BACKUP_RETENTION_DAYS': '0'},
    {'ENFOLDED_BACKUP_RETENTION_DAYS': '3651'},
    {'ENFOLDED_BACKUP_S3_REGION': 'AUTO'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'http://example.r2.cloudflarestorage.com'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'https://user:secret@example.r2.cloudflarestorage.com'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'https://example.r2.cloudflarestorage.com/bucket'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'https://example.r2.cloudflarestorage.com:bad'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'https://example.r2.cloudflarestorage.com:65536'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'https://example.r2.cloudflarestorage.com:0'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'https://example.r2.cloudflarestorage.com:'},
    {'ENFOLDED_BACKUP_S3_ENDPOINT': 'https://h:'},
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


def _workflow_step(text, step_name):
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines)
                 if line.strip() == f'- name: {step_name}')
    block = []
    for line in lines[start:]:
        if block and line.startswith('      - '):
            break
        block.append(line)
    step = '\n'.join(block)
    identity = next((line.split(':', 1)[1].strip() for line in block if line.strip().startswith('id:')), '')
    condition = next((line.split(':', 1)[1].strip() for line in block if line.strip().startswith('if:')), '')
    run_lines = []
    in_run = False
    for line in block:
        if not in_run:
            if line.strip() == 'run: |':
                in_run = True
            continue
        if line.startswith('          '):
            run_lines.append(line[10:])
        elif line.strip() == '':
            run_lines.append('')
        else:
            break
    return identity, condition, '\n'.join(run_lines) + '\n', step


def test_backup_workflow_never_publishes_a_github_artifact():
    text = (Path(__file__).resolve().parents[1] / '.github/workflows/backup.yml').read_text()
    assert 'uses: actions/upload-artifact' not in text
    assert 'upload-artifact@' not in text
    assert 'secrets.ENFOLDED_BACKUP_S3_BUCKET' in text
    assert 'secrets.ENFOLDED_BACKUP_S3_ENDPOINT' in text
    assert 'vars.ENFOLDED_BACKUP_S3_BUCKET' not in text
    assert 'vars.ENFOLDED_BACKUP_S3_ENDPOINT' not in text
    assert 'ENFOLDED_BACKUP_S3_ACCESS_KEY_ID' in text
    assert 'ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY' in text
    assert 'persist-credentials: false' in text
    assert 'version: 0.5.1' in text
    assert 'actions/checkout@11d5960a326750d5838078e36cf38b85af677262' in text
    assert "cron: '17,47 * * * *'" in text
    assert 'curl -fsSL --retry 5 --retry-all-errors --connect-timeout 20 --max-time 300' in text
    assert '# Example only; Mark has not chosen a retention (ADR-034 §5).' in text
    gate = (Path(__file__).resolve().parents[1] / 'scripts/backup_gate.sh').read_text()
    assert '# Example only; Mark has not chosen a retention (ADR-034 §5).' in gate
    store_id, store_if, _store_run, store_step = _workflow_step(text, 'Store the snapshot in the private bucket')
    _prune_id, prune_if, _prune_run, _prune_step = _workflow_step(text, 'Prune private-bucket objects past retention')
    assert store_id == 'store'
    assert store_if == "always() && steps.download.outcome == 'success' && steps.aws.outcome == 'success'"
    assert prune_if == "always() && steps.store.outcome == 'success'"
    assert 'VALIDATE_OUTCOME: ${{ steps.validate.outcome }}' in store_step


def test_store_step_quarantines_unless_validation_succeeded(tmp_path):
    text = (Path(__file__).resolve().parents[1] / '.github/workflows/backup.yml').read_text()
    _store_id, _store_if, script, _store_step = _workflow_step(text, 'Store the snapshot in the private bucket')
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    recorder = tmp_path / 'argv.jsonl'
    fake = fake_bin / 'python3'
    fake.write_text(f'#!{sys.executable}\n' + r'''
import json, os, sys
with open(os.environ['ARGV_LOG'], 'a') as fh:
    fh.write(json.dumps(sys.argv) + '\n')
print('offhost/worlds-backup-should-not-be-logged')
''')
    fake.chmod(0o755)
    for outcome, quarantined, summary_line in (
            ('success', False, 'Stored a validated snapshot.'),
            ('failure', True, 'Stored a quarantine snapshot.'),
            ('cancelled', True, 'Stored a quarantine snapshot.')):
        recorder.write_text('')
        summary = tmp_path / f'summary-{outcome}'
        result = subprocess.run(['bash', '-c', script], capture_output=True, text=True, env={
            'PATH': str(fake_bin) + os.pathsep + '/usr/bin:/bin',
            'ARGV_LOG': str(recorder),
            'FLY_APP': 'enfolded-beta',
            'STAMP': '20261003T113000Z',
            'VALIDATE_OUTCOME': outcome,
            'GITHUB_STEP_SUMMARY': str(summary),
        })
        assert result.returncode == 0, result.stderr
        argv = json.loads(recorder.read_text().strip())
        assert argv[1:5] == ['scripts/backup_store.py', 'put', '--app', 'enfolded-beta']
        assert ('--quarantine' in argv) is quarantined
        assert 'offhost/' not in result.stdout + result.stderr
        assert summary.read_text().strip() == summary_line
