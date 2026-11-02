from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from scripts.backup_store import expired_keys, object_key

APP = 'enfolded-beta'
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'scripts/backup_store.py'
HEALTH = ROOT / 'scripts/backup_health.py'
ENDPOINT = 'https://example.r2.cloudflarestorage.com'
WRITE_SECRET = 'write-secret-value'
LIST_SECRET = 'list-secret-value'


def test_object_names_keep_the_app_and_snapshot_and_split_quarantine():
    assert object_key(APP, '20261003T113000Z') == (
        'offhost/worlds-backup-enfolded-beta-20261003T113000Z.db')
    assert object_key(APP, '20261003T113000Z', quarantine=True) == (
        'offhost/unvalidated-worlds-backup-enfolded-beta-20261003T113000Z.db')


def test_retention_uses_snapshot_time_and_keeps_other_names():
    pages = [{'Contents': [
        {'Key': object_key(APP, '20260903T120000Z'), 'Size': 4},
        {'Key': object_key(APP, '20260903T120001Z'), 'Size': 0},
        {'Key': object_key(APP, '20260902T120000Z', quarantine=True), 'Size': 4},
        {'Key': object_key(APP, '20261003T113000Z'), 'Size': 4},
        {'Key': object_key(APP, '20261103T120000Z'), 'Size': 4},
        {'Key': object_key('other-app', '20260901T000000Z'), 'Size': 4},
        {'Key': 'notes/keep.db', 'Size': 4},
    ]}]
    deleted = expired_keys(pages, app=APP, retention_days=30, now=NOW)
    assert deleted == [
        object_key(APP, '20260902T120000Z', quarantine=True),
        object_key(APP, '20260903T120000Z'),
    ]


def install_fake_aws(tmp_path, pages):
    calls = tmp_path / 'calls.jsonl'
    pages_path = tmp_path / 'pages.json'
    pages_path.write_text(json.dumps(pages))
    fake = tmp_path / 'aws'
    fake.write_text(f'#!{sys.executable}\n' + r'''
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
secret = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
access = os.environ.get('AWS_ACCESS_KEY_ID', '')
config = Path(os.environ['AWS_CONFIG_FILE']).read_text()
record = {
    'argv': argv,
    'region': os.environ.get('AWS_DEFAULT_REGION'),
    'checksum': os.environ.get('AWS_REQUEST_CHECKSUM_CALCULATION'),
    'response_checksum': os.environ.get('AWS_RESPONSE_CHECKSUM_VALIDATION'),
    'metadata_disabled': os.environ.get('AWS_EC2_METADATA_DISABLED'),
    'path_style': 'addressing_style = path' in config,
    'secret_in_argv': bool(secret) and secret in argv,
    'access_in_argv': bool(access) and access in argv,
    'access_key_id': access,
}
with open(os.environ['AWS_FAKE_CALLS'], 'a') as fh:
    fh.write(json.dumps(record) + '\n')
if 'get-object' in argv:
    Path(argv[-1]).write_bytes(b'sqlite-bytes')
if os.environ.get('AWS_FAKE_FAIL'):
    sys.stderr.write('boom ' + secret)
    sys.exit(1)
if 'list-objects-v2' in argv:
    pages = json.loads(Path(os.environ['AWS_FAKE_PAGES']).read_text())
    index = 1 if '--continuation-token' in argv else 0
    print(json.dumps(pages[index]))
else:
    print('{}')
''')
    fake.chmod(0o755)
    return calls


def bucket_env(tmp_path, calls, **extra):
    env = {key: value for key, value in os.environ.items() if not key.startswith('ENFOLDED_BACKUP_')
           and not key.startswith('AWS_')}
    env.update({
        'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
        'AWS_FAKE_CALLS': str(calls),
        'AWS_FAKE_PAGES': str(tmp_path / 'pages.json'),
        'ENFOLDED_BACKUP_S3_BUCKET': 'enfolded-backups',
        'ENFOLDED_BACKUP_S3_ENDPOINT': ENDPOINT,
        'ENFOLDED_BACKUP_S3_REGION': 'auto',
        'ENFOLDED_BACKUP_S3_ACCESS_KEY_ID': 'write-key',
        'ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY': WRITE_SECRET,
    })
    env.update(extra)
    return env


def run_store(tmp_path, args, pages, **extra):
    calls = install_fake_aws(tmp_path, pages)
    result = subprocess.run([sys.executable, str(STORE), *args],
                            capture_output=True, text=True, env=bucket_env(tmp_path, calls, **extra))
    recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    return result, recorded


def test_put_uploads_the_named_object_with_write_credentials_not_on_the_command_line(tmp_path):
    body = tmp_path / 'offhost.db'
    body.write_bytes(b'not-empty')
    result, recorded = run_store(tmp_path, [
        'put', '--app', APP, '--stamp', '20261003T113000Z', '--body', str(body)], [{'Contents': []}],
        ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID='list-key',
        ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY=LIST_SECRET)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == object_key(APP, '20261003T113000Z')
    assert recorded[0]['access_key_id'] == 'write-key'
    assert recorded[0]['secret_in_argv'] is False
    assert recorded[0]['path_style'] is True
    assert recorded[0]['region'] == 'auto'
    assert recorded[0]['checksum'] == 'when_required'
    assert recorded[0]['metadata_disabled'] == 'true'
    argv = recorded[0]['argv']
    assert argv[:4] == ['--endpoint-url', ENDPOINT, 's3api', 'put-object']
    assert '--key' in argv and object_key(APP, '20261003T113000Z') in argv
    assert WRITE_SECRET not in result.stdout + result.stderr
    assert LIST_SECRET not in json.dumps(recorded)


