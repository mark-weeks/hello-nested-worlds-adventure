from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.backup_store import (
    MAX_LIST_PAGES, classify, expired_keys, get_object, list_object_pages, object_key, validate_endpoint,
)

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
    'aws_region': os.environ.get('AWS_REGION'),
    'session': os.environ.get('AWS_SESSION_TOKEN'),
    'profile': os.environ.get('AWS_PROFILE'),
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
    delay = os.environ.get('AWS_FAKE_SLEEP')
    if delay:
        import time
        time.sleep(float(delay))
if os.environ.get('AWS_FAKE_LEAK'):
    endpoint = argv[argv.index('--endpoint-url') + 1]
    host = endpoint.split('://', 1)[-1].split('/')[0]
    account = host.split('.')[0]
    sys.stderr.write(
        host.upper() + ' ' + account + ' offhost%2Fworlds-backup-enfolded-beta-secret.db boom ' + secret)
    sys.exit(1)
if os.environ.get('AWS_FAKE_FAIL'):
    endpoint = argv[argv.index('--endpoint-url') + 1]
    bucket = argv[argv.index('--bucket') + 1]
    key = argv[argv.index('--key') + 1] if '--key' in argv else 'offhost/worlds-backup-app.db'
    sys.stderr.write(f'SSL validation failed for {endpoint}/{bucket}/{key} boom {secret}')
    sys.exit(1)
if 'list-objects-v2' in argv:
    prefix = argv[argv.index('--prefix') + 1]
    if os.environ.get('AWS_FAKE_PAGE_COUNT'):
        total = int(os.environ['AWS_FAKE_PAGE_COUNT'])
        index = int(argv[argv.index('--continuation-token') + 1]) if '--continuation-token' in argv else 0
        last = index + 1 >= total
        body = {'Contents': [{'Key': prefix + '20200101T000000Z.db', 'Size': 8}],
                'IsTruncated': not last, 'Prefix': prefix}
        if not last:
            body['NextContinuationToken'] = str(index + 1)
        print(json.dumps(body))
    else:
        pages = json.loads(Path(os.environ['AWS_FAKE_PAGES']).read_text())
        if isinstance(pages, dict) and 'Contents' not in pages and 'IsTruncated' not in pages and 'KeyCount' not in pages:
            chosen = pages.get(prefix, [{'KeyCount': 0}])
        else:
            chosen = []
            for page in pages:
                contents = page.get('Contents') if isinstance(page, dict) else None
                if not isinstance(contents, list):
                    chosen.append(page)
                    continue
                matched = [item for item in contents
                           if isinstance(item, dict) and str(item.get('Key', '')).startswith(prefix)]
                copied = dict(page)
                copied['Contents'] = matched
                chosen.append(copied)
        if '--continuation-token' in argv:
            token = argv[argv.index('--continuation-token') + 1]
            index = int(token) if token.isdigit() else 1
        else:
            index = 0
        print(json.dumps(chosen[index] if index < len(chosen) else {'KeyCount': 0}))
elif os.environ.get('AWS_FAKE_DELETE_BODY'):
    print(os.environ['AWS_FAKE_DELETE_BODY'])
elif os.environ.get('AWS_FAKE_DELETE_ERRORS'):
    print(json.dumps({'Errors': [{'Key': 'offhost/worlds-backup-enfolded-beta-20200101T000000Z.db',
                                  'Code': 'AccessDenied', 'Message': 'no'}]}))
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


def test_quarantine_upload_uses_the_unvalidated_key_and_an_empty_snapshot_is_refused(tmp_path):
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


def deleted_keys(recorded):
    keys = []
    for call in recorded:
        argv = call['argv']
        if 'delete-objects' not in argv:
            continue
        payload = json.loads(argv[argv.index('--delete') + 1])
        keys.extend(item['Key'] for item in payload['Objects'])
    return keys


