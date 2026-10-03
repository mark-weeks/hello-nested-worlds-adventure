"""Validation failure must preserve the downloaded file for quarantined retention."""
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from scripts.validate_backup import validate


@pytest.mark.parametrize('kind,expected', [('current', 0), ('older-schema', 1), ('corrupt', 1)])
def test_snapshot_validation_never_modifies_or_discards_download(tmp_path, kind, expected):
    snapshot = tmp_path / 'snapshot #1?.db'
    if kind == 'corrupt':
        snapshot.write_bytes(b'damaged SQLite fixture')
    else:
        with closing(sqlite3.connect(snapshot)) as db:
            for table in ('world_nodes', 'world_mutations', 'invite_keys', 'intervention_work'):
                if kind == 'older-schema' and table == 'intervention_work':
                    continue
                db.execute(f'CREATE TABLE {table} (id INTEGER)')
            db.commit()
    before = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    snapshot.chmod(0o400)
    script = Path(__file__).resolve().parents[1] / 'scripts/validate_backup.py'
    result = subprocess.run([sys.executable, str(script), str(snapshot)], capture_output=True, text=True)
    assert result.returncode == expected, result.stderr
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == before
    if expected:
        assert 'retain as unvalidated' in result.stderr


def test_missing_snapshot_is_not_created_by_validation(tmp_path):
    path = tmp_path / 'missing.db'
    with pytest.raises(sqlite3.OperationalError):
        validate(path)
    assert not path.exists()
