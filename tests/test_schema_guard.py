"""A binary refuses a chronicle newer than the migrations it ships.

Migrations are forward-only. Downgrading across a schema bump is a
disaster restore, never an older process opened against the newer file.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

import persistence
import server
from main import main

_ROOT = Path(__file__).resolve().parents[1]


def _probe():
    spec = importlib.util.spec_from_file_location(
        "schema_probe", _ROOT / "scripts" / "schema_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "worlds.db"
    monkeypatch.setattr(persistence, "_DB_PATH", db_path)
    yield db_path


def _versions():
    conn = sqlite3.connect(persistence._DB_PATH)
    try:
        return [row[0] for row in conn.execute(
            "SELECT version FROM schema_version ORDER BY version")]
    finally:
        conn.close()


def test_known_schema_matches_migration_files_and_the_probe():
    probe = _probe()
    root = persistence._MIGRATIONS_DIR
    assert persistence.known_schema_version() == max(
        version for version, _path in persistence._list_migrations())
    assert probe.known_version(root) == persistence.known_schema_version()
    assert probe.migration_versions(root) == [
        version for version, _path in persistence._list_migrations()]


def test_probe_ignores_stray_files_and_uses_the_highest_number(tmp_path):
    probe = _probe()
    root = tmp_path / "migrations"
    root.mkdir()
    (root / "README.md").write_text("notes")
    (root / "notes.sql").write_text("SELECT 1;")
    (root / "0002_b.sql").write_text("SELECT 2;")
    (root / "0010_c.sql").write_text("SELECT 10;")
    assert probe.migration_versions(root) == [2, 10]
    assert probe.known_version(root) == 10
    assert probe.known_version(tmp_path / "missing") is None


def test_newer_schema_applies_nothing_and_is_not_marked_ready(tmp_path, monkeypatch):
    mig = tmp_path / "migrations"
    mig.mkdir()
    (mig / "0001_a.sql").write_text(
        "CREATE TABLE IF NOT EXISTS kept (id INTEGER);")
    monkeypatch.setattr(persistence, "_MIGRATIONS_DIR", mig)
    db = persistence._DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(persistence._SCHEMA_VERSION_DDL)
    conn.execute("INSERT INTO schema_version (version) VALUES (2)")
    conn.commit()
    conn.close()

    with pytest.raises(persistence.SchemaTooNewError) as exc:
        persistence.init_db()
    message = str(exc.value)
    assert "schema_version 2" in message
    assert "schema 1" in message
    assert "no in-place downgrade" in message
    assert "Traceback" not in message

    conn = sqlite3.connect(db)
    try:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name='kept'").fetchone() is None
        assert conn.execute(
            "SELECT version FROM schema_version").fetchall() == [(2,)]
    finally:
        conn.close()
    assert db not in persistence._initialized
    with pytest.raises(persistence.SchemaTooNewError):
        persistence.init_db()


def test_older_database_still_receives_later_migrations(tmp_path, monkeypatch):
    mig = tmp_path / "migrations"
    mig.mkdir()
    (mig / "0001_a.sql").write_text(
        "CREATE TABLE IF NOT EXISTS kept (id INTEGER);")
    (mig / "0002_b.sql").write_text(
        "CREATE TABLE IF NOT EXISTS added (id INTEGER);")
    monkeypatch.setattr(persistence, "_MIGRATIONS_DIR", mig)
    db = persistence._DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(persistence._SCHEMA_VERSION_DDL)
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")
    conn.execute("CREATE TABLE kept (id INTEGER);")
    conn.commit()
    conn.close()

    persistence.init_db()
    assert _versions() == [1, 2]
    conn = sqlite3.connect(db)
    try:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name='added'").fetchone() is not None
    finally:
        conn.close()


def test_read_applied_schema_does_not_create_or_migrate(tmp_path):
    missing = tmp_path / "no such" / "worlds.db"
    assert persistence.read_applied_schema_version(missing) is None
    assert not missing.exists()

    db = tmp_path / "plain.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_version (version) VALUES (4)")
    conn.execute("INSERT INTO schema_version (version) VALUES (9)")
    conn.commit()
    conn.close()
    assert persistence.read_applied_schema_version(db) == 9
    # Opening read-only did not create a second writer schema.
    assert persistence.read_applied_schema_version(db) == 9


def test_schema_version_command_is_read_only(capsys):
    assert not persistence._DB_PATH.exists()
    main(["schema-version"])
    out = capsys.readouterr().out
    assert f"known {persistence.known_schema_version()}" in out
    assert "applied none" in out
    assert not persistence._DB_PATH.exists()


def test_schema_version_command_refuses_a_newer_chronicle(capsys):
    persistence.init_db()
    future = persistence.known_schema_version() + 1
    persistence._initialized.discard(persistence._DB_PATH)
    conn = sqlite3.connect(persistence._DB_PATH)
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (future,))
    conn.commit()
    before = conn.execute(
        "SELECT name FROM sqlite_master ORDER BY name").fetchall()
    conn.close()

    with pytest.raises(SystemExit) as exc:
        main(["schema-version"])
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert f"applied {future}" in captured.out
    assert f"schema_version {future}" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out

    conn = sqlite3.connect(persistence._DB_PATH)
    try:
        assert conn.execute(
            "SELECT name FROM sqlite_master ORDER BY name").fetchall() == before
        assert future in _versions()
    finally:
        conn.close()


def test_cli_refuses_a_newer_chronicle_without_a_traceback(capsys):
    persistence.init_db()
    future = persistence.known_schema_version() + 3
    persistence._initialized.discard(persistence._DB_PATH)
    conn = sqlite3.connect(persistence._DB_PATH)
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (future,))
    conn.commit()
    conn.close()

    with pytest.raises(SystemExit) as exc:
        main(["invite", "list"])
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "No invite keys" not in captured.out
    assert f"schema_version {future}" in captured.err
    assert "Traceback" not in captured.err


def test_server_refuses_a_newer_chronicle_before_bind(monkeypatch, capsys):
    persistence.init_db()
    future = persistence.known_schema_version() + 1
    persistence._initialized.discard(persistence._DB_PATH)
    conn = sqlite3.connect(persistence._DB_PATH)
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (future,))
    conn.commit()
    conn.close()

    def bound(*_args, **_kwargs):
        raise AssertionError("server bound a port")

    monkeypatch.setattr(server, "_ThreadedServer", bound)
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert f"schema_version {future}" in err
    assert "Traceback" not in err