def test_delete_refuses_a_foreign_key_and_delete_before_keeps_newer_objects(tmp_path):
    refused, recorded = run_store(tmp_path, ['delete', '--app', APP, '--key', 'notes/player.db'],
                                  [{'Contents': []}])
    assert refused.returncode == 1
    assert recorded == []
    assert 'notes/player.db' not in refused.stderr
    assert "outside this app's backup names" in refused.stderr

    older = object_key(APP, '20261003T090000Z')
    same = object_key(APP, '20261003T100000Z', quarantine=True)
    newer = object_key(APP, '20261003T113000Z')
    foreign = object_key('other-app', '20261003T080000Z')
    pages = [{'Contents': [{'Key': key, 'Size': 8} for key in (older, same, newer, foreign, 'notes/keep.db')]}]
    result, recorded = run_store(tmp_path, ['delete-before', '--app', APP, '--before', '20261003T100000Z'], pages)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [older, same]
    assert deleted_keys(recorded) == [older, same]
    assert all('delete-object' not in call['argv'] for call in recorded)
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
    assert deleted_keys(recorded) == [old_key]
    listed = [call['argv'][call['argv'].index('--prefix') + 1]
              for call in recorded if 'list-objects-v2' in call['argv']]
    assert listed == [f'offhost/worlds-backup-{APP}-', f'offhost/unvalidated-worlds-backup-{APP}-']


def test_failed_download_redacts_the_secret_and_removes_the_partial_file(tmp_path):
    dest = tmp_path / 'restored.db'
    calls = install_fake_aws(tmp_path, [{'Contents': []}])
    env = bucket_env(tmp_path, calls, AWS_FAKE_FAIL='1')
    key = object_key(APP, '20261003T113000Z')
    result = subprocess.run([sys.executable, str(STORE), 'get', '--app', APP, '--key', key,
                             '--dest', str(dest)], capture_output=True, text=True, env=env)
    assert result.returncode == 1
    assert not dest.exists()
    combined = result.stdout + result.stderr
    assert WRITE_SECRET not in combined
    assert ENDPOINT not in combined
    assert 'enfolded-backups' not in combined
    assert key not in combined
    assert 'offhost/' not in combined
    assert '[redacted]' in result.stderr


def test_health_lists_with_the_read_only_credential_and_follows_the_continuation_token(tmp_path):
    fresh = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    validated = f'offhost/worlds-backup-{APP}-'
    quarantine = f'offhost/unvalidated-worlds-backup-{APP}-'
    pages = {
        validated: [
            {'Contents': [{'Key': object_key(APP, '20200101T000000Z'), 'Size': 8}],
             'IsTruncated': True, 'NextContinuationToken': 'page-2'},
            {'Contents': [{'Key': object_key(APP, fresh), 'Size': 8}],
             'IsTruncated': False},
        ],
        quarantine: [
            {'Contents': [{'Key': object_key(APP, fresh, quarantine=True), 'Size': 8}],
             'IsTruncated': False},
        ],
    }
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
    assert [call['access_key_id'] for call in recorded] == ['list-key', 'list-key', 'list-key']
    assert '--continuation-token' in recorded[1]['argv']
    assert recorded[1]['argv'][recorded[1]['argv'].index('--continuation-token') + 1] == 'page-2'
    assert recorded[0]['argv'][recorded[0]['argv'].index('--prefix') + 1] == validated
    assert LIST_SECRET not in calls.read_text()
    assert WRITE_SECRET not in calls.read_text()
    assert 'upload-artifact' not in result.stdout


def test_endpoint_rejects_a_port_that_is_not_a_number_in_range():
    for value in ('https://example.r2.cloudflarestorage.com:bad',
                  'https://example.r2.cloudflarestorage.com:65536',
                  'https://example.r2.cloudflarestorage.com:0',
                  'https://example.r2.cloudflarestorage.com:',
                  'https://h:'):
        try:
            validate_endpoint(value)
        except ValueError:
            continue
        raise AssertionError(value)
    validate_endpoint('https://example.r2.cloudflarestorage.com:443')


def test_retention_keeps_the_newest_validated_object_even_past_the_cutoff():
    old = object_key(APP, '20260801T120000Z')
    kept = object_key(APP, '20260903T120000Z')
    quarantine = object_key(APP, '20260903T120000Z', quarantine=True)
    future = object_key(APP, '20261103T120000Z')
    pages = [{'Contents': [
        {'Key': old, 'Size': 4},
        {'Key': kept, 'Size': 4},
        {'Key': quarantine, 'Size': 4},
        {'Key': future, 'Size': 4},
    ]}]
    assert expired_keys(pages, app=APP, retention_days=30, now=NOW) == [old, quarantine]
    alone = [{'Contents': [{'Key': kept, 'Size': 4}]}]
    assert expired_keys(alone, app=APP, retention_days=30, now=NOW) == []


