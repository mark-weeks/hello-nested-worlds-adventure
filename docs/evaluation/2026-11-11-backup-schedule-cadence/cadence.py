"""Re-derive the figures in docs/evaluation/2026-11-11-backup-schedule-cadence.md.

Reads the two CSV files beside this script and prints every count the record
quotes. It contacts nothing and reads no clock: the inputs are a snapshot of
GitHub's Actions run list for backup.yml and of the CI runs used as a control,
both taken on 2026-11-11. One check imports the repository's own freshness
rule (scripts/backup_store.assess_objects), so run it from a checkout.

    python docs/evaluation/2026-11-11-backup-schedule-cadence/cadence.py

The cron eras are the committer times of the commits on main that changed the
cron line in .github/workflows/backup.yml (git log --follow on that file).
"""
import csv
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))  # the repository root, for scripts.backup_store


def utc(text):
    return datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


# (label, cron minutes, cron hours, in force from). Each era ends where the next begins.
ERAS = [
    ('daily      0 6 * * *', (0,), (6,), utc('2026-07-06T02:24:54Z')),      # 20b5915 (#57)
    ('hourly     17 * * * *', (17,), tuple(range(24)), utc('2026-07-19T04:54:19Z')),  # 818b617 (#69)
    ('half-hour  17,47 * * * *', (17, 47), tuple(range(24)), utc('2026-10-03T19:50:45Z')),  # 8cfa6cb (#109)
]


def load_runs():
    with open(HERE / 'backup_runs.csv', newline='') as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row['start'] = utc(row['run_started_at'])
        row['seconds'] = (utc(row['updated_at']) - row['start']).total_seconds()
    return sorted(rows, key=lambda row: row['start'])


def ticks(minutes, hours, after, until):
    """Cron ticks t with after < t <= until."""
    out = []
    hour = after.replace(minute=0, second=0, microsecond=0)
    while hour <= until:
        if hour.hour in hours:
            for minute in minutes:
                tick = hour.replace(minute=minute)
                if after < tick <= until:
                    out.append(tick)
        hour += timedelta(hours=1)
    return out


def quantile(values, q):
    values = sorted(values)
    position = (len(values) - 1) * q
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def gaps_hours(starts):
    return [(b - a).total_seconds() / 3600 for a, b in zip(starts, starts[1:])]


def age_quantile(gaps, q):
    """Age of the newest run at a uniformly random instant: its q-quantile."""
    total = sum(gaps)
    low, high = 0.0, max(gaps)
    for _ in range(60):
        mid = (low + high) / 2
        if sum(min(gap, mid) for gap in gaps) / total < q:
            low = mid
        else:
            high = mid
    return high


def first_check(start):
    """The first :05 at or after the window starts."""
    check = start.replace(minute=5, second=0)
    return check if check >= start else check + timedelta(hours=1)


