"""Prove the newest validated snapshot stayed inside the one-hour bound.

The check reads the off-host listing and never uploads, downloads, or deletes.
Live runs use the read-only list pair (ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID
and ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY). The write pair is not a
fallback. ``--objects`` reads a saved listing and does not contact the bucket.

A day is 24 hours. The window ends at ``--now`` for a saved listing, and at
the clock otherwise. Age is the snapshot-start in the object name. The
finish evidence is the ``LastModified`` of the ``.ready`` marker written
after that snapshot's PUT returned. That time is later than the moment the
snapshot became readable, so a landing measured to it is an upper bound.
``LastModified`` on the snapshot itself is about when its PUT started. It
can prove a breach. It cannot prove a pass. A missing marker withholds
certification only when the bound depends on that object. A marker past
the bound is ``unresolved`` while the snapshot's own upload time is still
inside it, and a confirmed breach requires that upload time to be late.
Pass means an object was provably already in the bucket at the window's
start, each later marker the bound depends on is within the bound of the
previous snapshot-start, and the last snapshot-start is within the bound
of the window's end (60 minutes unless ``--max-gap-minutes`` says
otherwise).
``--from-first`` starts at the first validated object and requires two.
``--since`` ignores objects before a UTC instant. The measured interval
then starts at the first snapshot-start that remains. Quarantine names,
empty objects, other apps, and future stamps do not count.

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
    StoreError, classify, classify_ready, iter_objects, list_object_pages, load_object_pages,
    validate_app, validate_stamp,
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
    arrived = item['arrived']
    return {'key': item['key'], 'snapshot_at': _iso(item['taken']),
            'arrived_at': None if arrived is None else _iso(arrived),
            'size_in_bytes': item['size']}


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
    snapshots = {}
    markers = {}
    arrival_violations = []
    for item in iter_objects(pages):
        key = item.get('Key')
        size = item.get('Size')
        ready_at = classify_ready(key, app)
        if ready_at is not None:
            if type(size) is not int or size <= 0 or ready_at > now:
                continue
            if since is not None and ready_at < since:
                continue
            arrived = _parse_arrived(item.get('LastModified'))
            if arrived is None or arrived < ready_at or arrived > now:
                continue
            markers.setdefault(ready_at, []).append(arrived)
            continue
        classified = classify(key, app)
        if classified is None or classified[0] != 'validated' or type(size) is not int or size <= 0:
            continue
        taken = classified[1]
        if taken > now or key in snapshots:
            continue
        if since is not None and taken < since:
            continue
        lower = _parse_arrived(item.get('LastModified'))
        if lower is not None and lower > now:
            continue
        if lower is not None and lower < taken:
            arrival_violations.append((taken, _arrival_violation(taken, key, lower)))
            continue
        snapshots[key] = {'taken': taken, 'key': key, 'size': size, 'lower': lower}
    objects = []
    for snap in snapshots.values():
        candidates = [moment for moment in markers.get(snap['taken'], [])
                      if snap['lower'] is None or moment >= snap['lower']]
        snap['upper'] = min(candidates) if candidates else None
        snap['arrived'] = snap['upper'] if snap['upper'] is not None else snap['lower']
        if snap['upper'] is None and snap['lower'] is None:
            arrival_violations.append((snap['taken'], _arrival_violation(snap['taken'], snap['key'], None)))
            continue
        objects.append(snap)
    objects.sort(key=lambda snap: (snap['taken'], snap['key']))
    if since is not None:
        window_start = objects[0]['taken'] if objects else since
    elif from_first:
        window_start = objects[0]['taken'] if objects else now
    else:
        window_start = now - timedelta(days=days)
    in_window = [item for item in objects if item['taken'] >= window_start]
    cover = None
    for item in objects:
        if item['upper'] is not None and item['upper'] <= window_start and (
                cover is None or item['taken'] > cover['taken']):
            cover = item
    measured = []
    unresolved = []
    uncovered = False
    if not bounded:
        if cover is None:
            possible = [item for item in objects if item['taken'] <= window_start and (
                item['lower'] is None or item['lower'] <= window_start)]
            if possible:
                unresolved.append({'kind': 'unresolved', 'from': None, 'to': _iso(window_start),
                                   'gap_seconds': None, 'from_key': None, 'to_key': None})
            else:
                uncovered = True
        else:
            measured.append(_gap('window_start', cover['taken'], window_start, cover['key'], None))

    def _later_marker_covers(origin, snap):
        """A later finish marker already keeps this origin inside the bound."""
        for nxt in pending:
            if nxt['taken'] <= snap['taken'] or nxt['upper'] is None:
                continue
            if (nxt['upper'] - origin).total_seconds() <= bound:
                return True
        return False

    def _unproven(origin, origin_key, snap, moment):
        unresolved.append({
            'kind': 'unresolved', 'from': _iso(origin),
            'to': None if moment is None else _iso(moment),
            'gap_seconds': None if moment is None else _seconds((moment - origin).total_seconds()),
            'from_key': origin_key, 'to_key': snap['key'],
        })

    violations = []
    if not bounded and cover is not None:
        pending = [item for item in objects if item['taken'] > cover['taken']]
        previous = cover
    else:
        pending = list(objects) if bounded else [
            item for item in objects if item['taken'] >= window_start]
        previous = None
    for item in pending:
        origin = item['taken'] if previous is None else previous['taken']
        origin_key = item['key'] if previous is None else previous['key']
        if item['upper'] is not None and (item['upper'] - origin).total_seconds() <= bound:
            measured.append(_gap('successive', origin, item['upper'], origin_key, item['key']))
            previous = item
            continue
        # Another marker that already keeps this origin inside the bound makes
        # this object unnecessary, whether its own finish is missing or late.
        if previous is not None and _later_marker_covers(origin, item):
            continue
        if (previous is not None and not any(nxt['taken'] > item['taken'] for nxt in pending)
                and (now - previous['taken']).total_seconds() <= bound):
            continue
        late = item['lower'] is not None and (item['lower'] - origin).total_seconds() > bound
        if late:
            measured.append(_gap('successive', origin, item['lower'], origin_key, item['key']))
            previous = item
            continue
        finish = item['upper'] if item['upper'] is not None else item['lower']
        _unproven(origin, origin_key, item, finish)
        previous = item
    if previous is not None:
        measured.append(_gap('window_end', previous['taken'], now, previous['key'], None))
    elif not bounded and not unresolved:
        uncovered = True
    if bounded and len(objects) < 2:
        only = objects[0] if objects else None
        violations.append({'kind': 'count', 'from': None if only is None else _iso(only['taken']),
                           'to': None, 'gap_seconds': None,
                           'from_key': None if only is None else only['key'], 'to_key': None})
    if uncovered:
        violations.append({'kind': 'window_start', 'from': None, 'to': _iso(window_start),
                           'gap_seconds': None, 'from_key': None, 'to_key': None})
    for gap in measured:
        if gap['_raw'] > bound and not (gap['kind'] == 'window_start' and uncovered):
            violations.append(_public_gap(gap))
    for taken, violation in sorted(arrival_violations):
        if bounded or taken >= window_start:
            violations.append(violation)
    if not violations:
        violations.extend(unresolved)
    widest = None
    for gap in measured:
        if widest is None or gap['_raw'] > widest['_raw']:
            widest = gap
    result = 'fail' if any(item['kind'] != 'unresolved' for item in violations) else (
        'unresolved' if violations else 'pass')
    report = {
        'result': result,
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
        'anchor': _ref(cover) if (
            cover is not None and not bounded and cover['taken'] < window_start) else None,
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
        elif item['kind'] == 'unresolved':
            lines.append(
                f"unproven finish: {item['from']} -> {item['to']}  {item['to_key']}")
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