def test_child_process_drops_ambient_aws_settings_and_uses_the_configured_region(tmp_path):
    body = tmp_path / 'offhost.db'
    body.write_bytes(b'not-empty')
    result, recorded = run_store(tmp_path, [
        'put', '--app', APP, '--stamp', '20261003T113000Z', '--body', str(body)], [{'Contents': []}],
        AWS_REGION='us-west-2', AWS_DEFAULT_REGION='eu-west-1',
        AWS_ACCESS_KEY_ID='ambient-key', AWS_SECRET_ACCESS_KEY='ambient-secret',
        AWS_SESSION_TOKEN='ambient-session', AWS_PROFILE='ambient-profile')
    assert result.returncode == 0, result.stderr
    seen = recorded[0]
    assert seen['aws_region'] == 'auto'
    assert seen['region'] == 'auto'
    assert seen['access_key_id'] == 'write-key'
    assert seen['session'] in (None, '')
    assert seen['profile'] in (None, '')
    blob = json.dumps(seen) + result.stdout + result.stderr
    assert 'ambient-secret' not in blob
    assert 'ambient-session' not in blob
    assert 'us-west-2' not in blob


def test_get_uses_the_write_key_when_a_list_key_is_also_set(tmp_path):
    dest = tmp_path / 'restored.db'
    key = object_key(APP, '20261003T113000Z')
    result, recorded = run_store(tmp_path, ['get', '--app', APP, '--key', key, '--dest', str(dest)],
                                 [{'Contents': []}],
                                 ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID='list-key',
                                 ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY=LIST_SECRET)
    assert result.returncode == 0, result.stderr
    assert dest.read_bytes() == b'sqlite-bytes'
    assert recorded[0]['access_key_id'] == 'write-key'
    assert LIST_SECRET not in json.dumps(recorded)


def test_prune_deletes_expired_keys_in_one_batch_and_keeps_the_newest(tmp_path):
    now = datetime.now(timezone.utc)
    oldest = object_key(APP, (now - timedelta(days=40)).strftime('%Y%m%dT%H%M%SZ'))
    middle = object_key(APP, (now - timedelta(days=35)).strftime('%Y%m%dT%H%M%SZ'), quarantine=True)
    kept = object_key(APP, (now - timedelta(days=31)).strftime('%Y%m%dT%H%M%SZ'))
    pages = [{'Contents': [
        {'Key': oldest, 'Size': 8},
        {'Key': middle, 'Size': 8},
        {'Key': kept, 'Size': 8},
    ]}]
    result, recorded = run_store(tmp_path, ['prune', '--app', APP, '--retention-days', '30'], pages)
    assert result.returncode == 0, result.stderr
    assert deleted_keys(recorded) == [oldest, middle]
    assert sum('delete-objects' in call['argv'] for call in recorded) == 1
    assert kept not in result.stdout


def test_prune_splits_a_thousand_deletes_and_a_refused_batch_hides_the_key(tmp_path):
    now = datetime.now(timezone.utc)
    base = now - timedelta(days=400)
    keys = [object_key(APP, (base + timedelta(minutes=index)).strftime('%Y%m%dT%H%M%SZ'), quarantine=True)
            for index in range(1001)]
    kept = object_key(APP, (now - timedelta(days=31)).strftime('%Y%m%dT%H%M%SZ'))
    contents = [{'Key': key, 'Size': 8} for key in keys]
    contents.append({'Key': kept, 'Size': 8})
    pages = [{'Contents': contents}]
    result, recorded = run_store(tmp_path, ['prune', '--app', APP, '--retention-days', '30'], pages)
    assert result.returncode == 0, result.stderr
    batches = [json.loads(call['argv'][call['argv'].index('--delete') + 1])
               for call in recorded if 'delete-objects' in call['argv']]
    assert [len(batch['Objects']) for batch in batches] == [1000, 1]
    assert kept not in result.stdout

    refused, recorded = run_store(tmp_path, ['delete', '--app', APP, '--key', keys[0]], [{'Contents': []}],
                                  AWS_FAKE_DELETE_ERRORS='1')
    assert refused.returncode == 1
    assert 'offhost/' not in refused.stderr
    assert keys[0] not in refused.stderr
    assert 'refused to delete 1' in refused.stderr


