"""Read-only operator diagnostics; never initialize, migrate, or drain a database."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

QUEUES = ('causal_queue', 'verb_maturation', 'situation_work')


def _pending_sql(queue, seed):
    scope = '' if seed is None else ' AND world_seed = :seed'
    if queue != 'situation_work':
        return f'''SELECT id, world_seed, node_name, due_at, retry_at, attempts,
            last_error, semantics_version AS version, NULL AS situation_id,
            NULL AS step, NULL AS blocked_by
            FROM {queue} WHERE status = 'pending'{scope}'''
    # Keep orphaned work visible in an unscoped report; never infer its world.
    return f'''SELECT w.id, s.world_seed, NULL AS node_name, w.due_at, w.retry_at,
        w.attempts, w.last_error, s.definition_version AS version, w.situation_id,
        w.step, (SELECT p.id FROM situation_work p
            WHERE p.situation_id = w.situation_id AND p.step < w.step
                AND p.status = 'pending' ORDER BY p.step LIMIT 1) AS blocked_by
        FROM situation_work w LEFT JOIN situations s ON s.id = w.situation_id
        WHERE w.status = 'pending'{scope}'''


def work_report(db_path: Path, *, seed: int | None = None, limit: int = 20,
                now: datetime | None = None) -> dict:
    """Snapshot pending work across all queues, plus unsettled decision deadlines.

    Counts cover pending rows; samples are bounded per queue. Due/failed/backoff/
    predecessor categories overlap. Eligible means schedule-eligible, not that
    the configured pump is running or that the stored version can be interpreted.
    No payloads, actor identities, credentials, or journal contents are selected.
    Existing diagnostic error strings remain operator-only data.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Sample limit must be between 1 and 100 per queue.')
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    moment = moment.replace(microsecond=0)
    stamp = moment.isoformat(sep=' ')
    uri = Path(db_path).expanduser().resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only = ON')
        conn.execute('BEGIN')  # One consistent read snapshot; never a writer claim.
        version = conn.execute('SELECT MAX(version) FROM schema_version').fetchone()[0]
        if version is None or version < 23:
            raise ValueError('Work reports require schema 23 or later; this command never upgrades a database.')
        report = {'as_of_utc': stamp + 'Z', 'world_seed': seed,
                  'schema_version': version, 'sample_limit_per_queue': limit, 'queues': {}}
        for queue in QUEUES:
            sql = _pending_sql(queue, seed)
            params = {'seed': seed, 'now': stamp, 'limit': limit}
            counts = dict(conn.execute(f'''WITH pending AS ({sql})
                SELECT COUNT(*) AS pending,
                    COALESCE(SUM(due_at <= :now), 0) AS due,
                    COALESCE(SUM(due_at > :now), 0) AS scheduled,
                    COALESCE(SUM(last_error IS NOT NULL), 0) AS failed_pending,
                    COALESCE(SUM(retry_at > :now), 0) AS backed_off,
                    COALESCE(SUM(blocked_by IS NOT NULL), 0) AS waiting_for_predecessor,
                    COALESCE(SUM(due_at <= :now AND (retry_at IS NULL OR retry_at <= :now)
                        AND blocked_by IS NULL), 0) AS eligible,
                    MIN(CASE WHEN due_at <= :now THEN due_at END) AS oldest_due_at
                FROM pending''', params).fetchone())
            due = counts['oldest_due_at']
            counts['oldest_due_age_seconds'] = (
                int((moment - datetime.fromisoformat(due)).total_seconds()) if due else None)
            samples = conn.execute(f'''WITH pending AS ({sql})
                SELECT * FROM pending
                ORDER BY (last_error IS NOT NULL) DESC, due_at, id LIMIT :limit''', params).fetchall()
            counts['samples'] = [dict(row) for row in samples]
            counts['samples_truncated'] = counts['pending'] > len(samples)
            report['queues'][queue] = counts
        scope = '' if seed is None else ' AND world_seed = :seed'
        decisions = dict(conn.execute(f'''SELECT COUNT(*) AS open,
                COALESCE(SUM(deadline <= :now), 0) AS due,
                MIN(CASE WHEN deadline <= :now THEN deadline END) AS oldest_due_at
            FROM situations WHERE phase = 'decision'{scope}''', params).fetchone())
        decisions['samples'] = [dict(row) for row in conn.execute(f'''SELECT id, world_seed,
                definition_version AS version, deadline
            FROM situations WHERE phase = 'decision'{scope}
            ORDER BY deadline, id LIMIT :limit''', params)]
        decisions['samples_truncated'] = decisions['open'] > len(decisions['samples'])
        report['decisions'] = decisions
        return report


def format_report(report: dict) -> str:
    import json

    scope = 'all worlds' if report['world_seed'] is None else f"world {report['world_seed']}"
    lines = [f"Delayed work at {report['as_of_utc']} — {scope}",
             'Due includes backoff and predecessor waits. Eligible does not prove worker health.']
    for queue, row in report['queues'].items():
        age = row['oldest_due_age_seconds']
        lines.append(f"{queue}: pending={row['pending']} due={row['due']} "
                     f"eligible={row['eligible']} failed={row['failed_pending']} "
                     f"backoff={row['backed_off']} predecessor_wait={row['waiting_for_predecessor']} "
                     f"oldest_due_age_seconds={age if age is not None else '-'}")
        for sample in row['samples']:
            # JSON escaping keeps stored diagnostic control characters out of the terminal.
            lines.append('  ' + json.dumps(sample, sort_keys=True))
        if row['samples_truncated']:
            lines.append(f"  Showing {len(row['samples'])} of {row['pending']} pending items.")
    decisions = report['decisions']
    lines.append(f"Unsettled decisions: open={decisions['open']} due={decisions['due']}")
    lines.extend('  ' + json.dumps(row, sort_keys=True) for row in decisions['samples'])
    if decisions['samples_truncated']:
        lines.append(f"  Showing {len(decisions['samples'])} of {decisions['open']} decisions.")
    return '\n'.join(lines)