def test_quarantine_upload_and_empty_snapshot_never_call_the_store(tmp_path):
    body = tmp_path / 'offhost.db'
    body.write_bytes(b'not-empty')
    quarantined, recorded = run_store(tmp_path, [
        'put', '--app', APP, '--stamp', '20261003T113000Z', '--body', str(body), '--quarantine'],
        [{'Contents': []}])
    assert quarantined.returncode == 0, quarantined.stderr
    assert quarantined.stdout.strip() == object_key(APP, '20261003T113000Z', quarantine=True)
    assert recorded[0]['argv'].count(object_key(APP, '20261003T113000Z', quarantine=True)) == 1

    empty = tmp_path / 'empty.db'
    empty.write_bytes(b'')
    calls = tmp_path / 'unused.jsonl'
    refused = subprocess.run([sys.executable, str(STORE), 'put', '--app', APP,
                              '--stamp', '20261003T113000Z', '--body', str(empty)],
                             capture_output=True, text=True, env=bucket_env(tmp_path, calls))
    assert refused.returncode == 1
    assert not calls.exists()
    assert WRITE_SECRET not in refused.stdout + refused.stderr


def test_delete_refuses_a_foreign_key_and_delete_before_keeps_newer_objects(tmp_path):
    refused, recorded = run_store(tmp_path, ['delete', '--app', APP, '--key', 'notes/player.db'],
                                  [{'Contents': []}])
    assert refused.returncode == 1
    assert recorded == []
    assert 'notes/player.db' in refused.stderr

    older = object_key(APP, '20261003T090000Z')
    same = object_key(APP, '20261003T100000Z', quarantine=True)
    newer = object_key(APP, '20261003T113000Z')
    foreign = object_key('other-app', '20261003T080000Z')
    pages = [{'Contents': [{'Key': key, 'Size': 8} for key in (older, same, newer, foreign, 'notes/keep.db')]}]
    result, recorded = run_store(tmp_path, ['delete-before', '--app', APP, '--before', '20261003T100000Z'], pages)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [older, same]
    deleted = [call['argv'][call['argv'].index('--key') + 1] for call in recorded if 'delete-object' in call['argv']]
    assert deleted == [older, same]
    assert all(call['secret_in_argv'] is False for call in recorded)


def test_prune_deletes_only_this_apps_expired_objects(tmp_path):
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=31)).strftime('%Y%m%dT%H%M%SZ')
    fresh = (now - timedelta(minutes=5)).strftime('%Y%m%dT%H%M%SZ')
    old_key = object_key(APP, old, quarantine=True)
    fresh_key = object_key(APP, fresh)
    pages = [{'Contents': [
        {'Key': old_key, 'Size': 8},
        {'Key': fresh_key, 'Size': 8},
        {'Key': 'notes/keep.db', 'Size': 8},
    ]}]
    result, recorded = run_store(tmp_path, ['prune', '--app', APP, '--retention-days', '30'], pages)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == old_key
    deleted = [call['argv'][call['argv'].index('--key') + 1] for call in recorded if 'delete-object' in call['argv']]
    assert deleted == [old_key]
    listed = [call for call in recorded if 'list-objects-v2' in call['argv']]
    assert listed and listed[0]['argv'][listed[0]['argv'].index('--prefix') + 1] == 'offhost/'


def test_failed_download_redacts_the_secret_and_removes_the_partial_file(tmp_path):
    dest = tmp_path / 'restored.db'
    calls = install_fake_aws(tmp_path, [{'Contents': []}])
    env = bucket_env(tmp_path, calls, AWS_FAKE_FAIL='1')
    key = object_key(APP, '20261003T113000Z')
    result = subprocess.run([sys.executable, str(STORE), 'get', '--app', APP, '--key', key,
                             '--dest', str(dest)], capture_output=True, text=True, env=env)
    assert result.returncode == 1
    assert not dest.exists()
    assert WRITE_SECRET not in result.stdout + result.stderr
    assert '[redacted]' in result.stderr


def test_health_lists_with_the_read_only_credential_and_follows_the_continuation_token(tmp_path):
    fresh = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    pages = [
        {'Contents': [{'Key': object_key(APP, '20200101T000000Z'), 'Size': 8}],
         'IsTruncated': True, 'NextContinuationToken': 'page-2', 'Prefix': 'offhost/'},
        {'Contents': [{'Key': object_key(APP, fresh), 'Size': 8},
                      {'Key': object_key(APP, fresh, quarantine=True), 'Size': 8}],
         'IsTruncated': False, 'Prefix': 'offhost/'},
    ]
    calls = install_fake_aws(tmp_path, pages)
    env = bucket_env(tmp_path, calls,
                     ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID='list-key',
                     ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY=LIST_SECRET)
    result = subprocess.run([sys.executable, str(HEALTH), '--app', APP],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['status'] == 'fresh'
    assert report['key'] == object_key(APP, fresh)
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    assert [call['access_key_id'] for call in recorded] == ['list-key', 'list-key']
    assert '--continuation-token' in recorded[1]['argv']
    assert recorded[1]['argv'][recorded[1]['argv'].index('--continuation-token') + 1] == 'page-2'
    assert LIST_SECRET not in calls.read_text()
    assert WRITE_SECRET not in calls.read_text()
    assert 'upload-artifact' not in result.stdout