def test_listing_passes_one_hundred_pages_and_stops_at_the_cap(tmp_path):
    assert MAX_LIST_PAGES > 100
    assert MAX_LIST_PAGES * 1000 >= 3650 * 48
    calls = install_fake_aws(tmp_path, [])
    env = bucket_env(tmp_path, calls, AWS_FAKE_PAGE_COUNT='3')
    pages = list_object_pages(env, app=APP, max_pages=3)
    assert len(pages) == 6
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    assert len(recorded) == 6
    calls.write_text('')
    env['AWS_FAKE_PAGE_COUNT'] = '4'
    try:
        list_object_pages(env, app=APP, max_pages=3)
    except Exception as exc:
        assert 'did not finish' in str(exc)
    else:
        raise AssertionError('expected the page cap')
    recorded = [json.loads(line) for line in calls.read_text().splitlines() if line.strip()]
    assert len(recorded) == 3


def test_newer_quarantine_does_not_discard_an_expired_validated_copy():
    older = object_key(APP, '20260701T120000Z')
    kept = object_key(APP, '20260801T120000Z')
    quarantine = object_key(APP, '20261003T113000Z', quarantine=True)
    other = object_key('enfolded-staging', '20261003T115900Z')
    pages = [{'Contents': [
        {'Key': older, 'Size': 8},
        {'Key': kept, 'Size': 8},
        {'Key': quarantine, 'Size': 8},
        {'Key': other, 'Size': 8},
    ]}]
    assert expired_keys(pages, app=APP, retention_days=30, now=NOW) == [older]


def test_keep_newest_skips_an_empty_or_invalid_size():
    empty = object_key(APP, '20260903T120000Z')
    kept = object_key(APP, '20260801T120000Z')
    for size in (0, True, '8', None):
        pages = [{'Contents': [
            {'Key': kept, 'Size': 8},
            {'Key': empty, 'Size': size} if size is not None else {'Key': empty},
        ]}]
        assert expired_keys(pages, app=APP, retention_days=30, now=NOW) == [empty]


def test_delete_before_refuses_a_future_cutoff_and_keeps_the_newest(tmp_path):
    future, recorded = run_store(
        tmp_path, ['delete-before', '--app', APP, '--before', '20271102T000000Z', '--dry-run'],
        [{'Contents': [{'Key': object_key(APP, '20261001T000000Z'), 'Size': 8}]}])
    assert future.returncode == 1
    assert 'future' in future.stderr
    assert recorded == []
    assert 'Dry run' not in future.stderr

    older = object_key(APP, '20261001T000000Z')
    quarantine = object_key(APP, '20261015T000000Z', quarantine=True)
    kept = object_key(APP, '20261101T120000Z')
    pages = [{'Contents': [{'Key': key, 'Size': 8} for key in (older, quarantine, kept)]}]
    dry, recorded = run_store(tmp_path, [
        'delete-before', '--app', APP, '--after', '20261015T000000Z', '--before', '20261101T120000Z',
        '--dry-run'], pages)
    assert dry.returncode == 0, dry.stderr
    assert dry.stdout.split() == [quarantine]
    assert 'Dry run: nothing was deleted.' in dry.stderr
    assert deleted_keys(recorded) == []
    assert all('delete-objects' not in call['argv'] for call in recorded)

    removed, recorded = run_store(tmp_path, [
        'delete-before', '--app', APP, '--before', '20261101T120000Z'], pages)
    assert removed.returncode == 0, removed.stderr
    assert removed.stdout.split() == [older, quarantine]
    assert deleted_keys(recorded) == [older, quarantine]
    assert kept not in removed.stdout

    (tmp_path / 'calls.jsonl').unlink(missing_ok=True)
    backwards, recorded = run_store(tmp_path, [
        'delete-before', '--app', APP, '--after', '20261102T000000Z', '--before', '20261101T120000Z'],
        pages)
    assert backwards.returncode == 1
    assert 'lower bound' in backwards.stderr
    assert recorded == []


