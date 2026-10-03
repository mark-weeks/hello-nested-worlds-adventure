"""Cold-process recovery on disposable worlds, not evidence of hosted restore."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import shutil
import sqlite3
from urllib.parse import quote

import persistence as db
from persistence import interventions, participants
from multiverse import store
from tests.server_helpers import server


def logical_digest(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
        return hashlib.sha256('\n'.join(conn.iterdump()).encode()).hexdigest()


def test_cold_restore_keeps_identity_privacy_puzzles_and_one_pending_attempt(accounts, tmp_path, monkeypatch):
    original, other = accounts
    replacement = 'nw_' + 'c' * 32
    galaxy = store.world_tree(382).children[0].children[0]
    db.record_substance_change(382, galaxy.name, 'TEST_SETUP', None, {}, {'star_density': 400})
    node = quote(galaxy.name)
    body = {'node': galaxy.name, 'version': 3, 'request_id': 'restore-pending-attempt',
            'steps': [{'op': 'scatter'}]}
    snapshot = tmp_path / 'online.db'
    with server(db._DB_PATH) as request:
        assert request('/world')[0] == 403
        owner = request('/me', original)[1]['participant']['id']
        assert request('/position', original, {'node': galaxy.name, 'seed': 382, 'depth': 3})[0] == 200
        assert request('/journal/note', original, {'id': 'private-restore-note',
            'node': galaxy.name, 'text': 'Private rehearsal question'})[0] == 200
        puzzle = request('/puzzle?node_name=' + node, original)[1]
        status, receipt = request('/interventions/commit', original, body)
        assert status == 200 and receipt['accepted'] and receipt['phase'] == 'pending'
        participants.rotate(original, replacement)
        assert request('/me', original)[0] == 403
        assert request('/me', replacement)[1]['participant']['id'] == owner
        db.backup_to(snapshot)
    # Copy only the completed snapshot file, never a live WAL database.
    download = tmp_path / 'downloaded.db'
    shutil.copyfile(snapshot, download)
    download.chmod(0o400)
    with closing(sqlite3.connect(download.as_uri() + '?mode=ro', uri=True)) as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert conn.execute('PRAGMA journal_mode').fetchone() == ('delete',)
        # A read-time name-to-path join identifies every fixture history row.
        # This is feasibility evidence, not an alias migration implementation.
        total = conn.execute('SELECT COUNT(*) FROM world_mutations').fetchone()[0]
        mapped = conn.execute('SELECT COUNT(*) FROM world_mutations m JOIN world_nodes n '
                              'ON n.world_seed=m.world_seed AND n.name=m.node_name').fetchone()[0]
        assert mapped == total and total > 0
    restored = tmp_path / 'restored.db'
    monkeypatch.setattr(db, '_DB_PATH', restored)
    db.init_db()
    db.restore_from(download)
    assert logical_digest(download) == logical_digest(restored)
    assert not Path(str(download) + '-wal').exists()
    with server(restored) as request:
        assert request('/world')[0] == 403
        assert request('/me', original)[0] == 403
        assert request('/me', replacement)[1]['participant']['id'] == owner
        assert db.get_player_position(replacement)['node'] == galaxy.name
        assert request('/journal/data', replacement)[1]['notes'][0]['text'] == 'Private rehearsal question'
        assert request('/journal/data', other)[1]['notes'] == []
        assert request('/puzzle?node_name=' + node, replacement)[1] == puzzle
        assert request('/interventions/commit', replacement, body)[1] == receipt
        with db._connection() as conn:
            assert conn.execute('SELECT COUNT(*) FROM interventions').fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM intervention_work WHERE status='pending'").fetchone()[0] == 1
        # Accelerate only this disposable fixture's worker clock.
        later = datetime.now(timezone.utc) + timedelta(days=1)
        for step in range(5):
            interventions.advance(382, now=later + timedelta(minutes=step))
        assert interventions.live(382, galaxy)['star_density'] == 360
        with db._connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM intervention_work WHERE status='pending'").fetchone()[0] == 0
            count = conn.execute('SELECT COUNT(*) FROM world_mutations').fetchone()[0]
        assert request('/interventions/commit', replacement, body)[1] == receipt
        assert interventions.advance(382, now=later + timedelta(days=1)) == 0
        with db._connection() as conn:
            assert conn.execute('SELECT COUNT(*) FROM world_mutations').fetchone()[0] == count