def report_window(label, starts):
    gaps = gaps_hours(starts)
    total = sum(gaps)
    print(f'\n== {label}: {len(starts)} runs, {len(gaps)} gaps, {total:.1f} h')
    print(f'   gap mean {statistics.mean(gaps):.2f}  median {statistics.median(gaps):.2f}  '
          f'min {min(gaps):.2f}  p95 {quantile(gaps, 0.95):.2f}  max {max(gaps):.2f} h; '
          f'gaps <= 1 h: {sum(gap <= 1 for gap in gaps)}')
    widest = max(range(len(gaps)), key=lambda index: gaps[index])
    print(f'   widest gap starts {starts[widest]:%Y-%m-%d %H:%M} UTC')
    for limit in (1, 2, 4, 6, 8, 12):
        share = sum(min(gap, limit) for gap in gaps) / total
        print(f'   newest run <= {limit:>2} h old for {share * 100:5.1f}% of the time')
    mean_age = sum(gap * gap / 2 for gap in gaps) / total
    print(f'   age of newest run at a random instant: mean {mean_age:.2f}  '
          f'median {age_quantile(gaps, 0.5):.2f}  p95 {age_quantile(gaps, 0.95):.2f}  '
          f'max {max(gaps):.2f} h')
    widest_seconds = max((b - a).total_seconds() for a, b in zip(starts, starts[1:]))
    print(f'   smallest --max-age-minutes that never reads stale: {math.ceil(widest_seconds / 60)}')
    over = [gap - 1 for gap in gaps if gap > 1]
    print(f'   under 60 minutes: {len(over)} stale stretches, mean {statistics.mean(over):.2f} h, '
          f'longest {max(over):.2f} h')
    check = first_check(starts[0])
    index = fresh = checks = 0
    while check <= starts[-1]:
        while index + 1 < len(starts) and starts[index + 1] <= check:
            index += 1
        checks += 1
        fresh += (check - starts[index]).total_seconds() <= 3600
        check += timedelta(hours=1)
    print(f'   an hourly check at :05 with the 60-minute default: {checks} checks, '
          f'{fresh} fresh, {checks - fresh} stale ({(checks - fresh) / checks * 100:.1f}%)')


def repository_check(starts, app='enfolded-beta'):
    """The same hourly check, decided by scripts/backup_store.assess_objects.

    Each run in the window is taken to have stored one validated object whose
    snapshot-start is the run's start. That is the kindest reading: the real
    stamp is taken some seconds later, after the tools are installed.
    """
    from scripts.backup_store import assess_objects, object_key
    page = {'Contents': [{'Key': object_key(app, start.strftime('%Y%m%dT%H%M%SZ')), 'Size': 1}
                         for start in starts]}
    outcomes = Counter()
    check = first_check(starts[0])
    while check <= starts[-1]:
        outcomes[assess_objects([page], app=app, max_age_minutes=60, now=check)['status']] += 1
        check += timedelta(hours=1)
    print(f'\n-- scripts/backup_store.assess_objects, half-hourly window, hourly at :05, '
          f'60 minutes: {dict(outcomes)}')
    # A window is oldest one second before the next object appears, so those
    # instants decide whether a limit would ever have read stale.
    for minutes in (120, 360, 600, 624, 625):
        stale = sum(
            assess_objects([page], app=app, max_age_minutes=minutes,
                           now=following - timedelta(seconds=1))['status'] != 'fresh'
            for following in starts[1:])
        print(f'   --max-age-minutes {minutes}: stale before {stale} of {len(starts) - 1} '
              f'following objects')