def test_get_timeout_removes_the_partial_and_a_finished_download_is_private(tmp_path):
    dest = tmp_path / 'restored.db'
    key = object_key(APP, '20261003T113000Z')
    timed, _recorded = run_store(
        tmp_path, ['get', '--app', APP, '--key', key, '--dest', str(dest)], [{'Contents': []}],
        AWS_FAKE_SLEEP='5', ENFOLDED_BACKUP_S3_TIMEOUT_SECONDS='1')
    assert timed.returncode == 1
    assert 'timed out' in timed.stderr
    assert not dest.exists()
    assert not Path(str(dest) + '.partial').exists()
    assert 'Traceback' not in timed.stderr

    finished, _recorded = run_store(
        tmp_path, ['get', '--app', APP, '--key', key, '--dest', str(dest)], [{'Contents': []}],
        ENFOLDED_BACKUP_S3_TIMEOUT_SECONDS='30')
    assert finished.returncode == 0, finished.stderr
    assert dest.read_bytes() == b'sqlite-bytes'
    assert dest.stat().st_mode & 0o777 == 0o600
    assert not Path(str(dest) + '.partial').exists()


def test_interrupted_get_removes_the_partial_file(tmp_path, monkeypatch):
    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr('scripts.backup_store.run_aws', interrupt)
    dest = tmp_path / 'restored.db'
    key = object_key(APP, '20261003T113000Z')
    env = {
        'ENFOLDED_BACKUP_S3_BUCKET': 'enfolded-backups',
        'ENFOLDED_BACKUP_S3_ENDPOINT': ENDPOINT,
        'ENFOLDED_BACKUP_S3_REGION': 'auto',
        'ENFOLDED_BACKUP_S3_ACCESS_KEY_ID': 'write-key',
        'ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY': WRITE_SECRET,
    }
    with pytest.raises(KeyboardInterrupt):
        get_object(APP, key, dest, env=env)
    assert not dest.exists()
    assert not (tmp_path / 'restored.db.partial').exists()


def test_failed_command_redacts_the_account_id_and_an_encoded_key(tmp_path):
    dest = tmp_path / 'restored.db'
    key = object_key(APP, '20261003T113000Z')
    result, _recorded = run_store(
        tmp_path, ['get', '--app', APP, '--key', key, '--dest', str(dest)], [{'Contents': []}],
        AWS_FAKE_LEAK='1')
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert 'EXAMPLE.R2.CLOUDFLARESTORAGE.COM' not in combined
    assert 'example' not in combined.lower()
    assert 'offhost%2F' not in combined
    assert 'offhost/' not in combined
    assert WRITE_SECRET not in combined
    assert '[redacted]' in result.stderr
    assert not dest.exists()


def test_half_set_read_pair_fails_closed(tmp_path):
    calls = install_fake_aws(tmp_path, [{'Contents': []}])
    env = bucket_env(tmp_path, calls, ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID='list-key-half')
    result = subprocess.run([sys.executable, str(HEALTH), '--app', APP],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 2
    assert 'incomplete' in result.stderr
    assert 'list-key-half' not in result.stdout + result.stderr
    assert not calls.exists()

    secret_only = bucket_env(tmp_path, calls, ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY=LIST_SECRET)
    refused, recorded = run_store(
        tmp_path, ['prune', '--app', APP, '--retention-days', '30'], [{'Contents': []}],
        ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY=LIST_SECRET)
    assert refused.returncode == 1
    assert 'incomplete' in refused.stderr
    assert LIST_SECRET not in refused.stdout + refused.stderr
    assert recorded == []
    assert secret_only['ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY'] == LIST_SECRET


@pytest.mark.parametrize('body', ['[]', 'null'])
def test_a_non_dict_delete_response_is_rejected(tmp_path, body):
    key = object_key(APP, '20261003T113000Z')
    result, _recorded = run_store(
        tmp_path, ['delete', '--app', APP, '--key', key], [{'Contents': []}],
        AWS_FAKE_DELETE_BODY=body)
    assert result.returncode == 1
    assert 'unexpected delete response' in result.stderr
    assert 'Traceback' not in result.stderr
    assert key not in result.stderr


def test_name_variants_are_not_this_apps_backup():
    named = object_key(APP, '20261003T113000Z')
    assert classify(named + ' ', APP) is None
    assert classify(named + '.bak', APP) is None
    assert classify('offhost%2Fworlds-backup-enfolded-beta-20261003T113000Z.db', APP) is None
    assert classify(named.replace('.db', '.DB'), APP) is None
    assert classify(named, APP)[0] == 'validated'
