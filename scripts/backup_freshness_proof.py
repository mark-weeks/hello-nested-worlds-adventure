"""Prove successive validated snapshot-start times meet the one-hour bound.

The check reads the off-host listing and never uploads, downloads, or deletes.
Live runs use the read-only list pair (ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID
and ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY). The write pair is not a
fallback. ``--objects`` reads a saved listing and does not contact the bucket.

A day is 24 hours. The window ends at ``--now`` for a saved listing, and at
the clock otherwise. Pass means every successive snapshot-start gap in that
window is within the bound (60 minutes unless ``--max-gap-minutes`` says
otherwise), a validated snapshot is already current at the window's start,
and the last snapshot-start is within the bound of the window's end.
Quarantine names, empty objects, other apps, and future stamps do not count.
Age is the stamp in the object name, not LastModified.

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
    taken, key, size = item
    return {'key': key, 'snapshot_at': _iso(taken), 'size_in_bytes': size}


def _gap(kind, start, end, start_key, end_key):
    raw = (end - start).total_seconds()
    if raw < 0:
        raise ValueError('Snapshot times are out of order.')
    return {'kind': kind, 'from': _iso(start), 'to': _iso(end), 'gap_seconds': _seconds(raw),
            'from_key': start_key, 'to_key': end_key, '_raw': raw}


def _public_gap(gap):
    return {key: value for key, value in gap.items() if key != '_raw'}


def prove(pages, *, app, days=7, max_gap_minutes=60, now=None):
    """Return the bound report for one app. Raises ValueError on a bad listing."""
    validate_app(app)
    if type(days) is not int or days < 1 or days > 366:
        raise ValueError('days must be an integer from 1 to 366.')
    if type(max_gap_minutes) is not int or max_gap_minutes <= 0:
        raise ValueError('max-gap-minutes must be a positive integer.')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware.')
    now = now.astimezone(timezone.utc)
    window_start = now - timedelta(days=days)
    bound = max_gap_minutes * 60
    found = {}
    for item in iter_objects(pages):
        classified = classify(item.get('Key'), app)
        size = item.get('Size')
        if classified is None or classified[0] != 'validated' or type(size) is not int or size <= 0:
            continue
        taken = classified[1]
        if taken > now:
            continue
        key = item['Key']
        if key not in found:
            found[key] = (taken, key, size)
    objects = sorted(found.values())
    in_window = [item for item in objects if item[0] >= window_start]
    before = [item for item in objects if item[0] < window_start]
    anchor = before[-1] if before else None
    measured = []
    uncovered = False
    if in_window:
        if in_window[0][0] > window_start:
            if anchor is None:
                uncovered = True
            else:
                measured.append(_gap('successive', anchor[0], in_window[0][0], anchor[1], in_window[0][1]))
        for earlier, later in zip(in_window, in_window[1:]):
            measured.append(_gap('successive', earlier[0], later[0], earlier[1], later[1]))
        last = in_window[-1]
        measured.append(_gap('window_end', last[0], now, last[1], None))
    elif anchor is not None:
        measured.append(_gap('window_end', anchor[0], now, anchor[1], None))
    else:
        uncovered = True
    violations = []
    if uncovered:
        violations.append({'kind': 'window_start', 'from': None, 'to': _iso(window_start),
                           'gap_seconds': None, 'from_key': None, 'to_key': None})
    for gap in measured:
        if gap['_raw'] > bound:
            violations.append(_public_gap(gap))
    widest = None
    for gap in measured:
        if widest is None or gap['_raw'] > widest['_raw']:
            widest = gap
    report = {
        'result': 'fail' if violations else 'pass',
        'app': app,
        'window_days': days,
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
    over = [item for item in report['violations'] if item['kind'] != 'window_start']
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
        lines.append(f"uncovered window start: {item['to']} has no validated snapshot within the bound")
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
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--max-gap-minutes', type=int, default=60)
    parser.add_argument('--objects', type=Path,
                        help='offline JSON: one ListObjectsV2 page, a list of pages, or {"object_pages": [...]}')
    parser.add_argument('--now', help='UTC window end for a saved listing, such as 2026-11-22T12:00:00Z')
    args = parser.parse_args()
    if args.now and args.objects is None:
        parser.exit(2, 'Pass --now only with --objects.\n')
    try:
        moment = parse_now(args.now) if args.now else None
        if args.objects:
            pages = load_object_pages(args.objects)
        else:
            pages = list_object_pages(listing_env(os.environ), app=args.app)
        report = prove(pages, app=args.app, days=args.days,
                       max_gap_minutes=args.max_gap_minutes, now=moment)
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