def main():
    runs = load_runs()
    starts = [row['start'] for row in runs]
    last = starts[-1]
    print(f'{len(runs)} runs, #{runs[0]["run_number"]} to #{runs[-1]["run_number"]}, '
          f'{starts[0]:%Y-%m-%d %H:%M} to {last:%Y-%m-%d %H:%M} UTC')
    print('events:', dict(Counter(row['event'] for row in runs)))
    print('conclusions:', dict(Counter(row['conclusion'] for row in runs)))
    for row in runs:
        if row['conclusion'] != 'success':
            print(f'   not success: #{row["run_number"]} run {row["run_id"]} '
                  f'{row["start"]:%Y-%m-%d %H:%M} {row["conclusion"]}')

    print('\n-- did the workflow\'s concurrency group ever hold a run back?')
    numbers = [int(row['run_number']) for row in sorted(runs, key=lambda row: int(row['run_number']))]
    print(f'   run numbers 1 to {len(runs)} with none missing: {numbers == list(range(1, len(runs) + 1))}; '
          f'cancelled runs: {sum(row["conclusion"] == "cancelled" for row in runs)}')
    overlaps = sum(later['start'] < utc(earlier['updated_at']) for earlier, later in zip(runs, runs[1:]))
    shortest = min((b - a).total_seconds() for a, b in zip(starts, starts[1:])) / 60
    print(f'   runs that started before the run before them was last updated: {overlaps}; '
          f'shortest gap between two starts: {shortest:.1f} min')

    print('\n-- scheduled ticks against runs started, by cron era')
    bounds = [era[3] for era in ERAS] + [last]
    for (label, minutes, hours, begin), end in zip(ERAS, bounds[1:]):
        era_runs = [row for row in runs if begin < row['start'] <= end]
        expected = ticks(minutes, hours, begin, end)
        seconds = [row['seconds'] for row in era_runs]
        print(f'   {label:<26} {begin:%m-%d %H:%M} to {end:%m-%d %H:%M}: '
              f'{len(expected):>4} ticks, {len(era_runs):>3} runs '
              f'({len(era_runs) / len(expected) * 100:5.1f}%), '
              f'{(end - begin).total_seconds() / 86400 / len(era_runs) * 24:.2f} h per run; '
              f'run length median {statistics.median(seconds):.0f} s, '
              f'over 20 s: {sum(value > 20 for value in seconds)}')

    print('\n-- daily era: hours after the 06:00 UTC tick')
    late = [(row['start'] - row['start'].replace(hour=6, minute=0, second=0)).total_seconds() / 3600
            for row in runs if row['start'] <= ERAS[1][3]]
    print(f'   n {len(late)}  min {min(late):.2f}  median {statistics.median(late):.2f}  '
          f'max {max(late):.2f}')

    print('\n-- by ISO week (weeks that hold only hourly or half-hourly ticks)')
    by_week = Counter(row['start'].strftime('%G-W%V') for row in runs)
    monday = datetime(2026, 7, 20, tzinfo=timezone.utc)
    while monday <= last:
        week_end = min(monday + timedelta(days=7), last + timedelta(seconds=1))
        expected = 0
        for (label, minutes, hours, begin), end in zip(ERAS, bounds[1:]):
            low = max(monday, begin) - timedelta(seconds=1)
            high = min(week_end, end + timedelta(seconds=1)) - timedelta(seconds=1)
            if low < high:
                expected += len(ticks(minutes, hours, low, high))
        key = monday.strftime('%G-W%V')
        print(f'   {key} from {monday:%m-%d}: {by_week[key]:>3} runs of {expected:>3} ticks '
              f'({by_week[key] / expected * 100:5.1f}%)')
        monday += timedelta(days=7)

    half = [start for start in starts if start > ERAS[2][3]]
    hourly = [start for start in starts if ERAS[1][3] < start <= ERAS[2][3]]
    report_window('half-hourly cron, 2026-10-03 to 2026-11-10', half)
    report_window('last 14 days of the snapshot', [s for s in starts if s >= last - timedelta(days=14)])
    report_window('window first observed, 2026-10-31 23:44 to 2026-11-10 23:25',
                  [s for s in starts if s >= utc('2026-10-31T23:44:00Z')])
    report_window('hourly cron, 2026-07-19 to 2026-10-03', hourly)
    report_window('hourly cron, best fortnight, 2026-08-10 to 2026-08-23',
                  [s for s in hourly if utc('2026-08-10T00:00:00Z') <= s < utc('2026-08-24T00:00:00Z')])
    report_window('hourly cron, 2026-08-31 to 2026-10-03',
                  [s for s in hourly if s >= utc('2026-08-31T00:00:00Z')])

    repository_check(half)

    print('\n-- control: CI runs for pushes to main, seconds from commit to run created')
    with open(HERE / 'ci_push_control.csv', newline='') as handle:
        control = list(csv.DictReader(handle))
    waits = [(utc(row['run_created_at']) - utc(row['commit_committed_at'])).total_seconds()
             for row in control]
    print(f'   n {len(waits)}, {min(row["run_created_at"] for row in control)} to '
          f'{max(row["run_created_at"] for row in control)}: '
          f'min {min(waits):.0f}  median {statistics.median(waits):.1f}  max {max(waits):.0f} s')


if __name__ == '__main__':
    main()
