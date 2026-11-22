"""Prove the newest validated snapshot stayed inside the one-hour bound.

The check reads the off-host listing and never uploads, downloads, or deletes.
Live runs use the read-only list pair (ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID
and ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY). The write pair is not a
fallback. ``--objects`` reads a saved listing and does not contact the bucket.

A day is 24 hours. The window ends at ``--now`` for a saved listing, and at
the clock otherwise. Age is the snapshot-start in the object name. The
upload time is ``LastModified``. S3-compatible stores set that at about the
start of the PUT, so each landing gap undercounts by that upload's duration.
Pass means that, throughout the window, the newest validated object already
in the bucket was never more than the bound old (60 minutes unless
``--max-gap-minutes`` says otherwise). That holds when an object is already
in the bucket at the window's start, each later object lands within the
bound of the previous snapshot-start, and the last snapshot-start is within
the bound of the window's end. A missing upload time, or one before the
snapshot-start, cannot support a pass. An upload time after the window end
means the object was not yet available. ``--from-first`` starts at the first
validated object and requires two of them. ``--since`` ignores objects
before a UTC instant and then does the same, so a manual snapshot from
before the dispatcher does not stay in the production check. Quarantine
names, empty objects, other apps, and future stamps do not count.

JSON goes to stdout. A short summary goes to stderr. Exit 0 passes, 1 fails
the bound, and 2 means the listing or the credentials could not be read.
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backup_store import (
    StoreError, classify, iter_objects, list_object_pages, load_object_pages, validate_app,
    validate_stamp,
)

_WRITE_CREDENTIALS = (
    'ENFOLDED_BACKUP_S3_ACCESS_KEY_ID',
    'ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY',
)


def _iso(moment):
    moment = moment.astimezone(timezone.utc)
    if moment.microsecond:
        return moment.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


def _seconds(raw):
    whole = int(raw)
    if raw == whole:
        return whole
    return round(raw, 3)


def _ref(item):
    taken, arrived, key, size = item
    return {'key': key, 'snapshot_at': _iso(taken), 'arrived_at': _iso(arrived),
            'size_in_bytes': size}


def _parse_arrived(value):
    """UTC upload time, or None when the listing does not prove one."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith('+00:00'):
        text = text[:-6] + 'Z'
    if not text.endswith('Z'):
        return None
    body = text[:-1]
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
        try:
            return datetime.strptime(body, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _gap(kind, start, end, start_key, end_key):
    raw = (end - start).total_seconds()
    if raw < 0:
        raise ValueError('Snapshot times are out of order.')
    return {'kind': kind, 'from': _iso(start), 'to': _iso(end), 'gap_seconds': _seconds(raw),
            'from_key': start_key, 'to_key': end_key, '_raw': raw}


def _public_gap(gap):
    return {key: value for key, value in gap.items() if key != '_raw'}


def _arrival_violation(taken, key, arrived):
    return {'kind': 'arrival', 'from': _iso(taken),
            'to': None if arrived is None else _iso(arrived),
            'gap_seconds': None, 'from_key': key, 'to_key': None}


def prove(pages, *, app, days=7, max_gap_minutes=60, now=None, from_first=False, since=None):
    """Return the bound report for one app. Raises ValueError on a bad listing."""
    validate_app(app)
    if type(days) is not int or days < 1 or days > 366:
        raise ValueError('days must be an integer from 1 to 366.')
    if type(max_gap_minutes) is not int or max_gap_minutes <= 0:
        raise ValueError('max-gap-minutes must be a positive integer.')
    if type(from_first) is not bool:
        raise ValueError('from_first must be true or false.')
    if since is not None and (not isinstance(since, datetime) or since.tzinfo is None):
        raise ValueError('since must be a timezone-aware UTC time.')
    if from_first and since is not None:
        raise ValueError('Pass either from_first or since, not both.')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware.')
    now = now.astimezone(timezone.utc)
    if since is not None:
        since = since.astimezone(timezone.utc)
        if since > now:
            raise ValueError('since must not be after the window end.')
    bound = max_gap_minutes * 60
    bounded = from_first or since is not None
    found = {}
    arrival_violations = []
    seen = set()
    for item in iter_objects(pages):
        classified = classify(item.get('Key'), app)
        size = item.get('Size')
        if classified is None or classified[0] != 'validated' or type(size) is not int or size <= 0:
            continue
        taken = classified[1]
        if taken > now:
            continue
        key = item['Key']
        if key in seen:
            continue
        seen.add(key)
        if since is not None and taken < since:
            continue
        arrived = _parse_arrived(item.get('LastModified'))
        if arrived is not None and arrived > now:
            continue
        if arrived is None or arrived < taken:
            arrival_violations.append((taken, _arrival_violation(taken, key, arrived)))
            continue
        found[key] = (taken, arrived, key, size)
    objects = sorted(found.values())
    if since is not None:
        window_start = since
    elif from_first:
        window_start = objects[0][0] if objects else now
    else:
        window_start = now - timedelta(days=days)
    in_window = [item for item in objects if item[0] >= window_start]
    cover = None
    for item in objects:
        if item[1] <= window_start and (cover is None or item[0] > cover[0]):
            cover = item
    measured = []
    uncovered = False
    if not bounded:
        if cover is None:
            uncovered = True
        else:
            measured.append(_gap('window_start', cover[0], window_start, cover[2], None))
    newest = cover
    later = sorted((item for item in objects if item[1] > window_start), key=lambda item: (item[1], item[0]))
    for item in later:
        if newest is not None and item[0] < newest[0]:
            continue
        if newest is None:
            measured.append(_gap('successive', item[0], item[1], item[2], item[2]))
            newest = item
            continue
        measured.append(_gap('successive', newest[0], item[1], newest[2], item[2]))
        newest = item
    if newest is not None:
        measured.append(_gap('window_end', newest[0], now, newest[2], None))
    elif not bounded:
        uncovered = True
    violations = []
    if bounded and len(objects) < 2:
        only = objects[0] if objects else None
        violations.append({'kind': 'count', 'from': None if only is None else _iso(only[0]),
                           'to': None, 'gap_seconds': None,
                           'from_key': None if only is None else only[2], 'to_key': None})
    if uncovered:
        violations.append({'kind': 'window_start', 'from': None, 'to': _iso(window_start),
                           'gap_seconds': None, 'from_key': None, 'to_key': None})
    for gap in measured:
        if gap['kind'] == 'window_start' and not uncovered and gap['_raw'] > bound:
            violations.append(_public_gap(gap))
        elif gap['kind'] != 'window_start' and gap['_raw'] > bound:
            violations.append(_public_gap(gap))
    for taken, violation in sorted(arrival_violations):
        if bounded or taken >= window_start:
            violations.append(violation)
    widest = None
    for gap in measured:
        if widest is None or gap['_raw'] > widest['_raw']:
            widest = gap
    before = [item for item in objects if item[0] < window_start]
    anchor = before[-1] if before and not bounded else None
    report = {
        'result': 'fail' if violations else 'pass',
        'app': app,
        'window_days': None if bounded else days,
        'from_first': from_first,
        'since': None if since is None else _iso(since),
        'max_gap_minutes': max_gap_minutes,
        'bound_seconds': bound,
        'window_start': _iso(window_start),
        'window_end': _iso(now),
        'count': len(in_window),
        'first': _ref(in_window[0]) if in_window else None,
        'last': _ref(in_window[-1]) if in_window else None,
        'anchor': _ref(anchor) if anchor is not None else None,
        'max_gap_seconds': None if widest is None else widest['gap_seconds'],
        'max_gap': None if widest is None else _public_gap(widest),
        'violations': violations,
    }
    return report


def format_gap(seconds):
    if seconds is None:
        return 'none'
    whole = int(round(seconds))
    hours, remainder = divmod(abs(whole), 3600)
    minutes, secs = divmod(remainder, 60)
    body = f'{hours}h{minutes:02d}m{secs:02d}s' if hours else f'{minutes}m{secs:02d}s'
    return f'-{body}' if whole < 0 else body


def render_summary(report):
    """One short text report. Timestamps are UTC. Object keys are the names."""
    lines = [
        f"{report['result']}  app={report['app']}  count={report['count']}  "
        f"max_gap={format_gap(report['max_gap_seconds'])}  "
        f"bound={report['max_gap_minutes']}m  "
        f"window={report['window_start']}..{report['window_end']}",
    ]
    widest = report['max_gap']
    if widest is not None:
        lines.append(
            f"max_gap  {widest['from']} -> {widest['to']}  ({format_gap(widest['gap_seconds'])})")
    over = [item for item in report['violations'] if item['kind'] in ('successive', 'window_end')]
    uncovered = [item for item in report['violations'] if item['kind'] == 'window_start']
    if over:
        lines.append('gaps over the bound:')
        for item in over:
            if item['kind'] == 'window_end':
                lines.append(
                    f"  {item['from']} -> window end {item['to']}  ({format_gap(item['gap_seconds'])})")
            else:
                lines.append(
                    f"  {item['from']} -> {item['to']}  ({format_gap(item['gap_seconds'])})")
    for item in uncovered:
        if item['gap_seconds'] is None:
            lines.append(
                f"uncovered window start: {item['to']} has no validated snapshot within the bound")
        else:
            lines.append(
                f"uncovered window start: {item['from']} -> {item['to']}  "
                f"({format_gap(item['gap_seconds'])})")
    for item in report['violations']:
        if item['kind'] == 'arrival':
            lines.append(f"missing arrival time: {item['from']}  {item['from_key']}")
        elif item['kind'] == 'count':
            lines.append('fewer than two validated snapshots')
    first = report['first']
    last = report['last']
    lines.append('first  none' if first is None else f"first  {first['snapshot_at']}  {first['key']}")
    lines.append('last   none' if last is None else f"last   {last['snapshot_at']}  {last['key']}")
    anchor = report['anchor']
    if anchor is not None:
        lines.append(f"anchor  {anchor['snapshot_at']}  {anchor['key']}")
    return '\n'.join(lines) + '\n'


def listing_env(env):
    """Env for a list-only call. The write pair is removed so it cannot be used."""
    list_id = env.get('ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID', '')
    list_secret = env.get('ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY', '')
    if bool(list_id) != bool(list_secret):
        raise StoreError('A backup read credential is incomplete. Set both read variables or neither.')
    if not list_id or not list_secret:
        raise StoreError(
            'Read-only backup list credentials are not configured. '
            'Set both ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID and '
            'ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY.')
    cleaned = dict(env)
    for name in _WRITE_CREDENTIALS:
        cleaned.pop(name, None)
    return cleaned


def parse_now(value):
    if not isinstance(value, str):
        raise ValueError('now must be UTC, such as 2026-11-22T12:00:00Z.')
    text = value.strip()
    if text.endswith('+00:00'):
        text = text[:-6] + 'Z'
    if len(text) == 16 and text.endswith('Z'):
        return validate_stamp(text)
    if not text.endswith('Z'):
        raise ValueError('now must be UTC, such as 2026-11-22T12:00:00Z.')
    body = text[:-1]
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
        try:
            return datetime.strptime(body, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError('now must be UTC, such as 2026-11-22T12:00:00Z.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', required=True)
    parser.add_argument('--days', type=int, default=None)
    parser.add_argument('--from-first', action='store_true',
                        help='start at the first validated object and require at least two')
    parser.add_argument('--since',
                        help='UTC instant; ignore earlier objects and require at least two after it')
    parser.add_argument('--max-gap-minutes', type=int, default=60)
    parser.add_argument('--objects', type=Path,
                        help='offline JSON: one ListObjectsV2 page, a list of pages, or {"object_pages": [...]}')
    parser.add_argument('--now', help='UTC window end for a saved listing, such as 2026-11-22T12:00:00Z')
    args = parser.parse_args()
    if args.now and args.objects is None:
        parser.exit(2, 'Pass --now only with --objects.\n')
    try:
        chosen = [name for name, selected in (
            ('--from-first', args.from_first), ('--days', args.days is not None),
            ('--since', args.since is not None)) if selected]
        if len(chosen) > 1:
            parser.exit(2, 'Pass only one of --from-first, --days, or --since.\n')
        moment = parse_now(args.now) if args.now else None
        since = parse_now(args.since) if args.since else None
        if args.objects:
            pages = load_object_pages(args.objects)
        else:
            pages = list_object_pages(listing_env(os.environ), app=args.app)
        report = prove(pages, app=args.app, days=7 if args.days is None else args.days,
                       max_gap_minutes=args.max_gap_minutes, now=moment,
                       from_first=args.from_first, since=since)
    except StoreError as exc:
        parser.exit(2, f'Backup bound proof unavailable: {exc}\n')
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        parser.exit(2, 'Backup bound proof unavailable: check input and bucket read access.\n')
    sys.stdout.write(json.dumps(report, indent=2) + '\n')
    sys.stderr.write(render_summary(report))
    if report['result'] != 'pass':
        sys.exit(1)


if __name__ == '__main__':
    main()
