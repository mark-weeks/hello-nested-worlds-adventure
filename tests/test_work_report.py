"""Operator reports share a read snapshot and never claim or replay accepted work."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import subprocess
import sys

import pytest

import persistence as db
from persistence.recovery import work_report, format_report

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
PAST = '2026-09-14 11:59:00'
FUTURE = '2026-09-14 12:01:00'


@pytest.fixture
def queued_work():
    causal = db.enqueue_causal_hop(382, 'Place-1', 'SCALE_ACT', 1, 'down',
                                  {'actor_identity': 'PRIVATE-ACTOR', 'secret': 'PRIVATE-PAYLOAD'}, 0)
    maturation = db.enqueue_verb_maturation(382, 'Place-1', 'kindle', {}, 'PRIVATE-ACTOR', 0)
    other = db.enqueue_causal_hop(999, 'Elsewhere-1', 'SCALE_ACT', 1, 'down', {}, 0)
    with db.transaction() as conn:
        conn.execute("UPDATE causal_queue SET due_at=?", (PAST,))
        conn.execute("UPDATE causal_queue SET attempts=2,last_error='Unsupported version',retry_at=? WHERE id=?",
                     (FUTURE, causal))
        conn.execute("UPDATE verb_maturation SET due_at=?", (FUTURE,))
        conn.execute('''INSERT INTO situations(id,world_seed,slug,definition_version,definition,phase,deadline)
            VALUES ('instance',382,'signal',1,'{}','decision',?)''', (PAST,))
        for step in range(3):
            conn.execute('''INSERT INTO situation_work(situation_id,step,due_at) VALUES ('instance',?,?)''',
                         (step, PAST))
        conn.execute("UPDATE situation_work SET attempts=1,last_error='Storage unavailable',retry_at=? WHERE step=0",
                     (FUTURE,))
        conn.execute('''INSERT INTO interventions(id,world_seed,participant_id,node_name,version,plan,signal,route,performer)
            VALUES ('arrangement',382,'PRIVATE-PARTICIPANT','Place-1',2,'{"secret":"PRIVATE-PLAN"}','{}','[]','Ada')''')
        for hop in range(2):
            conn.execute('''INSERT INTO intervention_work(intervention_id,hop,node_name,due_at)
                VALUES ('arrangement',?,?,?)''', (hop, f'Place-{hop + 1}', PAST))
        conn.execute("UPDATE intervention_work SET attempts=1,last_error='Interpreter unavailable',retry_at=? WHERE hop=0",
                     (FUTURE,))
        completed = conn.execute('''INSERT INTO causal_queue
            (world_seed,node_name,kind,strength,direction,payload,due_at,status,outcome)
            VALUES (382,'Place-1','SCALE_ACT',1,'down','{}',?,'completed','applied')''', (PAST,)).lastrowid
    return causal, maturation, other, completed


def snapshot():
    with db._connection() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {t: conn.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables}


def test_report_counts_scopes_backoff_and_predecessors_without_writes(queued_work):
    before = snapshot()
    report = work_report(db._DB_PATH, now=NOW)
    causal = report['queues']['causal_queue']
    assert (causal['pending'], causal['due'], causal['eligible'], causal['failed_pending']) == (2, 2, 1, 1)
    assert causal['oldest_due_age_seconds'] == 60
    assert report['queues']['verb_maturation']['scheduled'] == 1
    situation = report['queues']['situation_work']
    assert (situation['pending'], situation['due'], situation['eligible']) == (3, 3, 0)
    assert (situation['backed_off'], situation['waiting_for_predecessor']) == (1, 2)
    assert situation['samples'][1]['blocked_by'] == situation['samples'][0]['id']
    intervention = report['queues']['intervention_work']
    assert (intervention['pending'], intervention['due'], intervention['eligible']) == (2, 2, 0)
    assert (intervention['backed_off'], intervention['waiting_for_predecessor'], intervention['failed_pending']) == (1, 1, 1)
    assert intervention['samples'][1]['blocked_by'] == intervention['samples'][0]['id']
    assert (intervention['samples'][0]['version'], intervention['samples'][0]['world_seed']) == (2, 382)
    assert report['decisions']['due'] == 1
    scoped = work_report(db._DB_PATH, seed=382, limit=1, now=NOW)
    assert scoped['queues']['causal_queue']['pending'] == 1
    assert scoped['queues']['causal_queue']['eligible'] == 0
    assert scoped['queues']['situation_work']['samples_truncated']
    assert len(scoped['queues']['situation_work']['samples']) == 1
    unknown = work_report(db._DB_PATH, seed=123, now=NOW)
    assert all(q['pending'] == 0 for q in unknown['queues'].values())
    assert unknown['decisions']['open'] == 0
    assert snapshot() == before
    text = json.dumps(report) + format_report(report)
    assert 'PRIVATE-ACTOR' not in text and 'PRIVATE-PAYLOAD' not in text
    assert 'PRIVATE-PARTICIPANT' not in text and 'PRIVATE-PLAN' not in text
    assert 'Storage unavailable' in text and 'Interpreter unavailable' in text


def test_report_does_not_wait_for_writer_or_initialize_database(queued_work, monkeypatch):
    def forbidden():
        raise AssertionError('Read-only reporting must not initialize or claim work')
    monkeypatch.setattr(db, 'init_db', forbidden)
    with db._connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        assert work_report(db._DB_PATH, now=NOW)['queues']['situation_work']['pending'] == 3


def test_report_limits_and_missing_database_fail_without_creation(tmp_path):
    missing = tmp_path / 'missing.db'
    with pytest.raises(sqlite3.OperationalError):
        work_report(missing)
    assert not missing.exists()
    for limit in (0, -1, 101, True):
        with pytest.raises(ValueError):
            work_report(missing, limit=limit)


def test_old_schema_is_rejected_without_migration(tmp_path):
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as conn:
        conn.executescript('CREATE TABLE schema_version(version INTEGER); INSERT INTO schema_version VALUES (22);')
    before = path.read_bytes()
    with pytest.raises(ValueError, match='schema 23'):
        work_report(path)
    assert path.read_bytes() == before


def test_inspection_and_retry_cover_all_queues_but_never_complete_work(queued_work):
    causal, maturation, _, completed = queued_work
    with db._connection() as conn:
        situation = conn.execute('SELECT id FROM situation_work WHERE step=0').fetchone()[0]
        intervention = conn.execute('SELECT id FROM intervention_work WHERE hop=0').fetchone()[0]
    for queue, work_id in [('causal_queue', causal), ('verb_maturation', maturation),
                           ('situation_work', situation), ('intervention_work', intervention)]:
        before = db.inspect_work(queue, work_id)
        assert db.retry_work(queue, work_id)
        after = db.inspect_work(queue, work_id)
        assert after == {**before, 'retry_at': None}
        assert not db.retry_work(queue, 999999)
        assert db.inspect_work(queue, 999999) is None
    fence = db.inspect_work('causal_queue', completed)
    assert not db.retry_work('causal_queue', completed)
    assert db.inspect_work('causal_queue', completed) == fence
    for queue in ('world_mutations', 'situation_work; DELETE FROM situation_work'):
        with pytest.raises(ValueError):
            db.inspect_work(queue, 1)
        with pytest.raises(ValueError):
            db.retry_work(queue, 1)
    # The generic delivery interpreter must still reject situation and intervention work.
    with pytest.raises(ValueError):
        db.deliver_work('situation_work', situation, lambda row: 'applied')
    with pytest.raises(ValueError):
        db.deliver_work('intervention_work', intervention, lambda row: 'applied')


def test_cli_json_and_human_report_use_existing_copy(queued_work, tmp_path, monkeypatch):
    before = snapshot()
    monkeypatch.chdir(tmp_path)
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'main.py'), 'work-report', '--db', str(db._DB_PATH), '--seed', '382', '--limit', '1']
    result = subprocess.run([*command, '--json'], capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report['world_seed'] == 382
    assert report['queues']['causal_queue']['pending'] == 1
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    assert 'situation_work: pending=3' in result.stdout
    assert 'Unsettled decisions: open=1' in result.stdout
    assert snapshot() == before
    missing = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'main.py'), 'work-report', '--db', str(db._DB_PATH.parent / 'absent.db')],
                             capture_output=True, text=True)
    assert missing.returncode != 0 and 'Work report unavailable' in missing.stderr
    assert 'Traceback' not in missing.stderr


def test_completed_history_does_not_dominate_report_work(queued_work, monkeypatch):
    with db.transaction() as conn:
        conn.executemany('''INSERT INTO causal_queue
            (world_seed,node_name,kind,strength,direction,payload,due_at,status,outcome)
            VALUES (382,'Place-1','SCALE_ACT',1,'down','{}',?,'completed','applied')''', [(PAST,)] * 20_000)
    original = sqlite3.connect
    def bounded(*args, **kwargs):
        conn = original(*args, **kwargs)
        steps = 0
        def progress():
            nonlocal steps
            steps += 100
            return steps > 5_000
        conn.set_progress_handler(progress, 100)
        return conn
    monkeypatch.setattr(sqlite3, 'connect', bounded)
    assert work_report(db._DB_PATH, now=NOW)['queues']['causal_queue']['pending'] == 2


def test_report_handles_encoded_file_paths(queued_work, tmp_path):
    target = tmp_path / 'copy ?# world.db'
    db.backup_to(target)
    assert work_report(target, now=NOW)['queues']['situation_work']['pending'] == 3


@pytest.mark.parametrize('existing_wal_copy', [False, True])
def test_backup_report_needs_no_writable_directory(queued_work, tmp_path, existing_wal_copy):
    directory = tmp_path / 'read-only'
    directory.mkdir()
    target = directory / 'backup.db'
    if existing_wal_copy:
        with closing(sqlite3.connect(target)) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('CREATE TABLE old_copy (id INTEGER)')
            conn.commit()
    expected = work_report(db._DB_PATH, now=NOW)
    db.backup_to(target)
    # Assert the portable format even on root/Windows runners that bypass mode bits.
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
    before = target.read_bytes()
    target.chmod(0o444)
    directory.chmod(0o555)
    try:
        assert work_report(target, now=NOW) == expected
        assert sorted(p.name for p in directory.iterdir()) == ['backup.db']
        assert target.read_bytes() == before
    finally:
        directory.chmod(0o755)
        target.chmod(0o600)
    with db._connection() as conn:
        assert conn.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
