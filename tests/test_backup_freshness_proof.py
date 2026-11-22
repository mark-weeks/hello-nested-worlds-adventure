"""The one-hour bound over a window, and the backup heartbeat ping gate.

Listings are fixtures. Nothing here contacts a bucket or a heartbeat host.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.backup_freshness_proof import prove, render_summary
from scripts.backup_store import object_key
from tests.test_backup_store import WRITE_SECRET, bucket_env, install_fake_aws

APP = 'enfolded-beta'
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
START = NOW - timedelta(days=1)
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'backup_freshness_proof.py'
TOKEN = 'heartbeat-token-secret'
HEARTBEAT_URL = f'https://monitor.example/ping/{TOKEN}'


def stamp(moment):
    return moment.strftime('%Y%m%dT%H%M%SZ')


def iso(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


def stored(moment, *, quarantine=False, size=1024, app=APP):
    return {'Key': object_key(app, stamp(moment), quarantine=quarantine), 'Size': size,
            'LastModified': '2020-01-01T00:00:00Z'}


def page(*items):
    return {'Prefix': 'offhost/', 'Contents': list(items)}


def series(start, stop, step=timedelta(minutes=30), omit=()):
    skipped = set(omit)
    items = []
    cursor = start
    while cursor <= stop:
        if cursor not in skipped:
            items.append(stored(cursor))
        cursor += step
    return items


def report_for(items, **kwargs):
    kwargs.setdefault('days', 1)
    kwargs.setdefault('now', NOW)
    return prove(page(*items), app=APP, **kwargs)


def test_a_tight_chain_across_the_window_passes():
    items = series(START, NOW)
    report = prove([page(*reversed(items[:10])), page(*reversed(items[10:]))],
                   app=APP, days=1, now=NOW)
    assert report['result'] == 'pass'
    assert report['count'] == len(items)
    assert report['window_days'] == 1
    assert report['max_gap_minutes'] == 60
    assert report['bound_seconds'] == 3600
    assert report['max_gap_seconds'] == 1800
    assert report['violations'] == []
    assert report['first']['snapshot_at'] == iso(START)
    assert report['last']['snapshot_at'] == iso(NOW)
    assert report['first']['key'] == object_key(APP, stamp(START))
    assert report['last']['key'] == object_key(APP, stamp(NOW))
    assert report['anchor'] is None
    summary = render_summary(report)
    assert summary.startswith('pass  ')
    assert f'count={len(items)}' in summary
    assert 'max_gap=30m00s' in summary
    assert object_key(APP, stamp(START)) in summary
    assert object_key(APP, stamp(NOW)) in summary


def test_a_gap_over_the_bound_fails_and_names_both_timestamps():
    hole_start = START + timedelta(hours=4)
    omitted = (hole_start + timedelta(minutes=30), hole_start + timedelta(hours=1))
    report = report_for(series(START, NOW, omit=omitted))
    assert report['result'] == 'fail'
    assert report['max_gap_seconds'] == 5400
    assert report['violations'] == [{
        'kind': 'successive',
        'from': iso(hole_start),
        'to': iso(hole_start + timedelta(hours=1, minutes=30)),
        'gap_seconds': 5400,
        'from_key': object_key(APP, stamp(hole_start)),
        'to_key': object_key(APP, stamp(hole_start + timedelta(hours=1, minutes=30))),
    }]
    summary = render_summary(report)
    assert summary.startswith('fail  ')
    assert f"{iso(hole_start)} -> {iso(hole_start + timedelta(hours=1, minutes=30))}" in summary
    assert '1h30m00s' in summary


def test_quarantine_empty_and_foreign_objects_do_not_fill_a_gap():
    hole_start = START + timedelta(hours=4)
    omitted = (hole_start + timedelta(minutes=30), hole_start + timedelta(hours=1))
    fillers = [
        stored(hole_start + timedelta(minutes=30), quarantine=True),
        stored(hole_start + timedelta(hours=1), size=0),
        stored(hole_start + timedelta(minutes=45), size=True),
        stored(hole_start + timedelta(minutes=50), app='enfolded-staging'),
        {'Key': 'notes/keep.db', 'Size': 1024},
    ]
    report = report_for([*series(START, NOW, omit=omitted), *fillers])
    assert report['result'] == 'fail'
    assert report['max_gap_seconds'] == 5400
    assert len(report['violations']) == 1
    dumped = json.dumps(report)
    assert 'unvalidated' not in dumped
    assert 'enfolded-staging' not in dumped
    assert 'notes/keep.db' not in dumped


def test_quarantine_beside_a_tight_chain_is_ignored():
    quarantine = stored(START + timedelta(minutes=15), quarantine=True)
    report = report_for([*series(START, NOW), quarantine])
    assert report['result'] == 'pass'
    assert 'unvalidated' not in json.dumps(report)
    assert quarantine['Key'] not in render_summary(report)


def test_empty_listing_fails_with_no_objects():
    for pages in ({'KeyCount': 0}, {'Prefix': 'offhost/'}, {'Contents': []}):
        report = prove(pages, app=APP, days=1, now=NOW)
        assert report['result'] == 'fail'
        assert report['count'] == 0
        assert report['first'] is None
        assert report['last'] is None
        assert report['anchor'] is None
        assert report['max_gap_seconds'] is None
        assert report['max_gap'] is None
        assert report['violations'] == [{
            'kind': 'window_start', 'from': None, 'to': iso(START),
            'gap_seconds': None, 'from_key': None, 'to_key': None,
        }]
    summary = render_summary(report)
    assert 'count=0' in summary
    assert 'first  none' in summary
    assert 'last   none' in summary
    assert f'uncovered window start: {iso(START)}' in summary
    with pytest.raises(ValueError):
        prove({'error': 'forbidden'}, app=APP, days=1, now=NOW)


def test_an_object_on_each_window_edge_is_included():
    report = report_for(series(START, NOW))
    assert report['first']['snapshot_at'] == iso(START)
    assert report['last']['snapshot_at'] == iso(NOW)
    assert report['result'] == 'pass'


def test_a_snapshot_one_second_before_the_window_is_the_anchor():
    anchor_at = START - timedelta(seconds=1)
    items = [stored(anchor_at), *series(START + timedelta(minutes=30), NOW)]
    report = report_for(items)
    assert report['result'] == 'pass'
    assert report['anchor']['snapshot_at'] == iso(anchor_at)
    assert report['anchor']['key'] not in (report['first']['key'],)
    assert report['first']['snapshot_at'] == iso(START + timedelta(minutes=30))
    assert report['count'] == len(items) - 1
    assert iso(anchor_at) in render_summary(report)


def test_a_gap_that_crosses_the_window_start_fails():
    anchor_at = START - timedelta(minutes=90)
    first = START + timedelta(minutes=10)
    report = report_for([stored(anchor_at), *series(first, NOW)])
    assert report['result'] == 'fail'
    assert report['violations'][0] == {
        'kind': 'successive',
        'from': iso(anchor_at),
        'to': iso(first),
        'gap_seconds': 100 * 60,
        'from_key': object_key(APP, stamp(anchor_at)),
        'to_key': object_key(APP, stamp(first)),
    }


def test_a_hole_entirely_before_the_window_does_not_fail_the_window():
    anchor_at = START - timedelta(minutes=30)
    older = stored(START - timedelta(hours=5))
    middle = stored(START - timedelta(hours=3))
    report = report_for([older, middle, stored(anchor_at), *series(START, NOW)])
    assert report['result'] == 'pass'
    assert report['anchor']['key'] == object_key(APP, stamp(anchor_at))
    assert older['Key'] not in json.dumps(report['violations'])
    assert middle['Key'] not in json.dumps(report['violations'])


def test_a_future_stamp_cannot_freshen_the_end_of_the_window():
    report = report_for([*series(START, NOW - timedelta(hours=2)), stored(NOW + timedelta(hours=1))])
    assert report['result'] == 'fail'
    assert report['last']['snapshot_at'] == iso(NOW - timedelta(hours=2))
    assert report['violations'][-1]['kind'] == 'window_end'
    assert stamp(NOW + timedelta(hours=1)) not in json.dumps(report)


def test_the_exact_bound_passes_and_one_extra_second_fails():
    on_the_hour = report_for(series(START, NOW - timedelta(hours=1)))
    assert on_the_hour['result'] == 'pass'
    assert on_the_hour['max_gap_seconds'] == 3600
    assert on_the_hour['max_gap']['kind'] == 'window_end'

    interior = report_for(series(START, NOW, omit=(START + timedelta(hours=4, minutes=30),)))
    assert interior['result'] == 'pass'
    assert interior['max_gap_seconds'] == 3600
    assert interior['violations'] == []

    early = NOW - timedelta(hours=1, seconds=1)
    items = [item for item in series(START, NOW - timedelta(hours=1))
             if item['Key'] != object_key(APP, stamp(NOW - timedelta(hours=1)))]
    items.append(stored(early))
    over = report_for(items)
    assert over['result'] == 'fail'
    closing = over['violations'][-1]
    assert closing['kind'] == 'window_end'
    assert closing['gap_seconds'] == 3601
    assert closing['from'] == iso(early)
    assert closing['to'] == iso(NOW)
    assert closing['to_key'] is None


def test_a_window_that_opens_with_no_snapshot_fails_even_when_later_gaps_are_short():
    report = report_for(series(START + timedelta(minutes=10), NOW))
    assert report['result'] == 'fail'
    assert report['anchor'] is None
    assert report['violations'][0]['kind'] == 'window_start'
    assert report['max_gap_seconds'] == 1800
    assert 'uncovered window start' in render_summary(report)


def _run(tmp_path, payload, *args, env_extra=None):
    source = tmp_path / 'listing.json'
    source.write_text(json.dumps(payload))
    marker = tmp_path / 'aws-called'
    if marker.exists():
        marker.unlink()
    bindir = tmp_path / 'bin'
    bindir.mkdir(exist_ok=True)
    aws = bindir / 'aws'
    aws.write_text('#!/bin/sh\necho called >> "$AWS_CALLED"\nexit 99\n')
    aws.chmod(0o755)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('ENFOLDED_BACKUP_') and not key.startswith('AWS_')}
    env.update({'PATH': str(bindir) + os.pathsep + os.environ.get('PATH', ''),
                'AWS_CALLED': str(marker)})
    if env_extra:
        env.update(env_extra)
    result = subprocess.run([sys.executable, str(SCRIPT), '--app', APP, '--objects', str(source), *args],
                            capture_output=True, text=True, env=env)
    called = marker.read_text() if marker.exists() else ''
    return result, called


def test_cli_reports_pass_fail_and_empty_without_calling_aws(tmp_path):
    passed, called = _run(tmp_path, page(*series(START, NOW)), '--days', '1', '--now', iso(NOW))
    assert passed.returncode == 0, passed.stderr
    assert called == ''
    body = json.loads(passed.stdout)
    assert body['result'] == 'pass'
    assert passed.stdout.endswith('\n')
    assert 'pass  ' in passed.stderr

    hole = START + timedelta(hours=4)
    failed, called = _run(
        tmp_path, page(*series(START, NOW, omit=(hole + timedelta(minutes=30), hole + timedelta(hours=1)))),
        '--days', '1', '--now', '20261122T120000Z')
    assert failed.returncode == 1
    assert called == ''
    assert json.loads(failed.stdout)['result'] == 'fail'
    assert iso(hole) in failed.stderr
    assert iso(hole + timedelta(hours=1, minutes=30)) in failed.stderr

    empty, _called = _run(tmp_path, {'object_pages': [{'KeyCount': 0}]}, '--days', '1', '--now', iso(NOW))
    assert empty.returncode == 1
    assert json.loads(empty.stdout)['count'] == 0
    assert 'first  none' in empty.stderr
    assert 'last   none' in empty.stderr


def test_cli_defaults_are_seven_days_and_sixty_minutes(tmp_path):
    result, called = _run(tmp_path, page(stored(NOW)), '--now', iso(NOW))
    assert result.returncode == 1
    assert called == ''
    report = json.loads(result.stdout)
    assert report['window_days'] == 7
    assert report['max_gap_minutes'] == 60
    assert report['window_start'] == '2026-11-15T12:00:00Z'
    assert report['window_end'] == iso(NOW)
    offset, _called = _run(tmp_path, page(stored(NOW)), '--now', '2026-11-22T12:00:00+00:00')
    assert offset.returncode == 1
    assert json.loads(offset.stdout)['window_end'] == iso(NOW)


def test_cli_rejects_a_live_clock_override_and_a_bad_listing(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), '--app', APP, '--now', iso(NOW)],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stdout == ''
    assert '--now' in result.stderr

    garbage, _called = _run(tmp_path, {'error': 'forbidden'}, '--now', iso(NOW))
    assert garbage.returncode == 2
    assert garbage.stdout == ''
    assert 'unavailable' in garbage.stderr

    for args in (('--days', '0'), ('--max-gap-minutes', '0'), ('--days', '367')):
        rejected, _called = _run(tmp_path, page(stored(NOW)), '--now', iso(NOW), *args)
        assert rejected.returncode == 2
        assert rejected.stdout == ''


def _live(tmp_path, pages, **extra):
    calls = install_fake_aws(tmp_path, pages)
    result = subprocess.run([sys.executable, str(SCRIPT), '--app', APP],
                            capture_output=True, text=True, env=bucket_env(tmp_path, calls, **extra))
    recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    return result, recorded


def test_a_live_proof_lists_with_the_read_pair_and_never_writes(tmp_path):
    result, recorded = _live(
        tmp_path, [{'KeyCount': 0}],
        ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID='list-key',
        ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY='list-secret-value')
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)['result'] == 'fail'
    assert [call['argv'][call['argv'].index('--prefix') + 1] for call in recorded] == [
        f'offhost/worlds-backup-{APP}-',
        f'offhost/unvalidated-worlds-backup-{APP}-',
    ]
    for call in recorded:
        assert 'list-objects-v2' in call['argv']
        assert 'put-object' not in call['argv']
        assert 'get-object' not in call['argv']
        assert 'delete-object' not in call['argv']
        assert 'delete-objects' not in call['argv']
        assert call['access_key_id'] == 'list-key'
        assert call['secret_in_argv'] is False
    assert 'list-secret-value' not in result.stdout + result.stderr
    assert WRITE_SECRET not in result.stdout + result.stderr


def test_a_live_proof_does_not_fall_back_to_the_write_key(tmp_path):
    missing, recorded = _live(tmp_path, [{'KeyCount': 0}])
    assert missing.returncode == 2
    assert missing.stdout == ''
    assert recorded == []
    assert 'not configured' in missing.stderr
    assert WRITE_SECRET not in missing.stdout + missing.stderr

    half, recorded = _live(tmp_path, [{'KeyCount': 0}],
                           ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID='list-key-half')
    assert half.returncode == 2
    assert recorded == []
    assert 'incomplete' in half.stderr
    assert 'list-key-half' not in half.stdout + half.stderr


def test_a_failed_listing_does_not_print_the_read_secret(tmp_path):
    result, recorded = _live(
        tmp_path, [{'KeyCount': 0}],
        ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID='list-key',
        ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY='list-secret-value',
        AWS_FAKE_FAIL='1')
    assert result.returncode == 2
    assert result.stdout == ''
    assert recorded
    assert 'list-secret-value' not in result.stdout + result.stderr
    assert WRITE_SECRET not in result.stdout + result.stderr
    assert 'example.r2.cloudflarestorage.com' not in result.stdout + result.stderr


def _heartbeat_script():
    from tests.test_backup_health import _workflow_step
    text = (ROOT / '.github' / 'workflows' / 'backup.yml').read_text()
    return _workflow_step(text, 'Ping the backup heartbeat')


def test_the_heartbeat_step_is_gated_on_a_validated_store():
    from tests.test_backup_health import _backup_workflow
    text, workflow = _backup_workflow()
    job = workflow['jobs']['backup']
    assert workflow['permissions'] == {'contents': 'read'}
    assert workflow['on']['workflow_dispatch'] is None
    assert workflow['on']['schedule'] == [{'cron': '17,47 * * * *'}]
    assert job['environment'] == {'name': 'backup', 'deployment': False}
    assert job['env']['ENFOLDED_BACKUP_RETENTION_DAYS'] == '30'
    assert 'ENFOLDED_BACKUP_HEARTBEAT_URL' not in job['env']
    names = [step.get('name') for step in job['steps']]
    store_at = names.index('Store the snapshot in the private bucket')
    ping_at = names.index('Ping the backup heartbeat')
    prune_at = names.index('Prune private-bucket objects past retention')
    assert ping_at == store_at + 1
    assert prune_at == ping_at + 1
    _identity, condition, script, step = _heartbeat_script()
    assert condition == "steps.validate.outcome == 'success' && steps.store.outcome == 'success'"
    assert 'always()' not in condition
    assert 'secrets.ENFOLDED_BACKUP_HEARTBEAT_URL' in step
    assert 'curl' in script
    assert text.count("cron: '17,47 * * * *'") == 1


def _ping(tmp_path, script, url, code='200'):
    log = tmp_path / 'curl.jsonl'
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    fake = bindir / 'curl'
    fake.write_text(f'#!{sys.executable}\n' + r'''
import json, os, sys
with open(os.environ['CURL_LOG'], 'a') as fh:
    fh.write(json.dumps(sys.argv) + '\n')
sys.stderr.write('stderr-leaked ' + sys.argv[-1] + '\n')
code = os.environ.get('CURL_FAKE_CODE', '200')
if code == 'missing':
    raise SystemExit(127)
print(code)
''')
    fake.chmod(0o755)
    summary = tmp_path / 'summary'
    env = {'PATH': str(bindir) + os.pathsep + '/usr/bin:/bin', 'CURL_LOG': str(log),
           'CURL_FAKE_CODE': code, 'GITHUB_STEP_SUMMARY': str(summary)}
    if url is not None:
        env['ENFOLDED_BACKUP_HEARTBEAT_URL'] = url
    result = subprocess.run(['bash', '--noprofile', '--norc', '-c', script],
                            capture_output=True, text=True, env=env)
    recorded = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    summary_text = summary.read_text() if summary.exists() else ''
    return result, recorded, summary_text


@pytest.mark.parametrize('url', [None, '', '   ', '\t'])
def test_an_unset_heartbeat_sends_nothing(tmp_path, url):
    _identity, _condition, script, _step = _heartbeat_script()
    result, recorded, summary = _ping(tmp_path, script, url)
    assert result.returncode == 0, result.stderr
    assert recorded == []
    assert summary.strip() == 'Backup heartbeat is unset; no ping was sent.'
    assert TOKEN not in result.stdout + result.stderr + summary


@pytest.mark.parametrize('code', ['200', '204'])
def test_a_successful_ping_posts_once_and_hides_the_url(tmp_path, code):
    _identity, _condition, script, _step = _heartbeat_script()
    result, recorded, summary = _ping(tmp_path, script, HEARTBEAT_URL, code)
    assert result.returncode == 0, result.stderr
    assert summary.strip() == 'Pinged the backup heartbeat.'
    assert len(recorded) == 1
    argv = recorded[0]
    assert argv[-1] == HEARTBEAT_URL
    assert argv[1] == '-q'
    assert 'POST' in argv
    assert '--max-redirs' in argv and argv[argv.index('--max-redirs') + 1] == '0'
    assert '--data-binary' in argv
    visible = result.stdout + result.stderr + summary
    assert TOKEN not in visible
    assert 'stderr-leaked' not in visible
    assert HEARTBEAT_URL not in visible


@pytest.mark.parametrize('code', ['302', '404', '500', '000', 'missing'])
def test_a_failed_ping_fails_the_step_without_printing_the_url(tmp_path, code):
    _identity, _condition, script, _step = _heartbeat_script()
    result, recorded, summary = _ping(tmp_path, script, HEARTBEAT_URL, code)
    assert result.returncode == 1
    assert 'Backup heartbeat ping failed.' in result.stderr
    assert 'Pinged the backup heartbeat.' not in summary
    assert TOKEN not in result.stdout + result.stderr + summary
    assert recorded


@pytest.mark.parametrize('url', [
    f'http://monitor.example/ping/{TOKEN}',
    f'https://monitor.example/bad {TOKEN}',
])
def test_a_non_https_heartbeat_url_is_refused_before_curl(tmp_path, url):
    _identity, _condition, script, _step = _heartbeat_script()
    result, recorded, summary = _ping(tmp_path, script, url)
    assert result.returncode == 1
    assert recorded == []
    assert 'https URL' in result.stderr
    assert TOKEN not in result.stdout + result.stderr + summary
